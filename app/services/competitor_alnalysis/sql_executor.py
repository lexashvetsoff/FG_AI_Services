from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def execute_sql(session: AsyncSession, sql: str):
    result = await session.execute(text(sql))
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]
