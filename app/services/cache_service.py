import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    def _url_key(self, short_code: str) -> str:
        return f"url:{short_code}"

    async def get_url(self, short_code: str) -> Optional[str]:
        """Fetch cached long URL by short code (<1ms lookup)."""
        try:
            return await self.redis.get(self._url_key(short_code))
        except Exception as e:
            logger.warning(f"Redis get failed for code {short_code}: {e}")
            return None

    async def set_url(
        self,
        short_code: str,
        original_url: str,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Cache original URL for short code with TTL."""
        try:
            ttl = ttl_seconds if ttl_seconds is not None else settings.CACHE_TTL_SECONDS
            await self.redis.set(self._url_key(short_code), original_url, ex=ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis set failed for code {short_code}: {e}")
            return False

    async def invalidate_url(self, short_code: str) -> bool:
        """Evict URL from cache."""
        try:
            await self.redis.delete(self._url_key(short_code))
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed for code {short_code}: {e}")
            return False

    async def emit_click_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Emits a click event payload asynchronously to Redis queue.
        Keeps redirect response path decoupled and sub-10ms.
        """
        try:
            payload = json.dumps(event_data)
            await self.redis.lpush(settings.CLICK_STREAM_KEY, payload)
            return True
        except Exception as e:
            logger.error(f"Failed to queue click event to Redis: {e}")
            return False
