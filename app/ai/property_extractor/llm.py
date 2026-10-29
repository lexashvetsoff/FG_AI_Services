import re
import json
import ollama
import logging
import asyncio
from rapidfuzz import fuzz, process
from typing import List, Union, Dict, Optional, Set
from app.config import settings
from app.schemas.schemas import (
    ExtractRequest,
    ExtractData,
    ClassifyAndExtractRequest,
    ClassifyAndExtractResponse,
    SingleTextResult,
    TextItem,
    CategorySchema,
    ClassifyRequest,
    ClassifyResponse,
    ProductClassification,
    ClassificationDimension,
    AllowedValue,
    ProductItem,
    MNNProductItem,
    MNNDictionaryItem,
    MNNClassifyResult,
    MNNClassifyRequest,
    MNNClassifyResponse,
    DosageCleanRequest,
    DosageCleanResponse,
    DosageItem
)


CHUNK_SIZE = 10
DIM_DOS = 'dim_doz'
logger = logging.getLogger(__name__)


class LLMClassifier:
    _DOSAGE_EXTRACTION_PROMPT = """Ты — строгий фармацевтический алгоритм.
Твоя задача — извлечь из текста товара ДОЗИРОВКУ (количество активного вещества и/или объем).

ПРАВИЛА:
1. Ищи ЛЮБОЕ упоминание массы, объема или концентрации:
   - Простая масса: "250мг", "500мг", "1г", "0.5г"
   - Простой объем: "100мл", "5мл", "1л"
   - Концентрация: "7.5мг/мл", "1%", "0.05%"
   - Сложные паттерны: "7.5мг/мл-100мл", "100мг/5мл-20.925г", "120мг(70мг/мл)-1.7мл"
   - Комбинированные: "5мг+8мг+20мг", "2мг+0.035мг"
   - На дозу/впрыск: "0.255мг/доза", "35мкг/доза-15мл"
   - Международные единицы: "10000МЕ", "3млн.МЕ"
2. Извлекай дозировку ЦЕЛИКОМ, как она написана в тексте (включая дефисы, скобки, плюсы).
3. ИГНОРИРУЙ количество в упаковке (N20, N10, №10, №30 и т.д.) — это НЕ дозировка.
4. Если в тексте НЕСКОЛЬКО дозировок (например, "5мг/мл-100мл"), верни их все через запятую.
5. Если дозировка не найдена, верни пустую строку.
6. Верни ТОЛЬКО валидный JSON.

ПРИМЕРЫ:
- "Амоксициллин (таб. 250мг N20 вн )" → "250мг"
- "Лазолван (р-р 7.5мг/мл-100мл фл. вн, д/инг )" → "7.5мг/мл-100мл"
- "Баралгин М (р-р 0.5г/мл-5мл N5 амп. д/ин )" → "0.5г/мл-5мл"
- "Африн (спрей 0.05%-15мл фл. назал )" → "0.05%-15мл"
- "Тербинафин-Вертекс (крем 1%-15г наруж )" → "1%-15г"

ФОРМАТ ОТВЕТА:
{
  "extracted_dosage": "извлеченная дозировка или пустая строка",
  "reasoning": "Краткое пояснение: что нашел и как извлек."
}
"""

    def __init__(self):
        self._client = ollama.AsyncClient(host=settings.ANALYST_OLLAMA_HOST)
        self._semaphore = asyncio.Semaphore(settings.OLLAMA_CONCURRENCY_LIMIT)

    def build_prompt(self, product: ProductItem, dimensions: List[ClassificationDimension]) -> str:
        dims_desc = []
        for dim in dimensions:
            vals = []
            for v in dim.allowed_values:
                vals.append(f"{v.code}=[{', '.join(v.values)}]")
            
            format_hint = "верни ОДИН код (строку) или null" if not dim.is_multi_value else "верни МАССИВ кодов (даже если один)"
            dims_desc.append(f"{dim.name} ({dim.id}): {', '.join(vals)}. Формат: {format_hint}")
        
        dims_str = "\n".join(dims_desc)
        
        example_classifications = {}
        for dim in dimensions:
            if dim.is_multi_value:
                example_classifications[dim.id] = ["код1", "код2"]
            else:
                example_classifications[dim.id] = "код_или_null"
        
        example_json = json.dumps(example_classifications, ensure_ascii=False, indent=2)
        
        return f"""Ты — строгий алгоритм классификации фармацевтических товаров.

СЛОВАРЬ МЕДИЦИНСКИХ АББРЕВИАТУР:
- таб. = таблетки
- р-р = раствор
- вн = внутрь / перорально / энтеральный (ОЧЕНЬ ЧАСТО ВСТРЕЧАЕТСЯ!)
- в/в = внутривенно / парентеральное
- д/ин = для инъекций / парентеральное
- д/инг = для ингаляций / ингаляционное
- наруж = наружное
- назал = назальный (в нос)
- мазь = мазь
- гель = гель
- крем = крем
- фл. = флакон
- амп. = ампула

СПРАВОЧНИКИ:
{dims_str}

ТОВАР:
Код: {product.code}
Текст: {product.text}

АЛГОРИТМ КЛАССИФИКАЦИИ:

ШАГ 1: ПОЛНЫЙ АНАЛИЗ ТЕКСТА
Найди ВСЕ ключевые слова и аббревиатуры в тексте.

ШАГ 2: РАСШИФРОВКА
Расшифруй все найденные слова.

ШАГ 3: ПРОВЕРКА ПО СПРАВОЧНИКУ И РАНЖИРОВАНИЕ
Для каждого расшифрованного значения проверь справочник.
ВАЖНО: Если найдено НЕСКОЛЬКО подходящих значений для одного измерения (например, комбинированный препарат с ДВУМЯ МНН), РАНЖИРУЙ их по точности:
- Основной код = первое по упоминанию в тексте ИЛИ основное действующее вещество (обычно с большей дозировкой)
- В reasoning объясни, почему выбрал именно этот код
ВАЖНО: Назальный относится к способу применения Наружное

ШАГ 4: ФОРМИРОВАНИЕ ОТВЕТА
Для измерений с форматом "ОДИН код" верни ТОЛЬКО самый точный код.
Для измерений с форматом "МАССИВ кодов" верни ВСЕ найденные коды.

ФОРМАТ ОТВЕТА (СТРОГО JSON-ОБЪЕКТ):
{{
  "code": {product.code},
  "reasoning": "ШАГ 1: Найдены слова: 'Ацетилсалиц', 'аскорб'. ШАГ 2: Расшифровка: 'Ацетилсалициловая кислота', 'Витамин С'. ШАГ 3: Проверка справочника: оба есть (коды 000000266, 000000267). Ранжирование: 'Ацетилсалициловая кислота' — основное действующее вещество (первое по упоминанию), выбираю код 000000266.",
  "classifications": {example_json}
}}
"""

    def clean_and_validate_classifications(
        self,
        raw_classifications: dict, 
        reasoning: str,
        dimensions: List[ClassificationDimension]
    ) -> Dict[str, Optional[str]]:
        """Очищает ответ от мусора (строк 'null') и жестко валидирует коды."""
        validated = {}
        
        # Словарь валидных кодов
        valid_codes_map = {
            dim.id: {val.code for val in dim.allowed_values} 
            for dim in dimensions
        }
        
        reasoning_lower = reasoning.lower() if reasoning else ""
    
        for dim in dimensions:
            returned_value = raw_classifications.get(dim.id)
            
            # Собираем валидные коды
            found_codes = []
            
            if isinstance(returned_value, list):
                for item in returned_value:
                    if isinstance(item, str) and item.lower() not in ['null', 'none', '']:
                        if item in valid_codes_map[dim.id]:
                            found_codes.append(item)
            elif isinstance(returned_value, str):
                if returned_value.lower() not in ['null', 'none', '']:
                    if returned_value in valid_codes_map[dim.id]:
                        found_codes.append(returned_value)
                        
            # Проверка на галлюцинации в reasoning
            if found_codes:
                not_found_patterns = [
                    f"{dim.name.lower()} не найден",
                    f"{dim.name.lower()} нет в справочнике",
                    "нет точного совпадения",
                    "не найдено в справочнике"
                ]
                
                for pattern in not_found_patterns:
                    if pattern in reasoning_lower:
                        found_codes = []
                        break
            
            # Формируем основное значение по правилам is_multi_value
            if dim.is_multi_value:
                validated[dim.id] = found_codes 
            else:
                # Для single-value берем первый найденный код (модель уже отранжировала)
                validated[dim.id] = found_codes[0] if found_codes else None

        return validated

    def normalize_dosage_string(self, text: str) -> str:
        """
        Агрессивная нормализация строки дозировки.
        Убирает всё, что не влияет на смысл дозировки.
        """
        if not text:
            return ""
        
        # 1. Приводим к нижнему регистру
        text = text.lower().strip()
        
        # 2. Унифицируем десятичные разделители
        text = text.replace(',', '.')
        
        # 3. Убираем ВСЕ пробелы (в дозировках они не важны)
        text = re.sub(r'\s+', '', text)
        
        # 4. Убираем невидимые символы
        text = re.sub(r'[\u200b\u00a0]', '', text)
        
        return text

    def find_best_dosage_match(self, extracted_dosage: str, dimension: ClassificationDimension):
        """Ищет наилучшее совпадение извлеченной дозировки в справочнике."""
        if not extracted_dosage:
            return None

        query = extracted_dosage.lower().strip()
        dict_choices = [item.values[0].lower() for item in dimension.allowed_values]

        # Используем ratio для более строгого поиска
        best_match = process.extractOne(
            query,
            dict_choices,
            scorer=fuzz.ratio,
            score_cutoff=85 # Высокий порог для точности
        )

        if best_match:
            matched_text, score, index = best_match
            logger.info(f"Dosage match: '{query}' -> '{matched_text}' (Score: {score})")
            return dimension.allowed_values[index].code

        return None

    async def process_single_dosage(self, product: ProductItem, dimensions: List[ClassificationDimension]):
        # ШАГ 1: Запрос к LLM на извлечение
        messages = [
            {'role': 'system', 'content': self._DOSAGE_EXTRACTION_PROMPT},
            {'role': 'user', 'content': product.text}
        ]

        response = await self._client.chat(
            model=settings.ANALYST_LLM_MODEL,
            messages=messages,
            format='json',
            options={'temperature': 0.0, 'num_ctx': 8192}
        )

        raw_json = response['message']['content']
        logger.info(raw_json)
        parsed_data = json.loads(raw_json)

        extracted_dosage = parsed_data.get('extracted_dosage', '')
        reasoning = parsed_data.get('reasoning', '')

        # ШАГ 2: Матчинг
        matched_code = self.find_best_dosage_match(extracted_dosage, dimensions)
        return {
            'code': product.code,
            'dosage': matched_code,
            'reasoning': reasoning
        }

    async def process_single_product(self, product: ProductItem, _dimensions: List[ClassificationDimension], is_request_doza: bool) -> dict:
        """Обрабатывает ОДИН товар через Ollama."""
        dimensions = list(_dimensions)

        # Если есть дозировки в запросе - обработаем их отдельно
        only_doza = False
        if is_request_doza:
            if len(dimensions) == 1:
                only_doza = True
            dimension_doza = [dimensions.pop(dimensions.index(dimension)) for dimension in dimensions if dimension.id == DIM_DOS]
        
        async with self._semaphore:
            try:
                if not only_doza:
                    prompt = self.build_prompt(product, dimensions)

                    response = await self._client.chat(
                        model=settings.ANALYST_LLM_MODEL,
                        messages=[{'role': 'user', 'content': prompt}],
                        format='json',
                        options={'temperature': 0.1, 'num_ctx': 80000}
                    )
                    
                    raw_json = response['message']['content']
                    logger.info(raw_json)
                    parsed_data = json.loads(raw_json)
                    
                    reasoning = parsed_data.get('reasoning')
                    raw_classifications = parsed_data.get('classifications', {})
                    
                    # Передаем reasoning для проверки логики
                    final_classifications = self.clean_and_validate_classifications(
                        raw_classifications, 
                        reasoning,
                        dimensions
                    )

                if is_request_doza:
                    doza_classification = await self.process_single_dosage(product, dimension_doza[0])

                    if only_doza:
                        return{
                            "code": product.code,
                            "reasoning": doza_classification['reasoning'],
                            "classifications": {
                                DIM_DOS: doza_classification['dosage']
                            } 
                        }

                reasoning = f'{reasoning} {doza_classification['reasoning']}'
                final_classifications[DIM_DOS] = doza_classification['dosage']
                
                return {
                    "code": product.code,
                    "reasoning": reasoning,
                    "classifications": final_classifications
                }

            except Exception as e:
                logger.error(f"Error processing {product.code}: {e}")
                classifications = {dim.id: [] if dim.is_multi_value else None for dim in dimensions}
                if is_request_doza:
                    classifications[DIM_DOS] = None
                return {
                    "code": product.code, 
                    "reasoning": f"Ошибка обработки: {e}",
                    "classifications": classifications
                }

    async def process(self, request: ClassifyRequest):
        # Проверим есть запрос классификации дозировок в запросе
        is_request_doza = False
        dimensions = request.dimensions
        for dimension in dimensions:
            if dimension.id == DIM_DOS:
                is_request_doza = True
        logger.info(f'Request dosage: {is_request_doza}')

        tasks = [self.process_single_product(product, request.dimensions, is_request_doza) for product in request.products]
        results = await asyncio.gather(*tasks)

        return ClassifyResponse(results=list(results))


