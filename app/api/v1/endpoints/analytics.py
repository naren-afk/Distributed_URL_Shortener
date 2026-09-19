from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.analytics import AnalyticsSummary
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get(
    "/{short_code}",
    response_model=AnalyticsSummary,
    summary="Get real-time analytics for a shortened URL",
)
async def get_analytics(
    short_code: str,
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummary:
    """
    Returns aggregated click metrics including total clicks, 24-hour clicks,
    top referrers, browser breakdown, OS breakdown, and recent click logs.
    """
    service = AnalyticsService(db=db)
    return await service.get_summary(short_code)
