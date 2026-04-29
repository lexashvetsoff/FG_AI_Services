from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnaliticService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_competitor_metrics(self, import_id: UUID):
        query = text("""
        WITH market_avg AS (
            SELECT
            city,
            product_name,
            price_segment,
            AVG(price) AS avg_price
            FROM normalized_prices
            WHERE import_id = :import_id
            GROUP BY city, product_name, price_segment
        ),
                     
        pharmacy_avg AS (
            SELECT
                np.city,
                np.pharmacy_name,
                np.price_segment,
                AVG(np.price / ma.avg_price) AS price_index
            FROM normalized_prices np
            JOIN market_avg ma
                ON np.city = ma.city
                AND np.product_name = ma.product_name
                AND np.price_segment = ma.price_segment
            WHERE np.import_id = :import_id
            GROUP BY np.city, np.pharmacy_name, np.price_segment
        )
                     
        INSERT INTO competitor_metrics(import_id, city, pharmacy_name, price_segment, price_index, category, created_at)
        SELECT
            :import_id,
            city,
            pharmacy_name,
            price_segment,
            price_index,
            CASE
                WHEN price_index < 0.95 THEN 'cheap'
                WHEN price_index <= 1.05 THEN 'mid'
                ELSE 'expensive'
            END,
            NOW()
        FROM pharmacy_avg
        """)

        await self.session.execute(query, {'import_id': import_id})
        await self.session.commit()
    
    async def calculate_city_metrics(self, import_id: UUID):
        query = text("""
        WITH base AS (
            SELECT *
            FROM normalized_prices
            WHERE import_id =:import_id
        ),
        
        city_stats AS (
            SELECT
                city,
                price_segment,
                AVG(price) AS avg_price,
                STDDEV(price) AS price_dispersion
            FROM base
            GROUP BY city, price_segment
        ),
        
        discounts AS (
            SELECT
                np.city,
                AVG(
                    CASE
                        WHEN np.is_our THEN
                            (comp.avg_price - np.price) / comp.avg_price
                    END
                ) AS avg_discount
            FROM base np
            JOIN (
                SELECT city, product_name, price_segment, AVG(price) AS avg_price
                FROM base
                WHERE is_our = false
                GROUP BY city, product_name, price_segment
            ) comp
                ON np.city = comp.city
                AND np.product_name = comp.product_name
                AND np.price_segment = comp.price_segment
            GROUP BY np.city
        )
                    
        INSERT INTO city_metrics(import_id, city, price_segment, avg_price, price_dispersion, avg_discount, created_at)
        SELECT
            :import_id,
            cs.city,
            cs.price_segment,
            cs.avg_price,
            cs.price_dispersion,
            COALESCE(d.avg_discount, 0),
            NOW()
        FROM city_stats cs
        LEFT JOIN discounts d ON cs.city = d.city
        """)
        
        await self.session.execute(query, {'import_id': import_id})
        await self.session.commit()
    
    async def calculate_product_metrics(self, import_id: UUID):
        query = text("""
        INSERT INTO product_metrics (
            import_id,
            city,
            product_name,
            price_segment,
            avg_price,
            min_price,
            max_price,
            std_dev,
            created_at
        )
        SELECT
            :import_id,
            city,
            product_name,
            price_segment,
            AVG(price),
            MIN(price),
            MAX(price),
            STDDEV(price),
            NOW()
        FROM normalized_prices
        WHERE import_id = :import_id
        GROUP BY city, product_name, price_segment
        """)

        await self.session.execute(query, {'import_id': import_id})
        await self.session.commit()
