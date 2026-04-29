from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.services.competitor_alnalysis.llm_service import LLMService
from app.api.dependencies import get_db, get_current_user
from app.core.templates import templates
from app.models.user import User


router = APIRouter(prefix='/v1', tags=['Competitor Analysis'])


@router.get('/{import_id}/report', response_class=HTMLResponse)
async def get_report(
    request: Request,
    import_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = LLMService(db)
    report = await service.generate_report(import_id)

    return templates.TemplateResponse(
        '/user/competitors/report.html',
        {
            'request': request,
            'user': user,
            'report': report
        }
    )


@router.get('/health_analisis')
async def health():
    from app.config import settings
    return {'status': 'ok', 'llm_model': settings.ANALYST_LLM_MODEL}
