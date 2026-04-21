import json
import ollama
import logging
from app.config import settings


logger = logging.getLogger(__name__)


class LLMVerifier:
    def __init__(self):
        self._client = ollama.AsyncClient(host=settings.OLLAMA_HOST)
    
    async def verify(self, internal_name: str, candidates: list[str],
                     best_match: str, vec_score: float, specs: dict) -> dict:
        context = [f'{k.replace('_', ' ').capitalize()}: {v}' for k, v in specs.items() if v]

        # sys_prompt = (
        #     "Ты эксперт по фармацевтическому ассортименту. Векторный анализ дал среднее совпадение. "
        #     "Проверь, является ли выбранный вариант полным аналогом. Учитывай МНН, дозировку, форму и тип. "
        #     "БАД ≠ ЛС, разная дозировка ≠ аналог. Верни ТОЛЬКО валидный JSON: "
        #     "{\"best_match\": \"строка или null\", \"confidence\": 0.0-1.0, \"reasoning\": \"1-2 предложения\"}"
        # )
        sys_prompt = (
            "Ты эксперт по фармацевтическому ассортименту. Векторный анализ дал среднее совпадение. "
            "Проверь, является ли выбранный вариант полным аналогом. Учитывай МНН, дозировку, форму и тип. "
            "БАД ≠ ЛС, разная дозировка ≠ аналог.\n\n"
            "Определи confidence (0.0–1.0) строго по правилам:\n"
            "- 1.0: полное совпадение по МНН, дозировке, форме выпуска и типу (оба ЛС, не БАД).\n"
            "- 0.7: совпадает МНН и форма, но дозировка отличается (например, 500 мг vs 250 мг).\n"
            "- 0.5: совпадает МНН, но форма или тип разные (таблетки vs капсулы, или ЛС vs БАД).\n"
            "- 0.2: только частичное совпадение (например, одно и то же действующее вещество, но разные соли/эфиры).\n"
            "- 0.0: не аналог (разное МНН, или БАД вместо ЛС, или критическое расхождение).\n\n"
            "Верни ТОЛЬКО валидный JSON:\n"
            "{\"best_match\": \"строка или null\", \"confidence\": 0.0-1.0, \"reasoning\": \"1-2 предложения с обоснованием\"}"
        )
        user_prompt = (
            f"{' | '.join(context)}\n\n"
            f"Наше: \"{internal_name}\"\n"
            f"Кандидаты:\n" + "\n".join(f"- {c}" for c in candidates) + "\n"
            f"Векторный фаворит: \"{best_match}\" (score: {vec_score:.3f})\n"
            "Подтверди или отклони выбор."
        )

        try:
            resp = await self._client.chat(
                model=settings.LLM_MODEL,
                messages=[{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': user_prompt}],
                options={'temperature': 0.1, 'num_ctx': 2048},
                format='json'
            )
            parsed = json.loads(resp['message']['content'].strip())
            return {
                'best_match': parsed.get('best_match'),
                'confidence': float(parsed.get('confidence', 0.5)),
                'reasoning': parsed.get('reasoning', 'LLM верификация'),
                'source': 'llm_fallback'
            }
        except Exception as e:
            logger.error(f'LLM fallback failed: {e}')
            return {
                'best_match': best_match,
                'confidence': max(vec_score - 0.15, 0.0),
                'reasoning': 'Ошибка верификации, применён векторный результат со штрафом',
                'source': 'vector_degraded'
            }
