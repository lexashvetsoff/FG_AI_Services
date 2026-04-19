import hashlib
import logging
import numpy as np
from app.config import settings
from app.services.cache import TTLCache
from app.models.llm import LLMVerifier
from app.models.embeddings import EmbeddingModel
from app.schemas import MatchRequest, MatchResponse
from app.utils.pharma_parser import extract_all_attrs
from app.services.attribute_matcher import AttributeMatcher


logger = logging.getLogger(__name__)


class MatcherService:
    def __init__(self, embedder: EmbeddingModel, llm: LLMVerifier, cache: TTLCache):
        self.embedder = embedder
        self.llm = llm
        self.cache = cache
        self.attr_matcher = AttributeMatcher()
    
    def _get_cache_key(self, req: MatchRequest) -> str:
        comp_hash = hashlib.md5("".join(sorted(req.competitor_names)).encode()).hexdigest()
        return f'match:{req.internal_id or 'anon'}:{comp_hash}'
    
    async def process(self, req: MatchRequest) -> MatchResponse:
        cache_key = self._get_cache_key(req)
        cached = self.cache.get(cache_key)
        if cached:
            logger.info('Get data from cache')
            return MatchResponse(**cached)
        
        # 1. Базовый векторный скор
        vec_score, best_vec, all_scores = self.embedder.score(req.internal_name, req.competitor_names)
        logger.info(f'Vector score: {vec_score:.3f} | Best: {best_vec} | req_id={req.request_id}')

        # 2. Определяем ground-truth атрибуты
        if req.pharma_specs:
            _strength = req.pharma_specs.strength
            _dosage_form = req.pharma_specs.dosage_form
            _pack_size = req.pharma_specs.pack_size
            
            gt_attrs = extract_all_attrs(req.internal_name)
            if _strength:
                gt_attrs['strength'] = _strength
            if _dosage_form:
                gt_attrs['dosage_form'] = _dosage_form
            if _pack_size:
                gt_attrs['pack_size'] = _pack_size
            
            # gt_attrs = {
            #     'strength': req.pharma_specs.strength,
            #     'dosage_form': req.pharma_specs.dosage_form,
            #     'pack_size': req.pharma_specs.pack_size
            # }
        else:
            gt_attrs = extract_all_attrs(req.internal_name)
        
        # 3. Коррекция скоринга атрибутами
        attr_multipliers = [self.attr_matcher.score(c, gt_attrs) for c in req.competitor_names]
        corrected_scores = [round(vs * am, 3) for vs, am in zip(all_scores, attr_multipliers)]

        # # 2. Коррекция атрибутами
        # specs = req.pharma_specs.model_dump(exclude_none=True) if req.pharma_specs else {}
        # attr_multipliers = []
        # corrected_scores = []

        # for comp_name in req.competitor_names:
        #     mult = self.attr_matcher.score(comp_name, req.pharma_specs)
        #     attr_multipliers.append(mult)
        
        # corrected_scores = [round(vs * am, 3) for vs, am in zip(all_scores, attr_multipliers)]
        
        best_idx = int(np.argmax(corrected_scores))
        final_best = req.competitor_names[best_idx]
        final_score = corrected_scores[best_idx]

        logger.info(
            f"Vec: {vec_score:.3f} | AttrMult: {attr_multipliers[best_idx]:.2f} | "
            f"Final: {final_score:.3f} | Best: {final_best} | req_id={req.request_id}"
        )

        scores_map = {c: s for c, s in zip(req.competitor_names, corrected_scores)}
        result_data = {}

        # 4. Роутинг с проверкой дозировки
        strength_mismatch = False
        if gt_attrs.get('strength'):
            comp_strength = extract_all_attrs(final_best).get('strength')
            if comp_strength:
                if self.attr_matcher._norm(gt_attrs['strength']) != self.attr_matcher._norm(comp_strength):
                    strength_mismatch = True

        # # 3. Роутинг с учётом атрибутов
        # # Если дозировка не совпала -> принудительно в LLM или no_match
        # strength_mismatch = False
        # if specs.get('strength'):
        #     if extract_strength(final_best) and extract_strength(final_best).replace(" ", "") != specs["strength"].replace(" ", ""):
        #         strength_mismatch = True
        
        if strength_mismatch or final_score < settings.THRESHOLD_HIGH:
            if final_score >= settings.THRESHOLD_LOW:
                # llm_res = await self.llm.verify(req.internal_name, req.competitor_names, final_best, final_score, specs)
                llm_res = await self.llm.verify(req.internal_name, req.competitor_names, final_best, final_score, gt_attrs)
                result_data = {
                    'internal_id': req.internal_id,
                    'request_id': req.request_id,
                    'internal_name': req.internal_name,
                    'best_match': llm_res['best_match'],
                    'confidence': round(llm_res['confidence'], 3),
                    'reasoning': llm_res['reasoning'],
                    'source': llm_res['source'],
                    'all_scores': scores_map
                }
            else:
                result_data = {
                    'internal_id': req.internal_id,
                    'request_id': req.request_id,
                    'internal_name': req.internal_name,
                    'best_match': None,
                    'confidence': round(final_score, 3),
                    'reasoning': 'Атрибуты (дозировка/форма) не совпадают или скор ниже порога.',
                    'source': 'no_match',
                    'all_scores': scores_map
                }
        else:
            result_data = {
                'internal_id': req.internal_id,
                'request_id': req.request_id,
                'internal_name': req.internal_name,
                'best_match': final_best,
                'confidence': round(final_score, 3),
                'reasoning': 'Высокое семантическое совпадение + подтверждение атрибутов',
                'source': 'vector_fast',
                'all_scores': scores_map
            }
        
        self.cache.set(cache_key, result_data)
        return MatchResponse(**result_data)
