from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.url import URL
from app.schemas.url import URLCreate
from app.services.base62 import id_to_short_code
from app.services.cache_service import CacheService


def parse_user_agent(user_agent: Optional[str]) -> Tuple[str, str]:
    """Extract browser and operating system from User-Agent string."""
    if not user_agent:
        return "Unknown", "Unknown"

    ua = user_agent.lower()

    # Browser detection
    if "edg/" in ua:
        browser = "Edge"
    elif "chrome/" in ua and "chromium/" not in ua:
        browser = "Chrome"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "safari/" in ua and "chrome/" not in ua:
        browser = "Safari"
    elif "opera" in ua or "opr/" in ua:
        browser = "Opera"
    elif "curl" in ua:
        browser = "cURL"
    elif "python" in ua or "locust" in ua:
        browser = "Benchmark/Bot"
    else:
        browser = "Other"

    # OS detection
    if "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "android" in ua:
        os_name = "Android"
    elif "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Other"

    return browser, os_name


class URLService:
    def __init__(self, db: AsyncSession, cache: CacheService):
        self.db = db
        self.cache = cache

    async def shorten_url(self, payload: URLCreate) -> URL:
        """Create a shortened URL entry and warm the Redis cache."""
        now = datetime.now(timezone.utc)
        expires_at = None
        if payload.expires_in_days:
            expires_at = now + timedelta(days=payload.expires_in_days)

        original_url = str(payload.url)

        if payload.custom_alias:
            alias = payload.custom_alias.strip()
            # Check for collision
            stmt = select(URL).where(URL.short_code == alias)
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Custom alias '{alias}' is already in use. Please choose another.",
                )

            url_record = URL(
                short_code=alias,
                original_url=original_url,
                created_at=now,
                expires_at=expires_at,
                is_active=True,
            )
            self.db.add(url_record)
            await self.db.commit()
            await self.db.refresh(url_record)
        else:
            # Insert first to get auto-incrementing ID
            url_record = URL(
                short_code="",  # temporary placeholder
                original_url=original_url,
                created_at=now,
                expires_at=expires_at,
                is_active=True,
            )
            self.db.add(url_record)
            await self.db.flush()

            # Encode auto-increment ID to unique Base62 short code
            generated_code = id_to_short_code(url_record.id)
            url_record.short_code = generated_code
            await self.db.commit()
            await self.db.refresh(url_record)

        # Calculate cache TTL based on expiration
        ttl = settings.CACHE_TTL_SECONDS
        if expires_at:
            remaining_seconds = int((expires_at - now).total_seconds())
            ttl = max(1, min(remaining_seconds, settings.CACHE_TTL_SECONDS))

        # Warm Redis cache
        await self.cache.set_url(url_record.short_code, url_record.original_url, ttl_seconds=ttl)

        return url_record

    async def resolve_url(
        self,
        short_code: str,
        client_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Ultra-fast redirect lookup:
        1. Query Redis (<1ms).
        2. On cache miss, fall back to PostgreSQL and re-warm Redis.
        3. Emit async click event to Redis for background processing.
        """
        cached_url = await self.cache.get_url(short_code)
        target_url: Optional[str] = cached_url

        if not target_url:
            # Cache miss -> Query DB
            stmt = select(URL).where(
                URL.short_code == short_code,
                URL.is_active.is_(True),
            )
            result = await self.db.execute(stmt)
            url_record = result.scalar_one_or_none()

            if not url_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Short URL not found or has been disabled.",
                )

            # Check expiration
            if url_record.expires_at and url_record.expires_at < datetime.now(timezone.utc):
                url_record.is_active = False
                await self.db.commit()
                await self.cache.invalidate_url(short_code)
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="This short URL has expired.",
                )

            target_url = url_record.original_url

            # Re-warm cache
            ttl = settings.CACHE_TTL_SECONDS
            if url_record.expires_at:
                remaining = int((url_record.expires_at - datetime.now(timezone.utc)).total_seconds())
                ttl = max(1, min(remaining, settings.CACHE_TTL_SECONDS))
            await self.cache.set_url(short_code, target_url, ttl_seconds=ttl)

        # Asynchronously queue click analytics event without blocking redirect
        if client_metadata:
            browser, os_name = parse_user_agent(client_metadata.get("user_agent"))
            event = {
                "short_code": short_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ip_address": client_metadata.get("ip_address"),
                "referrer": client_metadata.get("referrer"),
                "user_agent": client_metadata.get("user_agent"),
                "browser": browser,
                "os": os_name,
            }
            await self.cache.emit_click_event(event)

        return target_url
