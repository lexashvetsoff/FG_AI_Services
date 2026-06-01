from typing import Dict, Optional
from app.utils.pharma_parser import extract_all_attrs


class AttributeMatcher:
    """Вычисляет коэффициент коррекции на основе строгих правил фарм-матчинга"""
    
    @staticmethod
    def _norm(val: str) -> str:
        return val.replace(' ', '').lower() if val else ''

    def score(self, comp_name: str, gt: Dict) -> float:
        if not gt: return 1.0
        
        comp = extract_all_attrs(comp_name)
        mult = 1.0

        # 1. БРЕНД/МНН ЯКОРЬ. Если бренд не совпадает -> критический штраф
        if gt.get('brand') and comp.get('brand'):
            # Нечёткое сравнение брендов (допускаем опечатки/сокращения)
            if gt['brand'] not in comp['brand'] and comp['brand'] not in gt['brand']:
                mult *= 0.15  # Практически отсекаем

        # 2. ИНГРЕДИЕНТЫ. Строго: если у нас есть "Магний", у конкурента должен быть
        gt_ings = gt.get('ingredients', set())
        comp_ings = comp.get('ingredients', set())
        if gt_ings and comp_ings:
            missing = gt_ings - comp_ings
            # Игнорируем "vitamin b" как менее критичный, остальные важны
            critical_missing = {i for i in missing if 'vitamin' not in i and len(i) > 3}
            if critical_missing:
                mult *= 0.25  # Жёсткий штраф за отсутствие ключевого вещества

        # 3. ДОЗИРОВКА. Разрешаем вхождение (15мг matches 15мг+153.5мг)
        gt_str = gt.get('strength')
        comp_str = comp.get('strength')
        if gt_str and comp_str:
            g = self._norm(gt_str)
            c = self._norm(comp_str)
            # Если ядро дозировки совпадает или содержится внутри -> ок
            if not (g in c or c in g):
                mult *= 0.40
        elif gt_str and not comp_str:
            mult *= 0.85  # Мягкий штраф, если у конкурента вообще не указана

        # 4. ФАСОВКА. Сравниваем абсолютные числа. Г/МЛ считаем равными для гелей/жидкостей
        gt_pack = gt.get('pack_count')
        comp_pack = comp.get('pack_count')
        if gt_pack and comp_pack:
            if gt_pack != comp_pack:
                mult *= 0.60  # Штраф за разное количество
        elif gt_pack and not comp_pack:
            mult *= 0.90

        # 5. ФОРМА. Допускаем вариации (таб.п.о. -> таблетки)
        gt_form = gt.get('dosage_form')
        comp_form = comp.get('dosage_form')
        if gt_form and comp_form:
            if self._norm(gt_form) != self._norm(comp_form):
                mult *= 0.75

        return max(mult, 0.05)
