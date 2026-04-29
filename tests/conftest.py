import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import httpx
import ollama

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import settings
from app.services.matcher import MatcherService
from app.ai.matcher.embeddings import EmbeddingModel
from app.ai.matcher.llm import LLMVerifier
from app.services.cache import TTLCache


# --- Конфигурация для тестов ---
# PARSER_OLLAMA_HOST = os.getenv("PARSER_OLLAMA_HOST", "http://127.0.0.1:11434")
# OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:27b") # Укажите вашу модель
TEST_TIMEOUT = 180  # Секунд на один тест с реальным LLM


@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для сессии тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def check_ollama_available():
    """Проверяет, запущен ли Ollama и доступна ли модель"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Проверяем здоровье сервиса
            resp = await client.get(f"{settings.PARSER_OLLAMA_HOST}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            
            # Ищем нужную модель (частичное совпадение имени)
            if not any(settings.PARSER_LLM_MODEL in name for name in model_names):
                pytest.skip(f"Model '{settings.PARSER_LLM_MODEL}' not found in Ollama. Available: {model_names}")
                
        return True
    except Exception as e:
        pytest.skip(f"Ollama not available at {settings.PARSER_OLLAMA_HOST}: {e}")


@pytest.fixture
async def matcher_service_real(check_ollama_available):
    """
    Фикстура с РЕАЛЬНЫМ LLM.
    Требует запущенного Ollama.
    """
    # 1. Загружаем эмбеддинги (локально, быстро)
    embedder = EmbeddingModel("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    # 2. Создаем реальный LLM клиент
    llm = LLMVerifier()
    # Переопределяем хост, если он отличается от дефолтного в конфиге
    llm._client = ollama.AsyncClient(host=settings.PARSER_OLLAMA_HOST)
    
    # 3. Кэш
    cache = TTLCache()
    
    service = MatcherService(embedder, llm, cache)
    yield service
    
    # Очистка (опционально)
    cache.clear()


@pytest.fixture
def matcher_service_mock():
    """Фикстура с МОКОВЫМ LLM (для быстрых тестов без GPU)"""
    embedder = EmbeddingModel("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    mock_llm = AsyncMock()
    # Умный мок: если скор высокий -> подтверждаем, иначе -> нет
    async def mock_verify(*args, **kwargs):
        vec_score = kwargs.get('vec_score', 0)
        best_match = kwargs.get('best_match')
        return {
            "best_match": best_match if vec_score > 0.7 else None,
            "confidence": vec_score,
            "reasoning": "Mocked",
            "source": "llm_fallback"
        }
    mock_llm.verify.side_effect = mock_verify
    
    cache = TTLCache()
    return MatcherService(embedder, mock_llm, cache)
