from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.competitor_analysis import Import
from app.utils.competitor_analysis_utils import ImportStatus, SourceType


class ImportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, file_name: str) -> Import:
        obj = Import(
            source_type=SourceType.excel,
            file_name=file_name,
            status=ImportStatus.uploaded
        )

        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)

        return obj
    
    async def set_status(self, import_id, status):
        await self.session.execute(
            update(Import)
            .where(Import.id == import_id)
            .values(status=status)
        )
        await self.session.commit()
