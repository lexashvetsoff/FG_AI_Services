import uuid
import pandas as pd
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.file_processing.structure_detector import StructureDetector
from app.services.file_processing.excel_processor import ExcelProcessor
from app.repository.price_repository import PriceRepository
from app.repository.import_repository import ImportRepository
from app.services.file_processing.analitics_service import AnaliticService


class ImportService:
    def __init__(self, session: AsyncSession):
        self.session = session

        self.detector = StructureDetector()
        self.processor = ExcelProcessor()

        self.price_repo = PriceRepository(session)
        self.import_repo = ImportRepository(session)
        self.analytics = AnaliticService(session)
    
    async def process_file(self, file_path: Path, filename: str):
        # 1. создаем import
        import_obj = await self.import_repo.create(filename)

        try:
            xls = pd.ExcelFile(file_path)
            all_rows = []

            for sheet in xls.sheet_names:
                df = xls.parse(sheet)

                structure = self.detector.detect(df, sheet)
                dtos = self.processor.process(df, structure, import_obj.id)

                all_rows.extend([self._dto_to_dict(d) for d in dtos])
            
            # 2. сохраняем
            await self.price_repo.bulk_insert(all_rows)

            # 3. аналитика
            await self.analytics.calculate_product_metrics(import_obj.id)
            await self.analytics.calculate_competitor_metrics(import_obj.id)
            await self.analytics.calculate_city_metrics(import_obj.id)

            # 4. статус
            await self.import_repo.set_status(import_obj.id, 'done')
        
        except Exception as e:
            await self.session.rollback()
            await self.import_repo.set_status(import_obj.id, 'error')
            raise e
        
        return import_obj.id
    
    def _dto_to_dict(self, dto):
        return {
            'import_id': dto.import_id,
            'city': dto.city,
            'product_name': dto.product_name,
            'pharmacy_name': dto.pharmacy_name,
            'is_our': dto.is_our,
            'price': dto.price,
            'purchase_price': dto.purchase_price,
        }
