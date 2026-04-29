from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from app.config import settings


def create_access_token(client_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {'sub': client_id, 'exp': expire, 'iat': datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise ValueError(f'Invalid token: {e}')


def create_token_for_user(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode['exp'] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token_for_user(user_id: int) -> str:
    return (
        {'sub': str(user_id), 'type': 'access'},
        timedelta(minutes=settings.USER_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token_for_user(user_id: int) -> str:
    return create_token_for_user(
        {'sub': str(user_id), 'type': 'refresh'},
        timedelta(days=settings.USER_REFRESH_TOKEN_EXPIRE_DAYS)
    )
