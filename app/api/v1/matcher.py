from fastapi import APIRouter, Depends, HTTPException, Request
from app.schemas.schemas import MatchRequest, MatchResponse
from app.services.matcher import MatcherService
from app.auth.dependencies import get_current_client


router = APIRouter(prefix='/v1', tags=['Matching'])


async def get_service(request: Request) -> MatcherService:
    return request.app.state.matcher_service


@router.post('/match', response_model=MatchResponse)
async def match_names(
    req: MatchRequest,
    service: MatcherService = Depends(get_service),
    client_id: str = Depends(get_current_client)
):
    try:
        return await service.process(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Matching failed: {str(e)}')


@router.get('/health_matching')
async def health():
    from app.config import settings
    return {'status': 'ok', 'embed_model': settings.EMBED_MODEL, 'llm_model': settings.LLM_MODEL}
