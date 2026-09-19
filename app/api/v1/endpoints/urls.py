from fastapi import APIRouter, Depends, HTTPException, Request, status
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.url import URL
from app.schemas.url import URLCreate, URLResponse
from app.services.cache_service import CacheService
from app.services.url_service import URLService

router = APIRouter()


def get_url_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> URLService:
    cache = CacheService(redis)
    return URLService(db=db, cache=cache)


@router.post(
    "/shorten",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shortened URL",
)
async def shorten_url(
    payload: URLCreate,
    request: Request,
    service: URLService = Depends(get_url_service),
) -> URLResponse:
    """Shortens a long URL with Base62 encoding or an optional custom alias."""
    url_record = await service.shorten_url(payload)
    base = settings.BASE_URL.rstrip("/")
    short_url = f"{base}/{url_record.short_code}"

    return URLResponse(
        short_code=url_record.short_code,
        short_url=short_url,
        original_url=url_record.original_url,
        created_at=url_record.created_at,
        expires_at=url_record.expires_at,
        click_count=url_record.click_count,
    )


@router.get(
    "/urls/{short_code}",
    response_model=URLResponse,
    summary="Get metadata for a shortened URL",
)
async def get_url_info(
    short_code: str,
    db: AsyncSession = Depends(get_db),
) -> URLResponse:
    """Returns metadata for a specific short URL code."""
    stmt = select(URL).where(URL.short_code == short_code)
    result = await db.execute(stmt)
    url_record = result.scalar_one_or_none()

    if not url_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"URL with code '{short_code}' not found.",
        )

    base = settings.BASE_URL.rstrip("/")
    return URLResponse(
        short_code=url_record.short_code,
        short_url=f"{base}/{url_record.short_code}",
        original_url=url_record.original_url,
        created_at=url_record.created_at,
        expires_at=url_record.expires_at,
        click_count=url_record.click_count,
    )


@router.delete(
    "/urls/{short_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a shortened URL",
)
async def delete_short_url(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    """Disables a short code and evicts it from the Redis cache."""
    stmt = select(URL).where(URL.short_code == short_code)
    result = await db.execute(stmt)
    url_record = result.scalar_one_or_none()

    if not url_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"URL with code '{short_code}' not found.",
        )

    url_record.is_active = False
    await db.commit()

    cache = CacheService(redis)
    await cache.invalidate_url(short_code)
