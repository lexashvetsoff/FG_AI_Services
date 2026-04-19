import re
from typing import Optional, Dict


def extract_strength(text: str) -> Optional[str]:
    """Извлекает дозировку: 400мг, 500 мг, 5%, 100мл"""
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(мг|мл|г|%)', text, re.IGNORECASE)
    if match:
        val = match.group(1).replace(',', '.')
        return f'{val} {match.group(2)}'.strip()
    return None


def extract_pack_size_old(text: str) -> Optional[str]:
    """Извлекает фасовку: №20, 20 шт, 30шт"""
    match = re.search(r'(?:№|номер)?\s*(\d+)\s*(?:шт)?', text, re.IGNORECASE)
    return f"№{match.group(1)}" if match else None


def extract_pack_size(text: str) -> Optional[str]:
    """Извлекает фасовку: №20, 20 шт, 30шт"""
    # Сначала ищем явный № с числом
    match = re.search(r'№\s*(\d+)', text, re.IGNORECASE)
    if match:
        return f"№{match.group(1)}"
    
    # 2. Число + единица фасовки (шт, таб, капс, уп, блистер, доза)
    pattern = r'\b(\d+)\s*(?:шт|штук|таб|таблетки|таблеток|капс|капсул|уп|упаковки|блистер|дозы)\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return f"№{match.group(1)}"
    
    # Если ничего не найдено, пробуем найти число в конце строки (часто фасовка последняя)
    match = re.search(r'(\d+)\s*$', text)
    if match:
        return f"№{match.group(1)}"
    
    return None


def normalize_dosage_form(text: str) -> Optional[str]:
    """Нормализует ЛФ: таб.п.о. -> таблетки, р-р -> раствор и т.д."""
    t = text.lower()
    mapping = {
        r'таб': 'таблетки', r'капсул': 'капсулы', r'сироп': 'сироп',
        r'мазь|крем|гель': 'мазь/гель', r'р-р|раствор': 'раствор',
        r'суппозит|свеч': 'свечи', r'кап[л.и]': 'капли', r'порошок': 'порошок'
    }
    for pattern, norm in mapping.items():
        if re.search(pattern, t):
            return norm
    return None


def extract_all_attrs(text: str) -> Dict[str, Optional[str]]:
    """Извлекает дозировку, форму и фасовку в единый dict"""
    return {
        'strength': extract_strength(text),
        'dosage_form': normalize_dosage_form(text),
        'pack_size': extract_pack_size(text)
    }
