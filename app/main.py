import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.ai.matcher.embeddings import EmbeddingModel
from app.ai.matcher.llm import LLMVerifier
from app.services.cache import TTLCache
from app.services.matcher import MatcherService
from app.api.v1.matcher import router as api_router
from app.auth.router import router as auth_router


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logging.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logging.info("⏳ Initializing models...")
    embedder = EmbeddingModel(settings.EMBED_MODEL)
    llm = LLMVerifier()
    cache = TTLCache(settings.CACHE_TTL)
    service = MatcherService(embedder, llm, cache)
    app.state.matcher_service = service
    logging.info("✅ Models loaded. Service ready.")

    yield

    logging.info("👋 Shutting down application")


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan
    )
    app.include_router(api_router)
    app.include_router(auth_router)
    return app


app = create_app()