class LLMClassifyreDoza:
    def __init__(self):
        self._client = ollama.AsyncClient(host=settings.ANALYST_OLLAMA_HOST)
        self._semaphore = asyncio.Semaphore(settings.OLLAMA_CONCURRENCY_LIMIT)

    def normalize_text(self, text: str) -> str:
        text = text.strip().lower()
        text = text.replace(',', '.') # Стандартизация десятичных разделителей
        text = re.sub(r'\s+', ' ', text) # Убираем множественные пробелы
        return text

    def classify_by_regex(self, text: str) -> Optional[str]:
        """Возвращает название группы, если строка подходит под паттерн, иначе None."""
        t = text.lower()
        
        # 1. Комбинированная (содержит '+')
        if '+' in t:
            return "Комбинированная дозировка"
        
        # 2. Международные единицы
        if re.search(r'(ме|ед\.|международных|анти-ха)', t):
            return "Международные единицы (МЕ)"
        
        # 3. Дозировка на дозу/впрыск
        if re.search(r'/доз', t):
            return "Дозировка на дозу/впрыск"
        
        # 4. Процентный раствор
        if '%' in t:
            return "Процентный раствор (%)"
        
        # 5. Концентрация (мг/мл, г/л и т.д.)
        if re.search(r'(мг|мкг|г)\s*/\s*(мл|л)', t):
            return "Концентрация (мг/мл, г/л)"
        
        # 6. Чистый объем
        if re.match(r'^\d+(\.\d+)?\s*(мл|л)$', t):
            return "Объем (мл, л)"
        
        # 7. Чистая масса
        if re.match(r'^\d+(\.\d+)?\s*(мг|г|мкг)$', t):
            return "Масса (мг, г, мкг)"
        
        # Если ничего не подошло, отдаем на суд LLM
        return None

    def build_prompt(self, chunk: List[str]) -> str:
        items_str = "\n".join([f"- \"{item}\"" for item in chunk])
        return f"""Ты — строгий эксперт по нормализации фармацевтических данных.
Тебе дан список строк, которые не удалось классифицировать простыми правилами.
Твоя задача: определить, является ли строка дозировкой, и если да, то к какой группе она относится.

ДОПУСТИМЫЕ ГРУППЫ (выбери строго одну):
1. "Масса (мг, г, мкг)" - например: "1.45г", "225мг", "1г N5" (N5 - упаковка, 1г - масса)
2. "Объем (мл, л)" - например: "2500 мл"
3. "Концентрация (мг/мл, г/л)" - например: "100мг/мл", "100мг/5мл-20.925г"
4. "Процентный раствор (%)" - например: "1.5%", "2%-120мл"
5. "Комбинированная дозировка" - несколько активных веществ
6. "Дозировка на дозу/впрыск" - например: "0.255мг/доза", "35мкг/доза"
7. "Международные единицы (МЕ)" - например: "10000МЕ", "3млн.МЕ"
8. "Мусор / Не дозировка" - например: "ампулы 10 шт", "4.0", "0,65", "104 30гр" (если похоже на ошибку OCR)

Верни ТОЛЬКО валидный JSON-массив объектов:
[
  {{
    "text": "исходная строка",
    "group": "Название группы из списка выше",
    "is_garbage": true/false,
    "comment": "Краткое пояснение (1-2 слова)"
  }}
]

Список для анализа:
{items_str}
"""

    def normalize_dosage_response(self, parsed_data: any) -> list:
        """
        Универсальная нормализация ответа LLM к формату списка словарей.
        Обрабатывает все капризы локальных моделей:
        - Сразу список
        - Объект с ключом items/results/data
        - Словарь, где ключи - это тексты
        """
        # 1. Если это уже список - отлично
        if isinstance(parsed_data, list):
            return parsed_data
            
        elif isinstance(parsed_data, dict):
            # 2. Ищем стандартные ключи-обертки
            for key in ['items', 'results', 'data', 'dosages', 'products']:
                if key in parsed_data and isinstance(parsed_data[key], list):
                    logger.info(f"Found wrapper key: '{key}'")
                    return parsed_data[key]
                    
            # 3. Универсальный поиск: ищем любой ключ, значением которого является список словарей
            for key, value in parsed_data.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    logger.info(f"Found list in key: '{key}'")
                    return value
                    
            # 4. Модель вернула словарь, где ключи - это сами тексты
            # Например: {"100мг/5мл": {"group": "...", ...}, "20 млрд.": {...}}
            normalized = []
            for text_key, item_data in parsed_data.items():
                if isinstance(item_data, dict):
                    # Если внутри нет поля text, добавляем его из ключа
                    if 'text' not in item_data:
                        item_data = {**item_data, 'text': text_key}
                    normalized.append(item_data)
            if normalized:
                return normalized
                
            logger.error(f"Could not normalize dict: {list(parsed_data.keys())}")
            return []
            
        else:
            logger.error(f"Unexpected parsed_data type: {type(parsed_data)}")
            return []

    async def process_llm_chunk(self, chunk: List[str]) -> List[dict]:
        try:
            prompt = self.build_prompt(chunk)

            response = await self._client.chat(
                model=settings.ANALYST_LLM_MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                format='json',
                options={'temperature': 0.0, 'num_ctx': 4096}
            )
            raw_json = response['message']['content']
            # logger.info(raw_json)
            parsed_data = json.loads(raw_json)

            normalized_items = self.normalize_dosage_response(parsed_data)
        
            if not normalized_items:
                logger.warning("Normalization returned empty list, returning fallback")
                return [
                    {"text": item, "group": "Требует ручной проверки", "is_garbage": False, "comment": "Не удалось распарсить ответ LLM"} 
                    for item in chunk
                ]
            
            # Теперь normalized_items - гарантированно список словарей
            # Дополнительно убеждаемся, что у каждого элемента есть обязательные поля
            validated_items = []
            for item in normalized_items:
                if isinstance(item, dict) and 'text' in item:
                    # Убеждаемся, что все поля на месте (страховка от галлюцинаций модели)
                    item.setdefault('group', 'Не определено')
                    item.setdefault('is_garbage', False)
                    item.setdefault('comment', '')
                    validated_items.append(item)
            
            return validated_items
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e}")
            return [
                {"text": item, "group": "Требует ручной проверки", "is_garbage": False, "comment": f"JSON error: {e}"} 
                for item in chunk
            ]
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return [
                {"text": item, "group": "Требует ручной проверки", "is_garbage": False, "comment": str(e)} 
                for item in chunk
            ]

    async def process(self, request: DosageCleanRequest):
        results = []
        # groups_summary = {}
        garbage_count = 0
        llm_chunk = []

        # 1. Первичная обработка Regex
        for dosage in request.dosages:
            norm_text = self.normalize_text(dosage)
            group = self.classify_by_regex(norm_text)
            
            if group:
                # Успешно классифицировано Python
                is_garbage = False
                comment = "Классифицировано Regex"
            else:
                # Сложный случай, отправляем в батч для LLM
                llm_chunk.append(norm_text)
                continue # Обработаем ниже
                
            # results.append({
            #     "original_text": dosage,
            #     "normalized_text": norm_text,
            #     "group": group,
            #     "is_garbage": is_garbage,
            #     "comment": comment
            # })

            results.append(
                DosageItem(
                    original_text=dosage,
                    normalized_text=norm_text,
                    group=group,
                    is_garbage=is_garbage,
                    comment=comment
                )
            )
            # groups_summary[group] = groups_summary.get(group, 0) + 1

        # 2. Обработка сложных случаев через LLM (батчами по 30 штук)
        if llm_chunk:
            batch_size = 30
            batches = [llm_chunk[i:i + batch_size] for i in range(0, len(llm_chunk), batch_size)]
            
            tasks = [self.process_llm_chunk(batch) for batch in batches]
            llm_responses = await asyncio.gather(*tasks)
            
            # Собираем результаты LLM
            # Создаем маппинг для быстрого поиска, так как порядок может быть важен
            llm_results_map = {}
            for batch_res in llm_responses:
                for item in batch_res:
                    llm_results_map[item['text']] = item
                    
            for dosage in request.dosages:
                norm_text = self.normalize_text(dosage)
                if norm_text in llm_results_map:
                    llm_data = llm_results_map[norm_text]
                    is_garbage = llm_data.get('is_garbage', False)
                    group = llm_data.get('group', 'Не определено')
                    
                    # results.append({
                    #     "original_text": dosage,
                    #     "normalized_text": norm_text,
                    #     "group": group,
                    #     "is_garbage": is_garbage,
                    #     "comment": llm_data.get('comment', '')
                    # })

                    results.append(
                        DosageItem(
                            original_text=dosage,
                            normalized_text=norm_text,
                            group=group,
                            is_garbage=is_garbage,
                            comment=llm_data.get('comment', '')
                        )
                    )
                    
                    if is_garbage:
                        garbage_count += 1
                    # groups_summary[group] = groups_summary.get(group, 0) + 1

        return DosageCleanResponse(
            total_items=len(request.dosages),
            garbage_count=garbage_count,
            # groups_summary=groups_summary,
            results=results
        )


