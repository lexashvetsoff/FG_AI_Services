import re
import math
from typing import Optional, Dict, List, Set


def extract_strength(text: str) -> Optional[str]:
    """Извлекает дозировку. Поддерживает составные: 10мг, 2мг+0.03мг"""
    pattern = r'(\d+(?:[.,]\d+)?)\s*(мг|мл|г|мкг|%)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if not matches:
        return None
    normalized = [f"{v.replace(',', '.')}{u}" for v, u in matches]
    return '+'.join(normalized) if len(normalized) > 1 else normalized[0]


def normalize_strength(strength: str) -> List[str]:
    if not strength:
        return []
    components = re.split(r'[+/]', strength)
    normalized = []
    for comp in components:
        comp = comp.strip().lower()
        match = re.match(r'(\d+(?:\.\d+)?)\s*(мг|мл|г|мкг|%)', comp, re.IGNORECASE)
        if match:
            normalized.append(f"{float(match.group(1))}{match.group(2).lower()}")
    normalized.sort()
    return normalized


def strength_match(s1: str, s2: str, tolerance: float = 0.01) -> bool:
    n1, n2 = normalize_strength(s1), normalize_strength(s2)
    if len(n1) != len(n2):
        return False
    for v1, v2 in zip(n1, n2):
        val1 = float(re.search(r'(\d+(?:\.\d+)?)', v1).group(1))
        val2 = float(re.search(r'(\d+(?:\.\d+)?)', v2).group(1))
        if not math.isclose(val1, val2, rel_tol=tolerance):
            return False
    return True


def extract_pack_size(text: str) -> Optional[str]:
    """Надёжно извлекает фасовку: №90, №21+7, №28х3, 60 шт"""
    # 1. Явный маркер № или N
    m = re.search(r'(?:№|N)\s*(\d+(?:[+хx]\d+)?)', text, re.IGNORECASE)
    if m:
        return f"№{m.group(1).lower().replace('х', 'x').replace('x', 'x')}"
    # 2. Число + единицы упаковки
    m = re.search(r'(\d+(?:[+хx]\d+)?)\s*(?:шт|таб|капс|кап|уп|амп|фл)', text, re.IGNORECASE)
    if m:
        return f"№{m.group(1).replace('х', 'x').replace('x', 'x')}"
    # 3. Число в конце строки
    m = re.search(r'\s(\d+)\s*$', text.strip())
    if m:
        return f"№{m.group(1)}"
    return None


def normalize_dosage_form(text: str) -> Optional[str]:
    t = text.lower()
    mapping = {
        r'таб': 'таблетки', r'капсул': 'капсулы', r'сироп': 'сироп',
        r'мазь|крем|гель': 'мазь/гель', r'р-р|раствор': 'раствор',
        r'суппозит|свеч': 'свечи', r'кап[л.и]': 'капли', r'порошок': 'порошок'
    }
    for pat, norm in mapping.items():
        if re.search(pat, t):
            return norm
    return None


def extract_ingredients(text: str) -> Set[str]:
    """Извлекает добавки. Жёстко фильтрует мусор и служебные слова."""
    if not text:
        return set()
    t = text.lower()
    ings = set()
    
    # Ищем паттерны: "с X, Y", "+X", "содержит X"
    for match in re.finditer(r'(?:с|со|содержит|\+)\s+([а-яёa-z0-9\s,+\-]+?)(?:\s+№|\s+таб|\s+капс|\s+мл|\s+г|\s+кап|\.|$)', t):
        parts = re.split(r'[,\s+и\s+]', match.group(1))
        for p in parts:
            p = p.strip()
            if len(p) > 2 and p not in {'модиф', 'высвоб', 'пленочн', 'оболочк', 'покрыт'}:
                ings.add(p)
    
    # Словарь известных веществ
    KNOWN = {'лютеин', 'зеаксантин', 'черника', 'хром', 'цинк', 'селен', 'магний', 
             'глицин', 'кальций', 'калий', 'железо', 'йод', 'омега', 'коллаген', 
             'биотин', 'коэнзим', 'карнитин', 'витамины группы в', 'vitamin b'}
    for k in KNOWN:
        if k in t:
            ings.add(k)
    return ings


def extract_brand(text: str) -> str:
    t = text.strip()
    match = re.match(r'^([^\d+\-№N]+?)\s*(?:\d|таб|капс|№|N|$)', t, re.IGNORECASE)
    if match:
        brand = match.group(1).strip().lower()
        words = [w for w in brand.split() if w not in {'для', 'при', 'от', 'с', 'и', 'в', 'на', 'со'}]
        return ' '.join(words[:2]) if words else ''
    return ''


def extract_all_attrs(text: str) -> Dict:
    return {
        'strength': extract_strength(text),
        'dosage_form': normalize_dosage_form(text),
        'pack_size': extract_pack_size(text),
        'ingredients': extract_ingredients(text),
        'brand': extract_brand(text)
    }
