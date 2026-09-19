from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis

router = APIRouter()


@router.get("", summary="Liveness and Readiness Health Check")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Checks connection pools for both PostgreSQL and Redis.
    Essential for load balancers (Nginx / AWS ALB) to determine instance health.
    """
    db_ok = False
    redis_ok = False

    # Check DB
    try:
        res = await db.execute(text("SELECT 1"))
        db_ok = res.scalar() == 1
    except Exception:
        db_ok = False

    # Check Redis
    try:
        redis_ok = await redis.ping()
    except Exception:
        redis_ok = False

    is_healthy = db_ok and redis_ok
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "degraded",
            "environment": settings.ENVIRONMENT,
            "services": {
                "database": "connected" if db_ok else "disconnected",
                "redis": "connected" if redis_ok else "disconnected",
            },
        },
    )
