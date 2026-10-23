from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.auth.dependencies import get_current_client
from app.services.property_extractor import (
    ExtractService,
    ClassExtractService,
    ClassifyerService,
    ClassifyerMNNService
)
from app.schemas.schemas import (
    ExtractRequest,
    ExtractResponse,
    ClassifyAndExtractRequest,
    ClassifyAndExtractResponse,
    ClassifyRequest,
    ClassifyResponse,
    MNNClassifyRequest,
    MNNClassifyResponse
)


router = APIRouter(prefix='/v1', tags=['Property Extract'])


async def get_service(request: Request) -> ExtractService:
    return request.app.state.extract_service


async def get_class_extract_service(request: Request) -> ClassExtractService:
    return request.app.state.class_extract_service


async def get_classifyer_service(request: Request) -> ClassifyerService:
    return request.app.state.classifyer_service


async def get_classifyer_mnn_service(request: Request) -> ClassifyerMNNService:
    return request.app.state.classifyer_mnn_service


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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Extract failed: {e}')


@router.post('/class_extract', response_model=ClassifyAndExtractResponse)
async def class_property_extract(
    request: ClassifyAndExtractRequest,
    service: ClassExtractService = Depends(get_class_extract_service),
    client: str = Depends(get_current_client)
):
    if not request.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Items list cannot be empty')
    if not request.categories:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Categories list cannot be empty')

    try:
        return await service.process(request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Extract failed: {e}')


@router.post('/classifyer', response_model=ClassifyResponse)
async def classifyer(
    request: ClassifyRequest,
    service: ClassifyerService = Depends(get_classifyer_service),
    client: str = Depends(get_current_client)
):
    try:
        return await service.process(request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Extract failed: {e}')


@router.post('/mnn_classifyer', response_model=MNNClassifyResponse)
async def mnn_classifyer(
    request: MNNClassifyRequest,
    service: ClassifyerMNNService = Depends(get_classifyer_mnn_service),
    client: str = Depends(get_current_client)
):
    if not request.dictionary:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Dictionary cannot be empty')

    try:
        return await service.process(request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Extract failed: {e}')
