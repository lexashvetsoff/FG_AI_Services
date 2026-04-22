import re
import math
from typing import Optional, Dict, List


# def extract_strength(text: str) -> Optional[str]:
#     """Извлекает дозировку: 400мг, 500 мг, 5%, 100мл"""
#     match = re.search(r'(\d+(?:[.,]\d+)?)\s*(мг|мл|г|%)', text, re.IGNORECASE)
#     if match:
#         val = match.group(1).replace(',', '.')
#         return f'{val} {match.group(2)}'.strip()
#     return None


def extract_strength(text: str) -> Optional[str]:
    """
    Извлекает дозировку: 400мг, 500 мг, 2мг+0.03мг, 5мг/мл
    Поддерживает составные дозировки с + или /
    """
    # Ищем все вхождения чисел с единицами измерения
    pattern = r'(\d+(?:[.,]\d+)?)\s*(мг|мл|г|%)'
    matches = re.findall(pattern, text, re.IGNORECASE)

    if not matches:
        return None
    
    # Нормализуем: запятая -> точка, убираем пробелы
    normalized = []
    for value, unit in matches:
        val = value.replace(',', '.').strip()
        normalized.append(f'{val}{unit}')
    
    # Если несколько компонентов - соединяем через +
    return '+'.join(normalized) if len(normalized) > 1 else normalized[0]


def normalize_strength(strength: str) -> List[str]:
    """
    Разбивает составную дозировку на компоненты и сортирует их
    "2мг+0.03мг" -> ["0.03мг", "2мг"] (сортировка для надёжного сравнения)
    """
    if not strength:
        return []
    
    # Разделяем по + или /
    components = re.split(r'[+/]', strength)
    normalized = []

    for comp in components:
        comp = comp.strip().lower()
        # Извлекаем число и единицу
        match = re.match(r'(\d+(?:\.\d+)?)\s*(мг|мл|г|%)', comp, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            unit = match.group(2).lower()
            normalized.append((val, unit))
    
    # Сортируем по значению (для надёжного сравнения)
    normalized.sort(key=lambda x: x[0])
    return [f'{val}{unit}' for val, unit in normalized]


def strength_match(strength1: str, strength2: str, tolerance: float = 0.01) -> bool:
    """
    Сравнивает две дозировки с учётом:
    - Составных дозировок (2мг+0.03мг)
    - Разных разделителей (точка/запятая)
    - Порядка компонентов
    - Небольшой погрешности (tolerance)
    """
    norm1 = normalize_strength(strength1)
    norm2 = normalize_strength(strength2)

    if len(norm1) != len(norm2):
        return False
    
    for comp1, comp2 in zip(norm1, norm2):
        # Извлекаем числовые значения
        match1 = re.match(r'(\d+(?:\.\d+)?)\s*(мг|мл|г|%)', comp1, re.IGNORECASE)
        match2 = re.match(r'(\d+(?:\.\d+)?)\s*(мг|мл|г|%)', comp2, re.IGNORECASE)

        if not match1 or not match2:
            return comp1 == comp2
        
        val1 = float(match1.group(1))
        val2 = float(match2.group(1))
        unit1 = match1.group(2).lower()
        unit2 = match2.group(2).lower()

        # Единицы должны совпадать
        if unit1 != unit2:
            return False
        
        # Значения должны совпадать с погрешностью
        if not math.isclose(val1, val2, rel_tol=tolerance):
            return False
    
    return True


def extract_pack_size_old(text: str) -> Optional[str]:
    """Извлекает фасовку: №20, 20 шт, 30шт"""
    match = re.search(r'(?:№|номер)?\s*(\d+)\s*(?:шт)?', text, re.IGNORECASE)
    return f"№{match.group(1)}" if match else None


def extract_pack_size_old2(text: str) -> Optional[str]:
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


def extract_pack_size(text: str) -> Optional[str]:
    """
    Ищет фасовку: №20, 60 шт, N30, 100 ампул и т.д.
    Важно не спутать с дозировкой (24 мг).
    """
    # Ищем число, за которым следует маркер фасовки или "шт"
    # Приоритет: №N, затем число перед "шт/таб/кап/уп"
    match = re.search(r'(?:№|N|номер)?\s*(\d+)\s*(?:шт|таб|кап|уп|амп|фл|мл|г)', text, re.IGNORECASE)
    if match:
        return f'№{match.group(1)}'
    
    # Если нет маркера, ищем просто "число шт" в конце строки или рядом с "упаковка"
    match = re.search(r'(\d+)\s*шт', text, re.IGNORECASE)
    if match:
        return f'№{match.group(1)}'
    
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
