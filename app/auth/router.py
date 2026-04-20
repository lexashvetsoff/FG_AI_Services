from fastapi import APIRouter, HTTPException, status
from app.config import settings
from app.schemas.schemas import TokenRequest, TokenResponse
from app.auth.jwt_handler import create_access_token


router = APIRouter(prefix='/v1/auth', tags=['Authentication'])


@router.post('/token', response_model=TokenResponse)
async def issue_token(request: TokenRequest):
    expected = settings.VALID_CLIENTS.get(request.client_id)
    if not expected or expected != request.client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid client credentials'
        )
    
    return TokenResponse(
        access_token=create_access_token(request.client_id),
        expire_in=settings.JWT_EXPIRE_MINUTES * 60
    )
