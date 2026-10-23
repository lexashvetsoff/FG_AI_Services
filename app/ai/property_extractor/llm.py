import json
import ollama
import logging
import asyncio
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
    ProductItem
)


CHUNK_SIZE = 10
logger = logging.getLogger(__name__)


class LLMClassifier:
    def __init__(self):
        self._client = ollama.AsyncClient(host=settings.PARSER_OLLAMA_HOST)
        self._semaphore = asyncio.Semaphore(settings.OLLAMA_CONCURRENCY_LIMIT)

    def build_prompt(self, product: ProductItem, dimensions: List[ClassificationDimension]) -> str:
        dims_desc = []
        for dim in dimensions:
            vals = []
            for v in dim.allowed_values:
                vals.append(f"{v.code}=[{', '.join(v.values)}]")
            
            format_hint = "верни МАССИВ кодов (даже если один)" if dim.is_multi_value else "верни ОДИН код (строку) или null"
            dims_desc.append(f"{dim.name} ({dim.id}): {', '.join(vals)}. Формат: {format_hint}")
        
        dims_str = "\n".join(dims_desc)
        
        return f"""Ты — строгий алгоритм классификации фармацевтических товаров.

ПРАВИЛА РАСШИФРОВКИ АББРЕВИАТУР:
- таб. = таблетки
- р-р = раствор (жидкая форма)
- вн = внутрь / перорально / энтеральный (НЕ внутривенно!)
- в/в = внутривенно / парентеральное
- д/ин = для инъекций / парентеральное
- д/инг = для ингаляций / ингаляционное
- наруж = наружное
- назал = назальный (в нос)

СПРАВОЧНИКИ:
{dims_str}

ТОВАР:
Код: {product.code}
Текст: {product.text}

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:
1. СНАЧАЛА напиши рассуждение в поле "reasoning": какие слова нашел и как их расшифровал.
2. ЗАТЕМ проверь: есть ли расшифрованное слово в справочнике?
3. ЕСЛИ СЛОВА НЕТ В СПРАВОЧНИКЕ — верни СТРОГО null (или пустой массив []).
   ПРИМЕР ПЛОХОЙ ЛОГИКИ: "раствор не найден в справочнике, но подойдет код таблеток" — ТАК ДЕЛАТЬ НЕЛЬЗЯ!
   ПРИМЕР ХОРОШЕЙ ЛОГИКИ: "раствор не найден в справочнике форм, возвращаю null".
4. НЕ ПЫТАЙСЯ подобрать похожие значения! Если слова нет — только null.
5. "вн" = ЭНТЕРАЛЬНЫЙ (внутрь), а НЕ внутривенно!

ФОРМАТ ОТВЕТА (СТРОГО JSON-ОБЪЕКТ):
{{
  "code": {product.code},
  "reasoning": "Найдены слова: 'р-р' (раствор), 'вн' (внутрь/энтеральный), 'д/инг' (ингаляции). Раствор не найден в справочнике форм -> null. Энтеральный есть (код 000000001). Ингаляционное есть (код 000000003).",
  "classifications": {{
    "{dimensions[0].id}": null,
    "{dimensions[1].id}": ["000000001", "000000003"]
  }}
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
        
        # Нормализуем reasoning для поиска
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
                        
            # КЛЮЧЕВАЯ ПРОВЕРКА: если в reasoning написано "не найден" или "нет в справочнике",
            # но модель вернула код — принудительно заменяем на null
            if found_codes:
                # Ищем паттерны, указывающие на отсутствие значения
                not_found_patterns = [
                    f"{dim.name.lower()} не найден",
                    f"{dim.name.lower()} нет в справочнике",
                    f"нет точного совпадения",
                    "не найдено в справочнике",
                    "нет подходящего"
                ]
                
                for pattern in not_found_patterns:
                    if pattern in reasoning_lower:
                        # Модель сама написала, что не нашла, но вернула код — это галлюцинация
                        found_codes = []
                        break
            
            # Формируем итоговое значение
            if dim.is_multi_value:
                validated[dim.id] = found_codes 
            else:
                validated[dim.id] = found_codes[0] if found_codes else None

        return validated

    async def process_single_product(self, product: ProductItem, dimensions: List[ClassificationDimension]) -> dict:
        """Обрабатывает ОДИН товар через Ollama."""
        async with self._semaphore:
            prompt = self.build_prompt(product, dimensions)
            
            try:
                response = await self._client.chat(
                    model=settings.PARSER_LLM_MODEL,
                    messages=[{'role': 'user', 'content': prompt}],
                    format='json',
                    options={'temperature': 0.1, 'num_ctx': 8192}
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
                
                return {
                    "code": product.code,
                    "reasoning": reasoning,
                    "classifications": final_classifications
                }

            except Exception as e:
                logger.error(f"Error processing {product.code}: {e}")
                return {
                    "code": product.code, 
                    "reasoning": f"Ошибка обработки: {e}",
                    "classifications": {dim.id: [] if dim.is_multi_value else None for dim in dimensions}
                }

    async def process(self, request: ClassifyRequest):
            tasks = [self.process_single_product(product, request.dimensions) for product in request.products]
            results = await asyncio.gather(*tasks)
    
            return ClassifyResponse(results=list(results))


class LLMClassExtractor:
    def __init__(self):
        self._client = ollama.AsyncClient(host=settings.PARSER_OLLAMA_HOST)
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
                    model=settings.PARSER_LLM_MODEL,
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
        self._client = ollama.AsyncClient(host=settings.PARSER_OLLAMA_HOST)

    async def extract(self, request: ExtractRequest) -> ExtractData | None:
        messages = [
            {'role': 'system', 'content': self._SYSTEM_PROMPT},
            {'role': 'user', 'content': request.text}
        ]

        try:
            response = await self._client.chat(
                model=settings.PARSER_LLM_MODEL,
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
