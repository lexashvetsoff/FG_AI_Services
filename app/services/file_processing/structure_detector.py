import re
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PharmacyBlock:
    pharmacy_name: str
    pharmacy_instance: str
    is_our: bool
    price_col: int


@dataclass
class PharmacyPair:
    our: PharmacyBlock
    competitor: PharmacyBlock


@dataclass
class SheetStructure:
    city: str
    header_row: int
    product_col: int
    pharmacy_pairs: List[PharmacyPair]


class StructureDetector:
    def detect(self, df: pd.DataFrame, sheet_name: str) -> SheetStructure:
        df = self._preprocess(df)

        header_row = self._find_header_row(df)
        product_col = self._find_product_col(df, header_row)
        blocks = self._detect_pharmacy_blocks(df, header_row)
        pairs = self._build_pairs(blocks)

        return SheetStructure(
            city=sheet_name,
            header_row=header_row,
            product_col=product_col,
            pharmacy_pairs=pairs
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

        normalized = self._normalize_name(name)

        # определяем тип колонки
        if 'цена аптеки' in sub:
            return PharmacyBlock(
                pharmacy_name=self._extract_network_name(normalized),
                pharmacy_instance=normalized,
                is_our=self._is_our(name),
                price_col=col
            )
        
        if 'цена конкурента' in sub:
            return PharmacyBlock(
                pharmacy_name=self._extract_network_name(normalized),
                pharmacy_instance=normalized,
                is_our=False,
                price_col=col
            )
        
        return None
    
    # =========================
    # PAIRS
    # =========================
    def _build_pairs(self, blocks: List[PharmacyBlock]) -> List[PharmacyPair]:
        pairs = []

        i = 0
        while i < len(blocks) - 1:
            current = blocks[i]
            next_block = blocks[i+1]

            # ожидаем: наша → конкурент
            if current.is_our and not next_block.is_our:
                pairs.append(
                    PharmacyPair(
                        our=current,
                        competitor=next_block
                    )
                )
                i += 2
            else:
                # fallback (грязные данные)
                i += 1
        
        return pairs

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

        # for block in blocks:
        #     key = block.pharmacy_name

        #     if key in seen:
        #         seen[key] += 1
        #         instance  = f'{key}_{seen[key]}'
        #     else:
        #         seen[key] = 1
        #         instance  = key
            
        #     result.append(
        #         PharmacyBlock(
        #             pharmacy_name=block.pharmacy_name,
        #             pharmacy_instance=instance,
        #             is_our=block.is_our,
        #             price_col=block.price_col
        #         )
        #     )
        for block in blocks:
            name = block.pharmacy_instance

            if name in seen:
                seen[name] += 1
                new_name = f'{name}_{seen[name]}'
            else:
                seen[name] = 1
                new_name = name
            
            result.append(
                PharmacyBlock(
                    pharmacy_name=block.pharmacy_name,
                    pharmacy_instance=new_name,
                    is_our=block.is_our,
                    price_col=block.price_col
                )
            )
        
        return result
    
    def _extract_network_name(self, name: str) -> str:
        name = name.strip()

        # убираем _4 _12 и тд
        name = re.sub(r'_\d+$', '', name)

        # убираем двойные пробелы
        name = re.sub(r'\s+', ' ', name)

        return name.strip()