class LLMClassifierMNN:
    _SYSTEM_PROMPT = """Ты — строгий фармацевтический алгоритм. 
Твоя задача — извлечь из текста товара МНН (международные непатентованные наименования) и расшифровать все медицинские аббревиатуры.

ПРАВИЛА:
1. Расшифровывай сокращения (например: "Ацетилсалиц.к-та" -> "Ацетилсалициловая кислота", "аскорб.к-та" -> "Аскорбиновая кислота", "р-р" игнорируй, это форма выпуска).
2. Если в тексте несколько действующих веществ, перечисли их все.
3. Если МНН не найдено, верни пустой список.
4. Верни ТОЛЬКО валидный JSON.

ФОРМАТ ОТВЕТА:
{
  "extracted_mnn": ["Название вещества 1", "Название вещества 2"],
  "reasoning": "Краткое пояснение: какие слова нашел и как расшифровал."
}
"""
    def __init__(self):
        self._client = ollama.AsyncClient(host=settings.ANALYST_OLLAMA_HOST)
        self._semaphore = asyncio.Semaphore(settings.OLLAMA_CONCURRENCY_LIMIT)

    def find_best_mnn_match(self, extracted_mnn: List[str], dictionary: List[MNNDictionaryItem]) -> Optional[str]:
        """Ищет наилучшее совпадение извлеченных МНН в справочнике"""
        if not extracted_mnn:
            return None

        # Нормализуем извлеченные МНН (lowercase, strip)
        normalized_extracted = [mnn.lower().strip() for mnn in extracted_mnn]
        
        # Если одно МНН - ищем точное совпадение через RapidFuzz
        if len(normalized_extracted) == 1:
            query = normalized_extracted[0]
            dict_choices = [item.value.lower() for item in dictionary]
            
            best_match = process.extractOne(
                query, 
                dict_choices, 
                scorer=fuzz.token_set_ratio,
                score_cutoff=80  # Высокий порог для точности
            )
            
            if best_match:
                _, score, index = best_match
                logger.info(f"Single MNN match: '{query}' -> '{dictionary[index].value}' (Score: {score})")
                return dictionary[index].code
            return None
        
        # Если несколько МНН - ищем запись, содержащую ВСЕ из них
        logger.info(f"Searching for combination: {normalized_extracted}")
        
        for item in dictionary:
            dict_value = item.value.lower()
            
            # Проверяем, все ли извлеченные МНН содержатся в этой записи
            all_contained = all(extracted in dict_value for extracted in normalized_extracted)
            
            if all_contained:
                logger.info(f"Found combination match: '{item.value}'")
                return item.code
        
        # Если не нашли запись со всеми МНН - возвращаем null
        logger.warning(f"No combination found for: {normalized_extracted}")
        return None

    async def process_single_mnn(self, product: MNNProductItem, dictionary: List[MNNDictionaryItem]) -> MNNClassifyResult:
        try:
            # ШАГ 1: Запрос к LLM на извлечение (без справочника!)
            messages = [
                {'role': 'system', 'content': self._SYSTEM_PROMPT},
                {'role': 'user', 'content': product.text}
            ]
            response = await self._client.chat(
                model=settings.ANALYST_LLM_MODEL,
                messages=messages,
                format='json',
                options={'temperature': 0.0, 'num_ctx': 2048}
            )
            raw_json = response['message']['content']
            logger.info(raw_json)
            parsed_data = json.loads(raw_json)

            extracted_mnn = parsed_data.get('extracted_mnn', [])
            reasoning = parsed_data.get('reasoning', '')

            # ШАГ 2: Матчинг в Python (предположительно должен занимать < 10 миллисекунд на 2800 записей)
            matched_code = self.find_best_mnn_match(extracted_mnn, dictionary)

            return MNNClassifyResult(
                code=product.code,
                mnn_code=matched_code,
                reasoning=reasoning
            )

        except Exception as e:
            logger.error(f"Error processing MNN for {product.code}: {e}")
        return MNNClassifyResult(code=product.code, mnn_code=None, reasoning=f"Error: {str(e)}")

    async def process(self, request: MNNClassifyRequest) -> MNNClassifyResponse:
        """Классифицирует МНН товаров, используя LLM для извлечения и Python для поиска в огромном справочнике."""
        tasks = [self.process_single_mnn(product, request.dictionary) for product in request.products]
        results = await asyncio.gather(*tasks)
        return MNNClassifyResponse(results=list(results))


