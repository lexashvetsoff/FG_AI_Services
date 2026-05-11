from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ContextBuilder:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def build(self, import_id: str, segment: str):
        cities = await self._get_sity_metrics(import_id, segment)
        competitors = await self._get_competitors(import_id, segment)
        products = await self._get_product_metrics(import_id, segment)
        overpriced = await self._get_overpriced_products(import_id, segment)
        underpriced = await self._get_underpriced_product(import_id, segment)
        high_variance = await self._get_high_variance_products(import_id, segment)
        city_leaders = await self._get_city_leaders(import_id, segment)

        return {
            'segment': segment,
            'cities': cities,
            'competitors': competitors,
            'products': products,
            'overpriced': overpriced,
            'underpriced': underpriced,
            'high_variance': high_variance,
            'city_leaders': city_leaders
        }
    
    async def build_full(self, import_id: str):
        segments = await self.get_segments(import_id)
        result = []

        for segment in segments:
            pair_summary = await self._get_pair_summary(import_id, segment)

            result.append({
                "segment": segment,
                "pair_summary": pair_summary,
                "insights": self._build_pair_insights(pair_summary)
            })
        
        return {
            "segments": result
        }
    
    async def build_for_segment(self, import_id: str, segment: str):
        cities = await self._get_sity_metrics(import_id, segment)
        competitors = await self._get_competitors(import_id, segment)
        products = await self._get_product_metrics(import_id, segment)
        pair_summary = await self._get_pair_summary(import_id, segment)
        insights = self._build_pair_insights(pair_summary)

        return {
            'segment': segment,
            'cities': cities,
            'competitors': competitors,
            'products': products,
            'pair_summary': pair_summary,
            'insights': insights
        }
    
    async def build_chat(self, import_id: str):
        # пока MVP: просто топ данные
        cities = await self._get_sity_metrics(import_id)
        competitors = await self._get_competitors(import_id)

        return {
            'cities': cities[:10],
            'competitors': competitors[:20]
        }
    
    async def _get_pair_summary(self, import_id: str, segment: str = None):
        query = """
        SELECT
            city,
            our_pharmacy_name,
            our_pharmacy_instance,
            competitor_pharmacy_name,
            competitor_pharmacy_instance,
            COUNT(*) AS total_positions,
            AVG(diff_pct) AS avg_diff_pct,
            SUM(CASE WHEN status = 'overprice' THEN 1 ELSE 0 END) AS overpriced_count,
            SUM(CASE WHEN status = 'underprice' THEN 1 ELSE 0 END) AS underpriced_count
        FROM pair_price_metrics
        WHERE import_id = :import_id
        """

        params = {'import_id': import_id}

        if segment:
            query += "AND price_segment = :segment"
            params['segment'] = segment
        
        query += """
        GROUP BY city, our_pharmacy_name, our_pharmacy_instance, competitor_pharmacy_name, competitor_pharmacy_instance
        ORDER BY avg_diff_pct DESC
        LIMIT 250
        """

        result = await self.session.execute(text(query), params)
        return [dict(r._mapping) for r in result]
    
    def _build_pair_insights(self, pair_summary: list[dict]) -> dict:
        insights = {
            'top_overpriced': [],
            'top_underpriced': [],
            'main_competitors': {}
        }

        for row in pair_summary:
            comp = row['competitor_pharmacy_instance']

            # считаем частоту конкурентов
            insights['main_competitors'].setdefault(comp, 0)
            insights['main_competitors'][comp] += row['total_positions']

            # overpriced
            if row['avg_diff_pct'] and row['avg_diff_pct'] > 0.05:
                insights['top_overpriced'].append(row)

            # underpriced
            if row['avg_diff_pct'] and row['avg_diff_pct'] < -0.05:
                insights['top_underpriced'].append(row)
        
        # сортировки
        insights['top_overpriced'] = sorted(
            insights['top_overpriced'],
            key=lambda x: x['avg_diff_pct'],
            reverse=True
        )[:10]

        insights['top_underpriced'] = sorted(
            insights['top_underpriced'],
            key=lambda x: x['avg_diff_pct']
        )[:10]

        insights['main_competitors'] = sorted(
            insights['main_competitors'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return insights
    
    async def _get_sity_metrics(self, import_id: str, segment: str = None):
        # query = text("""
        # SELECT city, avg_price, price_dispersion, avg_discount
        # FROM city_metrics
        # WHERE import_id = :import_id
        # """)
        if segment is None:
            query = text("""
            SELECT
                city,
                price_segment,
                avg_price,
                price_dispersion,
                avg_discount
            FROM city_metrics
            WHERE import_id = :import_id
            ORDER BY city
            """)

            result = await self.session.execute(query, {'import_id': import_id})
        else:
            query = text("""
            SELECT
                city,
                price_segment,
                avg_price,
                price_dispersion,
                avg_discount
            FROM city_metrics
            WHERE import_id = :import_id
                AND price_segment = :segment
            ORDER BY city
            """)

            result = await self.session.execute(query, {'import_id': import_id, 'segment': segment})
        
        return [dict(r._mapping) for r in result]
    
    async def _get_competitors(self, import_id: str, segment: str = None):
        # query = text("""
        # SELECT city, pharmacy_name, price_index, category
        # FROM competitor_metrics
        # WHERE import_id = :import_id
        # ORDER BY city, price_index
        # """)
        if segment is None:
            query = text("""
            SELECT
                city,
                price_segment,
                pharmacy_name,
                pharmacy_instance,
                price_index,
                category
            FROM competitor_metrics
            WHERE import_id = :import_id
            ORDER BY city, price_index
            """)

            result = await self.session.execute(query, {'import_id': import_id})
        else:
            query = text("""
            SELECT
                city,
                price_segment,
                pharmacy_name,
                pharmacy_instance,
                price_index,
                category
            FROM competitor_metrics
            WHERE import_id = :import_id
                AND price_segment = :segment
            ORDER BY city, price_index
            """)

            result = await self.session.execute(query, {'import_id': import_id, 'segment': segment})
        
        return [dict(r._mapping) for r in result]
    
    async def _get_product_metrics(self, import_id: str, segment: str):
        # query = text("""
        # SELECT
        #     city,
        #     product_name,
        #     avg_price,
        #     min_price,
        #     max_price,
        #     std_dev
        # FROM product_metrics
        # WHERE import_id = :import_id
        # ORDER BY std_dev DESC
        # LIMIT 50
        # """)
        query = text("""
        SELECT
            city,
            price_segment,
            product_name,
            avg_price,
            min_price,
            max_price,
            std_dev
        FROM product_metrics
        WHERE import_id = :import_id
            AND price_segment = :segment
        ORDER BY std_dev DESC
        LIMIT 50
        """)

        result = await self.session.execute(query, {'import_id': import_id, 'segment': segment})
        return [dict(r._mapping) for r in result]
    
    async def _get_overpriced_products(self, import_id: str, segment: str):
        """Завышенные товары (самый важный инсайт)"""
        # query = text("""
        # SELECT
        #     np.city,
        #     np.product_name,
        #     np.pharmacy_name,
        #     np.price,
        #     comp.avg_price,
        #     (np.price / comp.avg_price - 1) AS overprice_ratio
        # FROM normalized_prices np
        # JOIN (
        #     SELECT city, product_name, AVG(price) AS avg_price
        #     FROM normalized_prices
        #     WHERE is_our = false
        #     GROUP BY city, product_name
        # ) comp
        #     ON np.city = comp.city
        #     AND np.product_name = comp.product_name
        # WHERE np.import_id = :import_id
        #     AND np.is_our = true
        #     AND np.price > comp.avg_price * 1.1
        # ORDER BY overprice_ratio DESC
        # LIMIT 30
        # """)
        query = text("""
        SELECT
            np.city,
            np.price_segment,
            np.product_name,
            np.pharmacy_name,
            np.pharmacy_instance,
            np.price,
            comp.avg_price,
            (np.price / comp.avg_price - 1) AS overprice_ratio
        FROM normalized_prices np
        JOIN (
            SELECT
                city,
                product_name,
                price_segment,
                AVG(price) AS avg_price
            FROM normalized_prices
            WHERE is_our = false
                AND price_segment = :segment
            GROUP BY city, product_name, price_segment
        ) comp
        ON np.city = comp.city
            AND np.product_name = comp.product_name
            AND np.price_segment = comp.price_segment
        WHERE np.import_id = :import_id
            AND np.price_segment = :segment
            AND np.is_our = true
            AND np.price > comp.avg_price * 1.1
        ORDER BY overprice_ratio DESC
        LIMIT 30
        """)

        result = await self.session.execute(query, {'import_id': import_id, 'segment': segment})
        return [dict(r._mapping) for r in result]
    
    async def _get_underpriced_product(self, import_id: str, segment: str):
        """Недооцененные товары (потеря прибыли)"""
        query = text("""
        SELECT
            np.city,
            np.price_segment,
            np.product_name,
            np.pharmacy_name,
            np.pharmacy_instance,
            np.price,
            comp.avg_price,
            (1 - np.price / comp.avg_price) AS discount_ratio
        FROM normalized_prices np
        JOIN (
            SELECT 
                city,
                product_name,
                price_segment,
                AVG(price) AS avg_price
            FROM normalized_prices
            WHERE is_our = false
                AND price_segment = :segment
            GROUP BY city, product_name, price_segment
        ) comp
        ON np.city = comp.city
            AND np.product_name = comp.product_name
            AND np.price_segment = comp.price_segment
        WHERE np.import_id = :import_id
            AND np.price_segment = :segment
            AND np.is_our = true
            AND np.price < comp.avg_price * 0.9
        ORDER BY discount_ratio DESC
        LIMIT 30       
        """)

        result = await self.session.execute(query, {'import_id': import_id, 'segment': segment})
        return [dict(r._mapping) for r in result]
    
    async def _get_high_variance_products(self, import_id: str, segment: str):
        """Товары с высоким разбросом"""
        query = text("""
        SELECT
            city,
            price_segment,
            product_name,
            avg_price,
            std_dev,
            (std_dev / avg_price) AS variation
        FROM product_metrics
        WHERE import_id = :import_id
            AND price_segment = :segment
            AND avg_price > 0
        ORDER BY variation DESC
        LIMIT 30
        """)

        result = await self.session.execute(query, {'import_id': import_id, 'segment': segment})
        return [dict(r._mapping) for r in result]
    
    async def _get_city_leaders(self, import_id: str, segment: str):
        """Лидеры и аутсайдеры по городам"""
        query = text("""
        SELECT *
        FROM (
            SELECT
                city,
                price_segment,
                pharmacy_name,
                pharmacy_instance,
                price_index,
                category,
                RANK() OVER (PARTITION BY city ORDER BY price_index ASC) AS cheapest_rank,
                RANK() OVER (PARTITION BY city ORDER BY price_index DESC) AS expensive_rank
            FROM competitor_metrics
            WHERE import_id = :import_id
                AND price_segment = :segment
        ) t
        WHERE cheapest_rank = 1 OR expensive_rank = 1
        """)

        result = await self.session.execute(query, {'import_id': import_id, 'segment': segment})
        return [dict(r._mapping) for r in result]
    
    async def get_segments(self, import_id: str):
        query = text("""
        SELECT DISTINCT price_segment
        FROM normalized_prices
        WHERE import_id = :import_id
        ORDER BY price_segment
        """)

        result = await self.session.execute(query, {'import_id': import_id})
        return [r[0] for r in result]
