from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ContextBuilder:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def build(self, import_id: str):
        cities = await self._get_sity_metrics(import_id)
        competitors = await self._get_competitors(import_id)
        products = await self._get_product_menrics(import_id)
        overpriced = await self._get_overpriced_products(import_id)
        underpriced = await self._get_underpriced_product(import_id)
        high_variance = await self._get_high_variance_products(import_id)
        city_leaders = await self._get_city_leaders(import_id)

        return {
            'cities': cities,
            'competitors': competitors,
            'products': products,
            'overpriced': overpriced,
            'underpriced': underpriced,
            'high_variance': high_variance,
            'city_leaders': city_leaders
        }
    
    async def _get_sity_metrics(self, import_id: str):
        query = text("""
        SELECT city, avg_price, price_dispersion, avg_discount
        FROM city_metrics
        WHERE import_id = :import_id
        """)

        result = await self.session.execute(query, {'import_id': import_id})
        return [dict(r._mapping) for r in result]
    
    async def _get_competitors(self, import_id: str):
        query = text("""
        SELECT city, pharmacy_name, price_index, category
        FROM competitor_metrics
        WHERE import_id = :import_id
        ORDER BY city, price_index
        """)

        result = await self.session.execute(query, {'import_id': import_id})
        return [dict(r._mapping) for r in result]
    
    async def _get_product_menrics(self, import_id: str):
        query = text("""
        SELECT
            city,
            product_name,
            avg_price,
            min_price,
            max_price,
            std_dev
        FROM product_metrics
        WHERE import_id = :import_id
        ORDER BY std_dev DESC
        LIMIT 50
        """)

        result = await self.session.execute(query, {'import_id': import_id})
        return [dict(r._mapping) for r in result]
    
    async def _get_overpriced_products(self, import_id: str):
        """Завышенные товары (самый важный инсайт)"""
        query = text("""
        SELECT
            np.city,
            np.product_name,
            np.pharmacy_name,
            np.price,
            comp.avg_price,
            (np.price / comp.avg_price - 1) AS overprice_ratio
        FROM normalized_prices np
        JOIN (
            SELECT city, product_name, AVG(price) AS avg_price
            FROM normalized_prices
            WHERE is_our = false
            GROUP BY city, product_name
        ) comp
            ON np.city = comp.city
            AND np.product_name = comp.product_name
        WHERE np.import_id = :import_id
            AND np.is_our = true
            AND np.price > comp.avg_price * 1.1
        ORDER BY overprice_ratio DESC
        LIMIT 30
        """)

        result = await self.session.execute(query, {'import_id': import_id})
        return [dict(r._mapping) for r in result]
    
    async def _get_underpriced_product(self, import_id: str):
        """Недооцененные товары (потеря прибыли)"""
        query = text("""
        SELECT
            np.city,
            np.product_name,
            np.pharmacy_name,
            np.price,
            comp.avg_price,
            (1 - np.price / comp.avg_price) AS discount_ratio
        FROM normalized_prices np
        JOIN (
            SELECT city, product_name, AVG(price) AS avg_price
            FROM normalized_prices
            WHERE is_our = false
            GROUP BY city, product_name
        ) comp
        ON np.city = comp.city
        AND np.product_name = comp.product_name
        WHERE np.import_id = :import_id
        AND np.is_our = true
        AND np.price < comp.avg_price * 0.9
        ORDER BY discount_ratio DESC
        LIMIT 30       
        """)

        result = await self.session.execute(query, {'import_id': import_id})
        return [dict(r._mapping) for r in result]
    
    async def _get_high_variance_products(self, import_id: str):
        """Товары с высоким разбросом"""
        query = text("""
        SELECT
            city,
            product_name,
            avg_price,
            std_dev,
            (std_dev / avg_price) AS variation
        FROM product_metrics
        WHERE import_id = :import_id
        AND avg_price > 0
        ORDER BY variation DESC
        LIMIT 30
        """)

        result = await self.session.execute(query, {'import_id': import_id})
        return [dict(r._mapping) for r in result]
    
    async def _get_city_leaders(self, import_id: str):
        """Лидеры и аутсайдеры по городам"""
        query = text("""
        SELECT *
        FROM (
            SELECT
                city,
                pharmacy_name,
                price_index,
                category,
                RANK() OVER (PARTITION BY city ORDER BY price_index ASC) AS cheapest_rank,
                RANK() OVER (PARTITION BY city ORDER BY price_index DESC) AS expensive_rank
            FROM competitor_metrics
            WHERE import_id = :import_id
        ) t
        WHERE cheapest_rank = 1 OR expensive_rank = 1
        """)

        result = await self.session.execute(query, {'import_id': import_id})
        return [dict(r._mapping) for r in result]
