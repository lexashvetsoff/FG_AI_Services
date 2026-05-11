import logging
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.config import settings
from app.services.competitor_alnalysis.llm_service import LLMService
from app.api.dependencies import get_db, get_current_user
from app.schemas.schemas import ChatRequest, ChatRequestContext
from app.core.templates import templates
from app.utils.competitor_analysis_utils import ReportGenerationStatus
from app.models.competitor_analysis import LLMReport, ImportReport
from app.models.user import User


router = APIRouter(prefix='/v1', tags=['Competitor Analysis'])


# @router.get('/{import_id}/report', response_class=HTMLResponse)
# async def get_report(
#     request: Request,
#     import_id: str,
#     db: AsyncSession = Depends(get_db),
#     user: User = Depends(get_current_user)
# ):
#     service = LLMService(db)
#     # report = await service.generate_report(import_id)
#     reports = await service.generate_reports(db, import_id)
#     summary_report = await service.generate_summary_report(db, import_id, reports)
#     segments = [r['segment'] for r in reports]

#     return templates.TemplateResponse(
#         '/user/competitors/report.html',
#         {
#             'request': request,
#             'user': user,
#             'reports': reports,
#             'segments': segments,
#             'summary_report': summary_report['html']
#         }
#     )


@router.get('/{import_id}/report', response_class=HTMLResponse)
async def get_report(
    request: Request,
    import_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # 1. Проверяем существование записи в import_reports
    result = await db.execute(select(ImportReport).where(ImportReport.import_id == import_id))
    report_record = result.scalar_one_or_none()

    llm_service = LLMService(db)

    if report_record and report_record.status == ReportGenerationStatus.ready:
        # Отчёт готов – отдаём страницу с результатом
        reports = await llm_service.generate_reports(db, import_id)
        summary_report = await llm_service.generate_summary_report(db, import_id, reports)
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
    elif report_record and report_record.status == ReportGenerationStatus.processing:
        # Отчёт генерируется – страница ожидания
        return templates.TemplateResponse(
            '/user/competitors/loading.html',
            {
                'request': request,
                'user': user,
                'import_id': import_id
            }
        )
    elif report_record and report_record.status == ReportGenerationStatus.failed:
        # Ошибка генерации
        return templates.TemplateResponse(
            '/user/competitors/error.html',
            {
                'request': request,
                'user': user,
                'error': report_record.error_message
            }
        )
    else:
        # Нет записи или статус pending – запускаем генерацию
        await llm_service.start_background_generation(import_id, background_tasks)
        return templates.TemplateResponse(
            '/user/competitors/loading.html',
            {
                'request': request,
                'user': user,
                'import_id': import_id
            }
        )


@router.get('/{import_id}/report/status')
async def report_status(
    import_id: str,
    db: AsyncSession = Depends(get_db)
):
    llm_service = LLMService(db)
    status = await llm_service.get_report_generation_status(import_id)
    return status


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


@router.post('/chat_context')
async def chat_context(
    request: ChatRequestContext,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = LLMService(db)
    answer = await service.chat(
        import_id=request.import_id,
        question=request.question,
        extra=request.extra
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
