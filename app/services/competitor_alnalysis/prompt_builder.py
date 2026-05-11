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

ФОРМАТИРОВАНИЕ:
- НЕ используй LaTeX ($...$)
- пиши обычный текст
- вместо avg_diff_pct → "средняя разница (%)"

Формат:
- четко
- по пунктам
- с конкретными товарами и городами
"""
    
    def build_segment_prompt(self, context: dict) -> str:
        return f"""
Ты аналитик фармацевтического ритейла.

====================
КОНТЕКСТ
====================

Сегмент: {context["segment"]}

ВАЖНО:
- our_pharmacy — наша аптека (ФГ)
- competitor_pharmacy — конкурент
- сравнение идет ПАРАМИ (это ключевая логика)

====================
АГРЕГИРОВАННЫЕ ДАННЫЕ (ОСНОВА АНАЛИЗА)
====================

{json.dumps(context["pair_summary"], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

====================
ГОТОВЫЕ ИНСАЙТЫ
====================

{json.dumps(context["insights"], ensure_ascii=False, indent=2, cls=DecimalEncoder)}

====================
ЗАДАЧА
====================

Сделай структурированный отчет:

1. Общая ситуация по сегменту
2. Основные конкуренты (ТОЛЬКО из данных)
3. Где мы проигрываем (overprice)
4. Где мы выигрываем (underprice)
5. Конкретные рекомендации по ценам

ЗАПРЕЩЕНО:
- выдумывать конкурентов
- путать наши аптеки и конкурентов
- делать выводы без данных

ФОРМАТИРОВАНИЕ:
- НЕ используй LaTeX ($...$)
- пиши обычный текст
- вместо avg_diff_pct → "средняя разница (%)"

ПИШИ:
- четко
- по делу
- с цифрами
"""
    
    def build_chat_prompt(self, question: str, context: dict) -> str:
        return f"""
Ты аналитик фармацевтического ритейла.

====================
ВАЖНО
====================

- "ФГ" — наши аптеки
- остальные — конкуренты
- данные сгруппированы по сегментам

====================
ДАННЫЕ
====================

{json.dumps(context, ensure_ascii=False, indent=2, cls=DecimalEncoder)}

====================
ВОПРОС
====================

{question}

====================
ПРАВИЛА
====================

- отвечай только по данным
- не выдумывай
- если данных нет — скажи
- используй конкретные цифры
- отвечай коротко, 2-3 предложения

====================
ВАЖНО
====================
ФОРМАТИРОВАНИЕ:
- НЕ используй LaTeX ($...$)
- пиши обычный текст
- вместо avg_diff_pct → "средняя разница (%)"

Ответ:
"""
    
    def build_sql_propmt(self, question: str, import_id: str) -> str:
        return f"""
Ты senior SQL analyst.
Пишешь SQL для PostgreSQL.

========================================
ГЛАВНЫЕ ПРАВИЛА
========================================

- Только SELECT
- Никаких INSERT/UPDATE/DELETE
- Всегда добавляй:

WHERE import_id = '{import_id}'

- Всегда LIMIT 50
- Используй только существующие таблицы и поля
- Не придумывай поля

========================================
БИЗНЕС-ЛОГИКА
========================================

НАШИ АПТЕКИ:
- is_our = true
- обычно начинаются с "ФГ"

КОНКУРЕНТЫ:
- is_our = false

ВАЖНО:
- product_name = название товара
- pharmacy_name = название сети аптек
- pharmacy_instance = название конкретной аптеки
- НИКОГДА не сравнивай:
    product_name = 'ФГ-...'
- НИКОГДА не используй pharmacy_name и pharmacy_instance как товар

========================================
ТАБЛИЦЫ
========================================

normalized_prices
-----------------
Сырые цены.

Поля:
- import_id
- city → город
- product_name → товар
- pharmacy_name → сеть
- pharmacy_instance → аптека
- is_our → наша аптека или нет
- price → цена
- price_segment → ценовой сегмент
- pair_id → ID пары "наша аптека ↔ конкурент"
- competitor_name → прямой конкурент

Использовать:
- поиск цен
- список товаров
- список аптек


========================================

pair_price_metrics
------------------

Главная таблица сравнения.

1 строка = сравнение:
НАША АПТЕКА ↔ КОНКУРЕНТ
по конкретному товару.

Поля:
- import_id
- city
- product_name
- price_segment
- pair_id
- our_pharmacy_name
- our_pharmacy_instance
- competitor_pharmacy_name
- competitor_pharmacy_instance
- our_price
- competitor_price
- diff_abs
- diff_pct
- status

status:
- cheaper
- expensive
- equal

Использовать:
- анализ завышения
- анализ демпинга
- сравнение сетей

========================================

competitor_metrics
------------------

Поля:
- import_id
- city
- pharmacy_name
- pharmacy_instance
- price_segment
- price_index
- category

category:
- cheap
- mid
- expensive

Использовать:
- поиск дешевых сетей
- поиск дорогих сетей
- рейтинг конкурентов

========================================

city_metrics
------------

Поля:
- import_id
- city
- price_segment
- avg_price
- price_dispersion
- avg_discount

Использовать:
- сравнение городов
- анализ скидок

========================================

product_metrics
---------------

Поля:
- import_id
- city
- product_name
- price_segment
- avg_price
- min_price
- max_price
- std_dev

Использовать:
- поиск аномалий
- дорогие товары
- нестабильные товары

========================================
ПРИМЕРЫ ПРАВИЛЬНЫХ ЗАПРОСОВ
========================================

Пример:
Какие конкуренты самые дешевые?

SELECT pharmacy_instance, price_index
FROM competitor_metrics
WHERE import_id = '{import_id}'
ORDER BY price_index ASC
LIMIT 20;

----------------------------------------

Пример:
Какие товары у нас дороже конкурентов?

SELECT
    product_name,
    our_price,
    competitor_price,
    diff_pct
FROM pair_price_metrics
WHERE import_id = '{import_id}'
  AND diff_pct > 10
ORDER BY diff_pct DESC
LIMIT 50;

----------------------------------------

Пример:
Почему цены ФГ- 86 и Дешевая аптека (ДА) почти одинаковые в сегменте 501-1000?

SELECT
	city,
	our_pharmacy_instance,
	competitor_pharmacy_instance,
	product_name,
	our_price,
	competitor_price,
	diff_abs,
	diff_pct
FROM pair_price_metrics
WHERE import_id = '{import_id}'
	AND price_segment = '501-1000'
    AND (
        -- Поиск записей, связанных с первой локацией ('ФГ- 86')
        our_pharmacy_name LIKE '%ФГ- 86%' OR our_pharmacy_instance LIKE '%ФГ- 86%'
    )
    AND (
        -- Поиск записей, связанных со второй локацией ('Дешевая аптека (ДА)')
        competitor_pharmacy_name LIKE '%Дешевая аптека (ДА)%' OR competitor_pharmacy_instance LIKE '%Дешевая аптека (ДА)%'
    )
LIMIT 50

========================================
ВОПРОС
========================================

{question}

Верни только SQL.
"""
    
    def build_answer_prompt(self, question: str, data: list) -> str:
        return f"""
Ты аналитик фармацевтического ритейла.

ВОПРОС:
{question}

ДАННЫЕ:
{json.dumps(data, ensure_ascii=False, indent=2, cls=DecimalEncoder)}

ФОРМАТИРОВАНИЕ:
- НЕ используй LaTeX ($...$)
- пиши обычный текст
- вместо avg_diff_pct → "средняя разница (%)"

Объясни:
- кратко
- по делу
- с выводами
"""
    
    def build_over_prompt(self, question: str) -> str:
        return f"""
Ты аналитик фармацевтического ритейла.

Проанализируй вопрос пользователя.

ВОПРОС:
{question}

Если он не имеет отношения к аналитике фармацевтики - мягко скажи об этом и направь диалог в аналитическое русло.
Иначе - задай уточняющие вопросы.

ФОРМАТИРОВАНИЕ:
- НЕ используй LaTeX ($...$)
- пиши обычный текст

Отвечай кратко и по делу
"""

    def build_summary(self, segment_reports: list):
        return f"""
Ты аналитик фармацевтического ритейла.

У тебя есть отчеты по сегментам:

{json.dumps(segment_reports, ensure_ascii=False, indent=2)}

ФОРМАТИРОВАНИЕ:
- НЕ используй LaTeX ($...$)
- пиши обычный текст
- вместо avg_diff_pct → "средняя разница (%)"

Сделай общий вывод:

1. Какие города проблемные
2. Общая стратегия цен
3. Где теряем деньги
4. 5 ключевых действий
"""
