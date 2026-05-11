from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnaliticService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_pair_metrics(self, import_id: UUID):
        query = text("""
        INSERT INTO pair_price_metrics (
            import_id,
            city,
            product_name,
            price_segment,
            pair_id,
            our_pharmacy_name,
            our_pharmacy_instance,
            competitor_pharmacy_name,
            competitor_pharmacy_instance,
            our_price,
            competitor_price,
            diff_abs,
            diff_pct,
            status,
            created_at
        )
        SELECT
            np.import_id,
            np.city,
            np.product_name,
            np.price_segment,
            np.pair_id,

            np.pharmacy_name AS our_pharmacy_name,
            np.pharmacy_instance AS our_pharmacy_instance,
            comp.pharmacy_name AS competitor_pharmacy_name,
            comp.pharmacy_instance AS competitor_pharmacy_instance,

            np.price AS our_price,
            comp.price AS competitor_price,

            (np.price - comp.price) AS diff_abs,

            CASE 
                WHEN comp.price = 0 THEN 0
                ELSE (np.price - comp.price) / comp.price
            END AS diff_pct,

            CASE
                WHEN (np.price - comp.price) / comp.price > 0.05 THEN 'overprice'
                WHEN (np.price - comp.price) / comp.price < -0.05 THEN 'underprice'
                ELSE 'parity'
            END AS status,
            
            NOW()

        FROM normalized_prices np
        JOIN normalized_prices comp
            ON np.import_id = comp.import_id
        AND np.city = comp.city
        AND np.product_name = comp.product_name
        AND np.pair_id = comp.pair_id

        WHERE np.import_id = :import_id
        AND np.is_our = true
        AND comp.is_our = false
        AND np.price IS NOT NULL
        AND comp.price IS NOT NULL
        """)

        await self.session.execute(query, {'import_id': import_id})
        await self.session.commit()
    
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
                np.pharmacy_instance,
                np.price_segment,
                AVG(np.price / ma.avg_price) AS price_index
            FROM normalized_prices np
            JOIN market_avg ma
                ON np.city = ma.city
                AND np.product_name = ma.product_name
                AND np.price_segment = ma.price_segment
            WHERE np.import_id = :import_id
            GROUP BY np.city, np.pharmacy_name, np.pharmacy_instance, np.price_segment
        )
                     
        INSERT INTO competitor_metrics(import_id, city, pharmacy_name, pharmacy_instance, price_segment, price_index, category, created_at)
        SELECT
            :import_id,
            city,
            pharmacy_name,
            pharmacy_instance,
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
