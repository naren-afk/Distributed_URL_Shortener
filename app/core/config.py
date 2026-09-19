from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General
    PROJECT_NAME: str = "Distributed URL Shortener"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    BASE_URL: str = "http://localhost"

    # PostgreSQL Database Connection & Pooling
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/urlshortener"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # Redis Cache & Stream
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 86400  # 24 hours
    CLICK_STREAM_KEY: str = "url:click_stream"
    REDIS_POOL_MAX_CONNECTIONS: int = 50

    # Background Analytics Worker
    WORKER_BATCH_SIZE: int = 50
    WORKER_POLL_INTERVAL: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
