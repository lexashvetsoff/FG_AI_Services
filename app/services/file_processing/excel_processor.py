import pandas as pd
from uuid import UUID
from typing import List
from decimal import Decimal
from dataclasses import dataclass
from app.services.file_processing.structure_detector import SheetStructure, PharmacyBlock


@dataclass
class NormalizedPriceDTO:
    import_id: UUID
    city: str
    product_name: str
    pharmacy_name: str
    is_our: bool
    price: Decimal | None
    purchase_price: Decimal | None


class ExcelProcessor:
    def process(self, df: pd.DataFrame, structure: SheetStructure, import_id: UUID) -> List[NormalizedPriceDTO]:
        df = self._preprocess(df)
        result: List[NormalizedPriceDTO] = []
        start_row = structure.header_row + 2    # данные начинаются ниже

        for row_idx in range(start_row, len(df)):
            row = df.iloc[row_idx]

            product_name = self._extract_product_name(
                row,
                structure.product_col
            )
            if not product_name:
                continue

            for block in structure.pharmacy_blocks:
                price = self._extract_price(row, block.price_col)
                if price is None:
                    continue

                dto = NormalizedPriceDTO(
                    import_id=import_id,
                    city=structure.city,
                    product_name=product_name,
                    pharmacy_name=block.name,
                    is_our=block.is_our,
                    price=price,
                    purchase_price=None # добавим позже
                )

                result.append(dto)
        return result
    
    def _preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # df.fillna(method='ffill', axis=1, inplace=True)
        df = df.ffill(axis=1)
        return df
    
    def _extract_product_name(self, row, product_col) -> str | None:
        # print(type(row))
        # value = row[product_col]
        value = row.iloc[product_col]
        if not isinstance(value, str):
            return None
        
        value = value.strip()
        if not value:
            return None
        
        # фильтрация мусора
        if self._is_group_row(value):
            return None
        
        if len(value) < 3:
            return None
        
        return value
    
    def _is_group_row(self, value: str) -> bool:
        value = value.strip()

        # примеры: "0-150", "151-500"
        if '-' in value:
            parts = value.split('-')
            if all(p.strip().isdigit() for p in parts):
                return True
            
            if 'итого' in value.lower():
                return True
        return False
    
    def _extract_price(self, row, col) -> Decimal | None:
        # print(type(row))
        # value = row[col]
        value = row.iloc[col]

        if value is None:
            return None
        
        if isinstance(value, str):
            value = value.replace(',', '.').strip()
        
        try:
            num = float(value)
        except (ValueError, TypeError):
            return None
        
        if num <= 0:
            return None
        
        return Decimal(str(num))
