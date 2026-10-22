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
            dims_desc.append(f"{dim.name} ({dim.id}): {', '.join(vals)}")
        
        dims_str = "\n".join(dims_desc)
        
        return f"""Ты — строгий алгоритм классификации фармацевтических товаров.
    Расшифровывай медицинские аббревиатуры (таб.=таблетки, вн=энтеральный/внутрь, д/ин=парентеральное/инъекции, наруж=наружное, назал=назальный и т.д.).

СПРАВОЧНИКИ:
{dims_str}

ТОВАР:
Код: {product.code}
Текст: {product.text}

ЗАДАЧА:
1. СНАЧАЛА напиши краткое рассуждение в поле "reasoning": какие слова/аббревиатуры ты нашла и как их расшифровала.
2. ЗАТЕМ определи значения для каждого измерения.
3. Если расшифрованное слово ЕСТЬ в справочнике — верни его КОД.
4. Если слова НЕТ в справочнике (например, "назал", а в справочнике нет назального) — верни СТРОГО null. Не подбирай похожие значения!

ФОРМАТ ОТВЕТА (СТРОГО JSON-ОБЪЕКТ):
{{
  "code": {product.code},
  "reasoning": "Найдены слова: 'таб.' (таблетки), 'вн' (внутрь/энтеральный). 'Таблетки' есть в справочнике форм (код 000000001). 'Энтеральный' есть в справочнике способов (код 000000001).",
  "classifications": {{
    "{dimensions[0].id}": "код_или_null",
    "{dimensions[1].id}": "код_или_null"
  }}
}}
"""

    def clean_and_validate_classifications(
        self,
        raw_classifications: dict, 
        dimensions: List[ClassificationDimension]
    ) -> Dict[str, Optional[str]]:
        """Очищает ответ от мусора (строк 'null') и жестко валидирует коды."""
        validated = {}
        
        # Словарь валидных кодов
        valid_codes_map = {
            dim.id: {val.code for val in dim.allowed_values} 
            for dim in dimensions
        }
        
        for dim in dimensions:
            returned_value = raw_classifications.get(dim.id)
            
            # 1. Очистка от строкового "null" или "None"
            if isinstance(returned_value, str) and returned_value.lower() in ['null', 'none', '']:
                returned_value = None
                
            # 2. Жесткая проверка кода
            if returned_value in valid_codes_map[dim.id]:
                validated[dim.id] = returned_value
            else:
                # Если это не валидный код и не None, принудительно ставим None
                validated[dim.id] = None
                
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
                logger.debug(f"Raw JSON for {product.code}: {raw_json}")
                
                parsed_data = json.loads(raw_json)
                
                # Достаем рассуждения (если модель их вернула)
                reasoning = parsed_data.get('reasoning')
                raw_classifications = parsed_data.get('classifications', {})
                
                # Жесткая валидация кодов
                final_classifications = self.clean_and_validate_classifications(raw_classifications, dimensions)
                
                return {
                    "code": product.code,
                    "reasoning": reasoning,
                    "classifications": final_classifications
                }

            except json.JSONDecodeError as e:
                logger.error(f"JSON Decode Error for {product.code}: {e}")
                return {
                    "code": product.code, 
                    "reasoning": f"Ошибка парсинга JSON: {e}",
                    "classifications": {dim.id: None for dim in dimensions}
                }
            except Exception as e:
                logger.error(f"Error processing {product.code}: {e}")
                return {
                    "code": product.code, 
                    "reasoning": f"Ошибка обработки: {e}",
                    "classifications": {dim.id: None for dim in dimensions}
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
