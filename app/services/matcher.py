import hashlib
import logging
import numpy as np
from app.config import settings
from app.services.cache import TTLCache
from app.ai.matcher.llm import LLMVerifier
from app.ai.matcher.embeddings import EmbeddingModel
from app.schemas.schemas import MatchRequest, MatchResponse
from app.utils.pharma_parser import extract_all_attrs, strength_match
from app.services.attribute_matcher import AttributeMatcher

logger = logging.getLogger(__name__)

class MatcherService:
    def __init__(self, embedder: EmbeddingModel, llm: LLMVerifier, cache: TTLCache):
        self.embedder = embedder
        self.llm = llm
        self.cache = cache
        self.attr_matcher = AttributeMatcher()

    def _get_cache_key(self, req: MatchRequest) -> str:
        comp_hash = hashlib.md5(" ".join(sorted(req.competitor_names)).encode()).hexdigest()
        return f'match:{req.internal_id or "anon"}:{comp_hash}'

    async def process(self, req: MatchRequest) -> MatchResponse:
        cache_key = self._get_cache_key(req)
        cached = self.cache.get(cache_key)
        if cached:
            logger.info(f'Cache HIT | req_id={req.request_id}')
            return MatchResponse(**cached)
        
        # 1. Базовый векторный скоринг
        vec_score, best_vec, all_scores = self.embedder.score(req.internal_name, req.competitor_names)
        logger.info(f'Vector score: {vec_score:.3f} | Best: {best_vec} | req_id={req.request_id}')

        # 2. Определяем ground-truth атрибуты
        if req.pharma_specs:
            gt_attrs = extract_all_attrs(req.internal_name)
            if req.pharma_specs.strength:
                gt_attrs['strength'] = req.pharma_specs.strength
            if req.pharma_specs.dosage_form:
                gt_attrs['dosage_form'] = req.pharma_specs.dosage_form
            if req.pharma_specs.pack_size:
                gt_attrs['pack_size'] = req.pharma_specs.pack_size
            gt_attrs['product_type'] = req.pharma_specs.product_type
        else:
            gt_attrs = extract_all_attrs(req.internal_name)
            gt_attrs['product_type'] = None

        # 3. Коррекция скоринга атрибутами
        attr_multipliers = [self.attr_matcher.score(c, gt_attrs) for c in req.competitor_names]
        corrected_scores = [round(vs * am, 3) for vs, am in zip(all_scores, attr_multipliers)]

        best_idx = int(np.argmax(corrected_scores))
        final_best = req.competitor_names[best_idx]
        final_score = corrected_scores[best_idx]
        final_mult = attr_multipliers[best_idx]

        logger.info(
            f"Vec: {vec_score:.3f} | AttrMult: {final_mult:.2f} | "
            f"Final: {final_score:.3f} | Best: {final_best} | req_id={req.request_id}"
        )

        scores_map = {c: s for c, s in zip(req.competitor_names, corrected_scores)}
        result_data = {}

        # 4. Роутинг
        if final_mult < 0.3:
            # Атрибуты сильно порезали скор → no_match
            result_data = {
                'internal_id': req.internal_id,
                'request_id': req.request_id,
                'internal_name': req.internal_name,
                'best_match': None,
                'confidence': round(final_score, 3),
                'reasoning': 'Критическое расхождение атрибутов (бренд, состав или дозировка).',
                'source': 'no_match',
                'all_scores': scores_map
            }
        elif final_score < settings.THRESHOLD_HIGH:
            if final_score >= settings.THRESHOLD_LOW:
                # LLM fallback
                llm_res = await self.llm.verify(
                    req.internal_name, 
                    req.competitor_names, 
                    final_best, 
                    final_score, 
                    gt_attrs
                )
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
                # Низкий скор → no_match
                result_data = {
                    'internal_id': req.internal_id,
                    'request_id': req.request_id,
                    'internal_name': req.internal_name,
                    'best_match': None,
                    'confidence': round(final_score, 3),
                    'reasoning': 'Низкая семантическая близость после коррекции атрибутами.',
                    'source': 'no_match',
                    'all_scores': scores_map
                }
        else:
            # Высокий скор + атрибуты ок → vector_fast
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