class LLMClassExtractor:
    def __init__(self):
        self._client = ollama.AsyncClient(host=settings.ANALYST_OLLAMA_HOST)
        self._semaphore = asyncio.Semaphore(settings.OLLAMA_CONCURRENCY_LIMIT)

    def build_system_prompt(self, categories: List[CategorySchema]) -> str:
        """Формирует системный промпт со списком категорий и свойств."""
        categories_desc = []
        for cat in categories:
            props = ', '.join(cat.properties)
            categories_desc.append(f"- Категория: '{cat.name}'. Свойства: [{props}]")
        categories_str = '\n'.join(categories_desc)

        return f"""
Ты — строгая система классификации и извлечения атрибутов товаров.
Тебе доступен следующий справочник категорий и их свойств:
{categories_str}

Твоя задача:
1. Проанализировать текст товара и определить, к какой ОДНОЙ из предложенных категорий он относится.
2. Если текст не подходит ни к одной категории, верни "category": null.
3. Если категория определена, извлеки из текста ТОЛЬКО те свойства, которые указаны для этой категории.
4. Если какое-то свойство не найдено в тексте, не включай его в массив extracted_properties.
5. Оцени свою уверенность в выборе категории (confidence) числом от 0.0 до 1.0.

Правила формирования JSON:
- Поле 'id' должно в точности совпадать с переданным идентификатором.
- Поле 'category' - строка с названием категории или null.
- Поле 'confidence' - число (float).
- Поле 'extracted_properties' - массив объектов. Каждый объект имеет 'property_name' (строка) и 'value' (строка, число или массив строк).
- Поле 'error' - null (если нет ошибок).
- Верни ТОЛЬКО валидный JSON. Никаких пояснений, markdown-оберток или текста до/после JSON.
"""

    async def process_single_item(self, item: TextItem, system_prompt: str) -> SingleTextResult:
        """Обрабатывает один текст через Ollama с учетом семафора."""
        async with self._semaphore:
            try:
                user_prompt = f"ID товара: {item.id}\nТекст товара: {item.text}"
                messages = [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ]

                response = await self._client.chat(
                    model=settings.ANALYST_LLM_MODEL,
                    messages=messages,
                    format='json',
                    options={'temperature': 0.1, 'num_ctx': 8192}
                )

                parsed_data = json.loads(response['message']['content'].strip())

                # Страховка: жестко подставляем правильный ID, чтобы модель не напутала
                parsed_data['id'] = item.id 
                parsed_data['error'] = None

                return SingleTextResult(**parsed_data)
            
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON for id {item.id}")
                return SingleTextResult(id=item.id, error="LLM returned invalid JSON")
            except Exception as e:
                logger.error(f"Error processing id {item.id}: {e}")
                return SingleTextResult(id=item.id, error=str(e))

    async def process(self, request: ClassifyAndExtractRequest):
        """Классифицирует список товаров по категориям и извлекает их свойства."""
        # Формируем системный промпт ОДИН раз на весь батч (экономия токенов)
        system_prompt = self.build_system_prompt(request.categories)

        # Создаем асинхронные задачи для каждого текста
        tasks = [self.process_single_item(item, system_prompt) for item in request.items]

        # Запускаем все задачи параллельно (с учетом семафора)
        results = await asyncio.gather(*tasks)

        return ClassifyAndExtractResponse(status='success', results=list(results))


