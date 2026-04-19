from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt_handler import verify_access_token


security = HTTPBearer()


async def get_current_client(credintials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = verify_access_token(credintials.credentials)
        return payload['sub']
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
