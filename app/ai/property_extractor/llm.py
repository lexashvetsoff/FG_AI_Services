import json
import ollama
import logging
from app.config import settings
from app.schemas.schemas import ExtractRequest, ExtractData


logger = logging.getLogger(__name__)


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
