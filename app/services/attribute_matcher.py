from typing import Optional, Dict
from app.schemas.schemas import PharmaSpecs
# from app.utils.pharma_parser import extract_strength, extract_pack_size, normalize_dosage_form
from app.utils.pharma_parser import extract_all_attrs, strength_match


class AttributeMatcher:
    """Вычисляет коэффициент коррекции (0.0 - 1.0) на основе совпадения фарм-атрибутов"""

    PENALTIES = {
        "strength": 0.50,      # Критично: разная дозировка = полупродукт/другой товар
        "dosage_form": 0.30,   # Важно: таблетки vs сироп
        "pack_size": 0.15      # Менее критично: №20 vs №30 (возможно аналог)
    }

    @staticmethod
    def _norm(val: str) -> str:
        return val.replace(' ', '').lower()
    
    def score(self, comp_name: str, ground_truth: Dict[str, Optional[str]]) -> float:
        multipler = 1.0
        comp_attrs = extract_all_attrs(comp_name)

        for key, penalty in self.PENALTIES.items():
            gt_val = ground_truth.get(key)
            if gt_val:  # Сравниваем только если атрибут найден в ground_truth
                comp_val = comp_attrs.get(key)

                if key == 'strength':
                    # Используем умное сравнение для дозировок
                    if comp_val and not strength_match(gt_val, comp_val):
                        multipler *= (1.0 - penalty)
                    elif not comp_val:
                        multipler *= 0.95
                else:
                    # Для формы и фасовки - простое сравнение
                    if comp_val and self._norm(gt_val) != self._norm(comp_val):
                        multipler *= (1.0 - penalty)
                    elif not comp_val:
                        multipler *= 0.95   # Атрибут не найден в конкуренте → лёгкий штраф
        return max(multipler, 0.1)

    # def score(self, comp_name: str, specs: Optional[PharmaSpecs]) -> float:
    #     if not specs:
    #         return 0.85  # Нейтральный множитель, если specs не переданы
        
    #     multipler = 1.0

    #     # 1. Дозировка
    #     if specs.strength:
    #         comp_str = extract_strength(comp_name)
    #         if comp_str and comp_str.replace(' ', '') != specs.strength.replace(' ', ''):
    #             multipler *= (1.0 - self.PENALTIES['strength'])
    #         elif not comp_str:
    #             multipler *= 0.95 # Не найдено, но не отвергаем
        
    #     # 2. Лекарственная форма
    #     if specs.dosage_form:
    #         comp_form = normalize_dosage_form(comp_name)
    #         if comp_form and comp_form != specs.dosage_form:
    #             multipler *= (1.0 - self.PENALTIES['dosage_form'])
        
    #     # 3. Фасовка
    #     if specs.pack_size:
    #         comp_pack = extract_pack_size(comp_name)
    #         clean_pack = specs.pack_size.replace(' ', '')
    #         if comp_pack and comp_pack.replace(' ', '') != clean_pack:
    #             multipler *= (1.0 - self.PENALTIES['pack_size'])
        
    #     return max(multipler, 0.1)
