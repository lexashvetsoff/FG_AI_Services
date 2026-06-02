import logging
from typing import Dict, Optional
from app.utils.pharma_parser import extract_all_attrs, strength_match

logger = logging.getLogger(__name__)

class AttributeMatcher:
    PENALTIES = {
        'strength': 0.50,
        'dosage_form': 0.30,
        'pack_size': 0.15,
        'ingredients': 0.40,
        'brand': 0.80
    }
    
    SOFT_PENALTIES = {
        'strength': 0.95,
        'dosage_form': 0.95,
        'pack_size': 0.95,
        'ingredients': 0.90,
        'brand': 0.90
    }

    @staticmethod
    def _norm(val: str) -> str:
        return val.replace(' ', '').lower() if val else ''

    def score(self, comp_name: str, gt: Dict) -> float:
        if not gt:
            return 1.0
        
        comp = extract_all_attrs(comp_name)
        mult = 1.0
        applied_penalties = []

        # 1. БРЕНД
        gt_brand, comp_brand = gt.get('brand'), comp.get('brand')
        if gt_brand and comp_brand:
            b1, b2 = self._norm(gt_brand), self._norm(comp_brand)
            if b1 not in b2 and b2 not in b1:
                mult *= (1.0 - self.PENALTIES['brand'])
                applied_penalties.append(f"brand({gt_brand}!={comp_brand})")
        elif gt_brand and not comp_brand:
            mult *= self.SOFT_PENALTIES['brand']
            applied_penalties.append("brand_missing")

        # 2. ИНГРЕДИЕНТЫ
        gt_ings, comp_ings = gt.get('ingredients', set()), comp.get('ingredients', set())
        if gt_ings and comp_ings:
            missing = gt_ings - comp_ings
            critical = {i for i in missing if 'vitamin' not in i and len(i) > 3}
            if critical:
                mult *= (1.0 - self.PENALTIES['ingredients'])
                applied_penalties.append(f"ingredients({critical})")
        elif gt_ings and not comp_ings:
            mult *= self.SOFT_PENALTIES['ingredients']
            applied_penalties.append("ingredients_missing")

        # 3. ДОЗИРОВКА
        gt_str, comp_str = gt.get('strength'), comp.get('strength')
        if gt_str and comp_str:
            if not strength_match(gt_str, comp_str):
                mult *= (1.0 - self.PENALTIES['strength'])
                applied_penalties.append(f"strength({gt_str}!={comp_str})")
        elif gt_str and not comp_str:
            mult *= self.SOFT_PENALTIES['strength']
            applied_penalties.append("strength_missing")

        # 4. ФАСОВКА
        gt_pack, comp_pack = gt.get('pack_size'), comp.get('pack_size')
        if gt_pack and comp_pack:
            g = self._norm(gt_pack).replace('№', '')
            c = self._norm(comp_pack).replace('№', '')
            if g != c:
                mult *= (1.0 - self.PENALTIES['pack_size'])
                applied_penalties.append(f"pack_size({g}!={c})")
        elif gt_pack and not comp_pack:
            mult *= self.SOFT_PENALTIES['pack_size']
            applied_penalties.append("pack_size_missing")

        # 5. ФОРМА
        gt_form, comp_form = gt.get('dosage_form'), comp.get('dosage_form')
        if gt_form and comp_form:
            if self._norm(gt_form) != self._norm(comp_form):
                mult *= (1.0 - self.PENALTIES['dosage_form'])
                applied_penalties.append(f"dosage_form({gt_form}!={comp_form})")
        elif gt_form and not comp_form:
            mult *= self.SOFT_PENALTIES['dosage_form']
            applied_penalties.append("dosage_form_missing")

        # 🔍 DEBUG LOG: покажет, что именно срезало скор
        if applied_penalties:
            logger.info(f"AttrPenalties for '{comp_name[:40]}...': {applied_penalties} | Mult: {mult:.3f}")

        return max(mult, 0.1)
