from typing import List
# from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor_analysis import NormalizedPrice


class PriceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def bulk_insert(self, rows: List[dict], batch_size: int = 1000):
        if not rows:
            return
        
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]

            stmt = insert(NormalizedPrice).values(batch).on_conflict_do_nothing()
            # stmt = stmt.on_conflict_do_nothing()
            await self.session.execute(stmt)
        await self.session.commit()
