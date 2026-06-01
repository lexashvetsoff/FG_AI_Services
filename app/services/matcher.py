import hashlib
import logging
import numpy as np
from app.config import settings
from app.services.cache import TTLCache
from app.ai.matcher.llm import LLMVerifier
from app.ai.matcher.embeddings import EmbeddingModel
from app.schemas.schemas import MatchRequest, MatchResponse
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
        comp_hash = hashlib.md5(" ".join(sorted(req.competitor_names)).encode()).hexdigest()
        return f'match:{req.internal_id or "anon"}:{comp_hash}'

    async def process(self, req: MatchRequest) -> MatchResponse:
        cache_key = self._get_cache_key(req)
        cached = self.cache.get(cache_key)
        if cached:
            return MatchResponse(**cached)
        
        # 1. Векторный скоринг
        vec_score, _, all_scores = self.embedder.score(req.internal_name, req.competitor_names)
        
        # 2. Ground Truth (приоритет pharma_specs, fallback на парсинг)
        gt = extract_all_attrs(req.internal_name)
        if req.pharma_specs:
            if req.pharma_specs.strength: gt['strength'] = req.pharma_specs.strength
            if req.pharma_specs.dosage_form: gt['dosage_form'] = req.pharma_specs.dosage_form
            # pack_count пересчитается автоматически из strength/form если нужно, но оставим как есть
            if req.pharma_specs.product_type: gt['product_type'] = req.pharma_specs.product_type

        # 3. Коррекция атрибутов
        attr_mults = [self.attr_matcher.score(c, gt) for c in req.competitor_names]
        corrected = [round(v * m, 3) for v, m in zip(all_scores, attr_mults)]
        
        best_idx = int(np.argmax(corrected))
        final_best = req.competitor_names[best_idx]
        final_score = corrected[best_idx]
        final_mult = attr_mults[best_idx]

        scores_map = {c: s for c, s in zip(req.competitor_names, corrected)}
        result_data = {}

        # 4. Роутинг
        # Если атрибуты сильно порезали скор (mult < 0.3) -> no_match сразу
        if final_mult < 0.3:
            result_data = {
                'internal_id': req.internal_id, 'request_id': req.request_id,
                'internal_name': req.internal_name, 'best_match': None,
                'confidence': round(final_score, 3),
                'reasoning': 'Критическое расхождение атрибутов (бренд, состав или дозировка).',
                'source': 'no_match', 'all_scores': scores_map
            }
        elif final_score < settings.THRESHOLD_HIGH:
            if final_score >= settings.THRESHOLD_LOW:
                llm_res = await self.llm.verify(req.internal_name, req.competitor_names, final_best, final_score, gt)
                result_data = {
                    'internal_id': req.internal_id, 'request_id': req.request_id,
                    'internal_name': req.internal_name, 'best_match': llm_res['best_match'],
                    'confidence': round(llm_res['confidence'], 3), 'reasoning': llm_res['reasoning'],
                    'source': llm_res['source'], 'all_scores': scores_map
                }
            else:
                result_data = {
                    'internal_id': req.internal_id, 'request_id': req.request_id,
                    'internal_name': req.internal_name, 'best_match': None,
                    'confidence': round(final_score, 3),
                    'reasoning': 'Низкая семантическая близость после коррекции атрибутами.',
                    'source': 'no_match', 'all_scores': scores_map
                }
        else:
            result_data = {
                'internal_id': req.internal_id, 'request_id': req.request_id,
                'internal_name': req.internal_name, 'best_match': final_best,
                'confidence': round(final_score, 3),
                'reasoning': 'Высокое совпадение (атрибуты подтверждены).',
                'source': 'vector_fast', 'all_scores': scores_map
            }
        
        self.cache.set(cache_key, result_data)
        return MatchResponse(**result_data)