class LLMExtractor:
    _SYSTEM_PROMPT = """
    Ты — строгая система извлечения структурированных данных из текста. 
    Твоя задача — проанализировать текст и извлечь следующие поля:
    - name (строка): Торговое наименование
    - brand (строка): Бренд
    - type (список строк): Список типов продукта
    - taste (список строк): Список вкусов
    - color (список строк): Список цветов
    - aroma (список строк): Список ароматов
    - effect (список строк): Список эффектов
    - result (список строк): Список результатов
    - component (список строк): Список компонентов (состав)
    - hardness (список строк): Список значений жесткости
    - feature (список строк): Список особенностей

    Правила:
    1. Если поле не найдено в тексте, верни для него пустую строку (для строк) или пустой список (для списков). Не выдумывай данные.
    2. Разбивай сложные эффекты и результаты на отдельные пункты списка.
    3. В поле 'компонент' включай все ингредиенты из состава.
    4. Верни ТОЛЬКО валидный JSON. Никаких пояснений, текста до или после JSON, никаких markdown-оберток.
    """
    
    def __init__(self):
        self._client = ollama.AsyncClient(host=settings.ANALYST_OLLAMA_HOST)

    async def extract(self, request: ExtractRequest) -> ExtractData | None:
        messages = [
            {'role': 'system', 'content': self._SYSTEM_PROMPT},
            {'role': 'user', 'content': request.text}
        ]

        try:
            response = await self._client.chat(
                model=settings.ANALYST_LLM_MODEL,
                messages=messages,
                format='json',
                options={'temperature': 0.1, 'num_ctx': 8192}
            )
            parsed = json.loads(response['message']['content'].strip())
            print(parsed)
            validated_data = ExtractData(**parsed)
            return validated_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM: {e}")
            return None
        except Exception as e:
            logger.error(f"Error during extraction: {e}")
            return None
