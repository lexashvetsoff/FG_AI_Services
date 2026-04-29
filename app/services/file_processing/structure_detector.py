import pandas as pd
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PharmacyBlock:
    name: str
    is_our: bool
    price_col: int


@dataclass
class SheetStructure:
    city: str
    header_row: int
    product_col: int
    pharmacy_blocks: List[PharmacyBlock]


class StructureDetector:
    def detect(self, df: pd.DataFrame, sheet_name: str) -> SheetStructure:
        df = self._preprocess(df)

        header_row = self._find_header_row(df)
        product_col = self._find_product_col(df, header_row)
        blocks = self._detect_pharmacy_blocks(df, header_row)

        return SheetStructure(
            city=sheet_name,
            header_row=header_row,
            product_col=product_col,
            pharmacy_blocks=blocks
        )
    
    # =========================
    # PREPROCESS
    # =========================
    def _preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        # заполняем merged cells по горизонтали
        df = df.copy()
        # df.fillna(method='ffill', axis=1, inplace=True)
        # print(type(df))
        df = df.ffill(axis=1)
        # print(type(df))
        return df

    # =========================
    # HEADER DETECTION
    # =========================
    def _find_header_row(self, df: pd.DataFrame) -> int:
        # print(type(df))
        for i in range(min(15, len(df))):
            row = df.iloc[i]

            if row.astype(str).str.contains('наимен', case=False).any():
                return i
        
        raise ValueError('Не удалось найти строку заголовков')
    
    def _find_product_col(self, df: pd.DataFrame, header_row: int) -> int:
        row = df.iloc[header_row]

        for col, val in enumerate(row):
            if isinstance(val, str) and 'наимен' in val.lower():
                return col
        
        raise ValueError('Не удалось найти колонку товара')

    # =========================
    # PHARMACY BLOCKS
    # =========================
    def _detect_pharmacy_blocks(self, df: pd.DataFrame, header_row: int) -> List[PharmacyBlock]:
        header = df.iloc[header_row]
        subheader = df.iloc[header_row + 1]

        blocks: List[PharmacyBlock] = []

        for col in range(len(header)):
            # print(type(header))
            # cell = header[col]
            cell = header.iloc[col]

            if not isinstance(cell, str):
                continue

            name = cell.strip()
            if not name:
                continue

            if self._is_system_cell(name):
                continue

            block = self._build_block(name, col, subheader)
            if block:
                blocks.append(block)
        
        return self._deduplicate_blocks(blocks)

    # =========================
    # BLOCK BUILDING
    # =========================
    def _build_block(self, name: str, col: int, subheader: pd.Series) -> Optional[PharmacyBlock]:
        # sub = subheader[col]
        sub = subheader.iloc[col]
        if not isinstance(sub, str):
            return None
        
        sub = sub.lower()

        # определяем тип колонки
        if 'цена аптеки' in sub:
            return PharmacyBlock(
                name=self._normalize_name(name),
                is_our=self._is_our(name),
                price_col=col
            )
        
        if 'цена конкурента' in sub:
            return PharmacyBlock(
                name=self._normalize_name(name),
                is_our=False,
                price_col=col
            )
        
        return None

    # =========================
    # HELPERS
    # =========================
    def _is_system_cell(self, cell: str) -> bool:
        blacklist = [
            'наименование',
            'цена',
            'закуп',
            'баз',
            'к закуп',
            'к базе',
            '%',
            'разница'
        ]
        cell = cell.lower()

        return any(word in cell for word in blacklist)
    
    def _is_our(self, name: str) -> bool:
        return name.strip().upper().startswith('ФГ')
    
    def _normalize_name(self, name: str) -> str:
        # убираем адреса/телефоны
        return name.split(';')[0].strip()
    
    def _deduplicate_blocks(self, blocks: List[PharmacyBlock]) -> List[PharmacyBlock]:
        seen = {}
        result = []

        for block in blocks:
            name = block.name

            if name in seen:
                seen[name] += 1
                new_name = f'{name}_{seen[name]}'
            else:
                seen[name] = 1
                new_name = name
            
            result.append(
                PharmacyBlock(
                    name=new_name,
                    is_our=block.is_our,
                    price_col=block.price_col
                )
            )
        
        return result
