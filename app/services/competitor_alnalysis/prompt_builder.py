import json
from app.utils.decimal_encoder import DecimalEncoder


class PromptBuilder:
    def build(self, context: dict) -> str:
        return f"""
Ты аналитик фармацевтического ритейла.

Твоя задача — проанализировать данные мониторинга цен конкурентов.

Данные:

ГОРОДА:
{json.dumps(context['cities'], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

КОНКУРЕНТЫ:
{json.dumps(context['competitors'], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

Сделай:

1. Классификацию городов по уровню цен
2. Анализ конкурентов (кто дешевый, кто дорогой)
3. Где наши аптеки дают наибольшую скидку
4. Выяви аномалии
5. Дай 3-5 практических рекомендаций

Формат:
- структурированный текст
- без воды
- с конкретикой
"""
