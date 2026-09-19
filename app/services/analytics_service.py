from datetime import datetime, timedelta, timezone
from typing import Dict, List
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import ClickEvent
from app.models.url import URL
from app.schemas.analytics import AnalyticsSummary, ClickEventDetail


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, short_code: str) -> AnalyticsSummary:
        """Aggregate real-time click statistics for a short URL."""
        # 1. Fetch URL info
        stmt_url = select(URL).where(URL.short_code == short_code)
        res_url = await self.db.execute(stmt_url)
        url_record = res_url.scalar_one_or_none()

        if not url_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"URL with code '{short_code}' not found.",
            )

        # 2. Total clicks
        stmt_total = select(func.count(ClickEvent.id)).where(ClickEvent.short_code == short_code)
        res_total = await self.db.execute(stmt_total)
        total_clicks = res_total.scalar_one() or 0

        # 3. Clicks last 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt_24h = select(func.count(ClickEvent.id)).where(
            ClickEvent.short_code == short_code,
            ClickEvent.timestamp >= cutoff,
        )
        res_24h = await self.db.execute(stmt_24h)
        clicks_24h = res_24h.scalar_one() or 0

        # 4. Top Referrers
        stmt_ref = (
            select(
                func.coalesce(ClickEvent.referrer, "Direct").label("referrer"),
                func.count(ClickEvent.id).label("cnt"),
            )
            .where(ClickEvent.short_code == short_code)
            .group_by("referrer")
            .order_by(desc("cnt"))
            .limit(5)
        )
        res_ref = await self.db.execute(stmt_ref)
        top_referrers: Dict[str, int] = {row[0]: row[1] for row in res_ref.all()}

        # 5. Top Browsers
        stmt_browser = (
            select(
                func.coalesce(ClickEvent.browser, "Unknown").label("browser"),
                func.count(ClickEvent.id).label("cnt"),
            )
            .where(ClickEvent.short_code == short_code)
            .group_by("browser")
            .order_by(desc("cnt"))
            .limit(5)
        )
        res_browser = await self.db.execute(stmt_browser)
        top_browsers: Dict[str, int] = {row[0]: row[1] for row in res_browser.all()}

        # 6. Top OS
        stmt_os = (
            select(
                func.coalesce(ClickEvent.os, "Unknown").label("os"),
                func.count(ClickEvent.id).label("cnt"),
            )
            .where(ClickEvent.short_code == short_code)
            .group_by("os")
            .order_by(desc("cnt"))
            .limit(5)
        )
        res_os = await self.db.execute(stmt_os)
        top_os: Dict[str, int] = {row[0]: row[1] for row in res_os.all()}

        # 7. Recent 10 clicks
        stmt_recent = (
            select(ClickEvent)
            .where(ClickEvent.short_code == short_code)
            .order_by(desc(ClickEvent.timestamp))
            .limit(10)
        )
        res_recent = await self.db.execute(stmt_recent)
        recent_clicks = [
            ClickEventDetail(
                timestamp=event.timestamp,
                ip_address=event.ip_address,
                referrer=event.referrer,
                browser=event.browser,
                os=event.os,
                country=event.country,
            )
            for event in res_recent.scalars().all()
        ]

        return AnalyticsSummary(
            short_code=short_code,
            original_url=url_record.original_url,
            total_clicks=total_clicks,
            clicks_last_24h=clicks_24h,
            top_referrers=top_referrers,
            top_browsers=top_browsers,
            top_os=top_os,
            recent_clicks=recent_clicks,
        )
