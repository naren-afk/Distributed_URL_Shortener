from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class ClickEventDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    ip_address: Optional[str] = None
    referrer: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    country: Optional[str] = None


class AnalyticsSummary(BaseModel):
    short_code: str
    original_url: str
    total_clicks: int
    clicks_last_24h: int
    top_referrers: Dict[str, int]
    top_browsers: Dict[str, int]
    top_os: Dict[str, int]
    recent_clicks: List[ClickEventDetail]
