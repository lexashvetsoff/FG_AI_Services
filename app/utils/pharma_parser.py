import re
import math
from typing import Optional, Dict, List, Set, Tuple


def extract_strength(text: str) -> Optional[str]:
    """Извлекает дозировку. Поддерживает составные: 2мг+0.03мг, 15мг+153.5мг"""
    pattern = r'(\d+(?:[.,]\d+)?)\s*(мг|мл|г|мкг|%)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if not matches:
        return None
    normalized = [f"{v.replace(',', '.')}{u}" for v, u in matches]
    return '+'.join(normalized) if len(normalized) > 1 else normalized[0]


def extract_core_strength(text: str) -> Optional[str]:
    """Извлекает ТОЛЬКО активное вещество (первая дозировка). Игнорирует вес оболочки/наполнителя."""
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(мг|мл|г|мкг|%)', text, re.IGNORECASE)
    if match:
        return f"{match.group(1).replace(',', '.')}{match.group(2)}"
    return None


def normalize_pack_count(text: str) -> Optional[int]:
    """Превращает фасовку в абсолютное число единиц. Handles №21+7, №28х3, 60 шт, 150 мл/г"""
    t = text.upper().strip()
    # 21+7 -> 28
    m = re.search(r'(?:№|N)?\s*(\d+)\s*\+\s*(\d+)', t)
    if m: return int(m.group(1)) + int(m.group(2))
    # 28х3 -> 84
    m = re.search(r'(?:№|N)?\s*(\d+)\s*[ХXхx]\s*(\d+)', t)
    if m: return int(m.group(1)) * int(m.group(2))
    # Стандартный №30 или 30 шт/таб/капс
    m = re.search(r'(?:№|N|номер)?\s*(\d+)', t)
    if m: return int(m.group(1))
    return None


def normalize_dosage_form(text: str) -> Optional[str]:
    t = text.lower()
    mapping = {
        r'таб': 'таблетки', r'капсул': 'капсулы', r'сироп': 'сироп',
        r'мазь|крем|гель': 'мазь/гель', r'р-р|раствор': 'раствор',
        r'суппозит|свеч': 'свечи', r'кап[л.и]': 'капли', r'порошок': 'порошок',
        r'спрей': 'спрей', r'гель для душа': 'гель'
    }
    for pat, norm in mapping.items():
        if re.search(pat, t): return norm
    return None


def extract_ingredients(text: str) -> Set[str]:
    """Извлекает ключевые добавки/вещества. Нормализует регистр и окончания."""
    if not text: return set()
    t = text.lower()
    ings = set()
    # Паттерны: "с X, Y и Z", "+X", "содержит X"
    for match in re.finditer(r'[с+]\s*([а-яёa-z0-9\s,+\-]+?)(?:\s+№|\s+таб|\s+капс|\s+мл|\s+г|\.|$)', t):
        parts = re.split(r'[,\s+и\s+]', match.group(1))
        ings.update(p.strip() for p in parts if len(p.strip()) > 2)
    
    # Словарь известных веществ для точного маппинга
    KNOWN = {'лютеин', 'зеаксантин', 'черника', 'хром', 'цинк', 'селен', 'магний', 
             'глицин', 'кальций', 'калий', 'железо', 'йод', 'омега', 'коллаген', 
             'биотин', 'коэнзим', 'карнитин', 'витамины группы в', 'vitamin b'}
    for k in KNOWN:
        if k in t: ings.add(k)
    return ings


def extract_brand(text: str) -> str:
    """Извлекает бренд/МНН (первые 1-2 слова до цифр/дозировок)"""
    t = text.strip()
    # Берём всё до первой цифры или знака +
    match = re.match(r'^([^\d+\-]+?)\s*(?:\d|таб|капс|№|$)', t, re.IGNORECASE)
    if match:
        brand = match.group(1).strip().lower()
        # Убираем короткие предлоги
        words = brand.split()
        if words and words[0] in ['для', 'при', 'от', 'с', 'и']:
            words = words[1:]
        return ' '.join(words[:2]) if words else ''
    return ''


def extract_all_attrs(text: str) -> Dict:
    return {
        'strength': extract_strength(text),
        'core_strength': extract_core_strength(text),
        'dosage_form': normalize_dosage_form(text),
        'pack_count': normalize_pack_count(text),
        'ingredients': extract_ingredients(text),
        'brand': extract_brand(text)
    }
