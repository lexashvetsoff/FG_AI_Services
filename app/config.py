import json
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    APP_NAME: str = "Pharma Matcher API"
    APP_VERSION: str = "0.1.0"
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str
    PARSER_EMBED_MODEL: str = "sergeyzh/LaBSE-ru-sts"
    PARSER_LLM_MODEL: str = "qwen2.5:14b"
    PARSER_OLLAMA_HOST: str = "http://127.0.0.1:11434"
    ANALYST_LLM_MODEL: str = 'gemma4:e4b'
    ANALYST_OLLAMA_HOST: str = 'http://10.10.22.201:11434'
    OLLAMA_TIMEOUT: int = 30
    THRESHOLD_HIGH: float = 0.82
    THRESHOLD_LOW: float = 0.60
    CACHE_TTL: int = 7200
    LOG_LEVEL: str = "INFO"
    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int
    VALID_CLIENTS: dict = {}
    INITIAL_ADMIN_EMAIL: str | None = None
    INITIAL_ADMIN_PASSWORD: str | None = None
    USER_ACCESS_TOKEN_EXPIRE_MINUTES: int
    USER_REFRESH_TOKEN_EXPIRE_DAYS: int
    STORAGE_ROOT: str = 'app/storage'

    @field_validator("VALID_CLIENTS", mode="before")
    @classmethod
    def _parse_clients(cls, v):
        if isinstance(v, str):
            try: return json.loads(v)
            except json.JSONDecodeError: return {}
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
