import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.config import settings
from app.services.competitor_alnalysis.llm_service import LLMService
from app.api.dependencies import get_db, get_current_user
from app.schemas.schemas import ChatRequest
from app.core.templates import templates
from app.models.competitor_analysis import LLMReport
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
    # report = await service.generate_report(import_id)
    reports = await service.generate_reports(db, import_id)
    summary_report = await service.generate_summary_report(db, import_id, reports)
    segments = [r['segment'] for r in reports]

    return templates.TemplateResponse(
        '/user/competitors/report.html',
        {
            'request': request,
            'user': user,
            'reports': reports,
            'segments': segments,
            'summary_report': summary_report['html']
        }
    )


@router.post('/chat')
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = LLMService(db)
    answer = await service.chat(
        import_id=request.import_id,
        question=request.question
    )

    return {'answer': answer}


@router.get('/heatmap')
async def get_heatmap(
    import_id: str,
    segment: str,
    db: AsyncSession = Depends(get_db)
):
    query = text("""
SELECT
    city,
    AVG(diff_pct) AS avg_diff_pct
FROM pair_price_metrics
WHERE import_id = :import_id
    AND price_segment = :segment
GROUP BY city
ORDER BY city
""")
    
    result = await db.execute(
        query,
        {
            'import_id': import_id,
            'segment': segment
        }
    )

    return [dict(r._mapping) for r in result]


@router.get('/city_details')
async def get_city_details(
    import_id: str,
    city: str,
    segment: str,
    db: AsyncSession = Depends(get_db)
):
    query = text("""
SELECT
    our_pharmacy_instance,
    competitor_pharmacy_instance,
    AVG(diff_pct) AS avg_diff_pct
FROM pair_price_metrics
WHERE import_id = :import_id
    AND city = :city
    AND price_segment = :segment
GROUP BY our_pharmacy_instance, competitor_pharmacy_instance
ORDER BY avg_diff_pct DESC
LIMIT 50
""")
    
    result = await db.execute(
        query,
        {
            'import_id': import_id,
            'city': city,
            'segment': segment
        }
    )

    return [dict(r._mapping) for r in result]


@router.get('/chart')
async def get_chart(
    import_id: str,
    segment: str,
    db: AsyncSession = Depends(get_db)
):
    query = text("""
SELECT
    pharmacy_name,
    AVG(price_index) as price_index
FROM competitor_metrics
WHERE import_id = :import_id
    AND price_segment = :segment
    AND pharmacy_name LIKE 'ФГ%'
GROUP BY pharmacy_name
ORDER BY price_index DESC

""")
    
    result = await db.execute(
        query,
        {
            'import_id': import_id,
            'segment': segment
        }
    )

    return [dict(r._mapping) for r in result]


@router.get('/health_analisis')
async def health():
    from app.config import settings
    return {'status': 'ok', 'llm_model': settings.ANALYST_LLM_MODEL}
