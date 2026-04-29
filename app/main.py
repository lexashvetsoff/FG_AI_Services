import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.core.bootstrap import create_initial_admin
from app.ai.matcher.embeddings import EmbeddingModel
from app.ai.matcher.llm import LLMVerifier
from app.services.cache import TTLCache
from app.services.matcher import MatcherService
from app.api.v1.matcher import router as matcher_router
from app.api.v1.competitor_analysis import router as analysis_router
from app.auth.router import router as auth_router
from app.ui.router import router as ui_router
from app.admin.router import router as admin_router
from app.user.router import router as user_router


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

    async with AsyncSessionLocal() as session:
        await create_initial_admin(session)
    
    embedder = EmbeddingModel(settings.PARSER_EMBED_MODEL)
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

    app.mount('/static', StaticFiles(directory='app/static'), name='static')
    app.mount('/storage', StaticFiles(directory=settings.STORAGE_ROOT), name='storage')

    @app.get('/health', tags=['System'])
    def health_check():
        return {'status': 'ok'}
    
    app.include_router(ui_router)
    app.include_router(matcher_router)
    app.include_router(analysis_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(user_router)
    return app


app = create_app()
