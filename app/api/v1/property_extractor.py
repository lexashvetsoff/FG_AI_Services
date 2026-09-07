from fastapi import APIRouter, Depends, HTTPException, Request
from app.schemas.schemas import ExtractRequest, ExtractResponse
from app.services.property_extractor import ExtractService
from app.auth.dependencies import get_current_client


router = APIRouter(prefix='/v1', tags=['Property Extract'])


async def get_service(request: Request) -> ExtractService:
    return request.app.state.extract_service


@router.post('/extract', response_model=ExtractResponse)
async def property_extract(
    request: ExtractRequest,
    service: ExtractService = Depends(get_service),
    client: str = Depends(get_current_client)
):
    try:
        result = await service.process(request)
        return ExtractResponse(
            status='Ok',
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Extract failed: {e}')

