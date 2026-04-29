from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ContextBuilder:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def build(self, import_id: str):
        cities = await self._get_sity_metrics(import_id)
        competitors = await self._get_competitors(import_id)
        # TODO product metrics

        return {
            'cities': cities,
            'competitors': competitors
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
