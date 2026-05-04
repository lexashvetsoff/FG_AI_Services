import json
from app.utils.decimal_encoder import DecimalEncoder


class PromptBuilder:
    def build(self, context: dict) -> str:
        return f"""
Ты аналитик фармацевтического ритейла.

Тебе даны агрегированные данные мониторинга цен.

Ты анализируешь сегмент: {context["segment"]}

ВАЖНО:
Анализ только внутри сегмента.

Данные:

=== ГОРОДА ===
{json.dumps(context['cities'], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

=== КОНКУРЕНТЫ ===
{json.dumps(context['competitors'], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

=== ТОВАРЫ (TOP по разбросу цен) ===
{json.dumps(context['products'], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

=== ЗАВЫШЕННЫЕ ТОВАРЫ ===
{json.dumps(context["overpriced"], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

=== НЕДООЦЕНЕННЫЕ ТОВАРЫ ===
{json.dumps(context["underpriced"], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

=== ВЫСОКИЙ РАЗБРОС ===
{json.dumps(context["high_variance"], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

=== ЛИДЕРЫ ПО ГОРОДАМ ===
{json.dumps(context["city_leaders"], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

Сделай отчет:

1. Общая ситуация по городам
2. Кто демпингует / кто дорогой
3. Где мы теряем деньги (недооценка)
4. Где мы проигрываем рынку (завышение)
5. Товары с нестабильным рынком
6. 5 конкретных действий:
   - изменить цену
   - пересмотреть стратегию
   - обратить внимание на товары

Формат:
- четко
- по пунктам
- с конкретными товарами и городами
"""
    
    def build_summary(self, segment_reports: list):
        return f"""
Ты аналитик фармацевтического ритейла.

У тебя есть отчеты по сегментам:

{json.dumps(segment_reports, ensure_ascii=False, indent=2)}

Сделай общий вывод:

1. Какие города проблемные
2. Общая стратегия цен
3. Где теряем деньги
4. 5 ключевых действий
"""
