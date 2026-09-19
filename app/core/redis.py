from typing import AsyncGenerator
import redis.asyncio as aioredis
from app.core.config import settings

# Global connection pool for Redis to minimize connection handshake latency
redis_pool: aioredis.ConnectionPool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=settings.REDIS_POOL_MAX_CONNECTIONS,
    decode_responses=True,
)


def get_redis_client() -> aioredis.Redis:
    """Returns an async Redis client backed by the global connection pool."""
    return aioredis.Redis(connection_pool=redis_pool)


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency for accessing Redis client."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()


async def check_redis_health() -> bool:
    """Ping Redis to verify connectivity."""
    client = get_redis_client()
    try:
        return await client.ping()
    except Exception:
        return False
    finally:
        await client.aclose()


async def close_redis_pool() -> None:
    """Closes Redis connection pool cleanly during application shutdown."""
    await redis_pool.disconnect()
