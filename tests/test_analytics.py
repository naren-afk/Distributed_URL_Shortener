from datetime import datetime, timezone
import pytest
from app.models.analytics import ClickEvent
from app.models.url import URL
from app.services.analytics_service import AnalyticsService
from app.workers.analytics_worker import AnalyticsWorker


@pytest.mark.asyncio
async def test_analytics_service_aggregation(db_session):
    # Setup test URL
    url = URL(
        short_code="metrics-test",
        original_url="https://news.ycombinator.com",
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )
    db_session.add(url)
    await db_session.commit()

    # Add mock click events
    clicks = [
        ClickEvent(
            short_code="metrics-test",
            timestamp=datetime.now(timezone.utc),
            ip_address="192.168.1.1",
            referrer="https://twitter.com",
            browser="Chrome",
            os="Windows",
        ),
        ClickEvent(
            short_code="metrics-test",
            timestamp=datetime.now(timezone.utc),
            ip_address="192.168.1.2",
            referrer="https://twitter.com",
            browser="Chrome",
            os="Windows",
        ),
        ClickEvent(
            short_code="metrics-test",
            timestamp=datetime.now(timezone.utc),
            ip_address="192.168.1.3",
            referrer="Direct",
            browser="Safari",
            os="iOS",
        ),
    ]
    db_session.add_all(clicks)
    await db_session.commit()

    service = AnalyticsService(db=db_session)
    summary = await service.get_summary("metrics-test")

    assert summary.total_clicks == 3
    assert summary.clicks_last_24h == 3
    assert summary.top_referrers["https://twitter.com"] == 2
    assert summary.top_referrers["Direct"] == 1
    assert summary.top_browsers["Chrome"] == 2
    assert summary.top_browsers["Safari"] == 1
    assert summary.top_os["Windows"] == 2
    assert summary.top_os["iOS"] == 1
    assert len(summary.recent_clicks) == 3


@pytest.mark.asyncio
async def test_worker_process_batch(db_session):
    # Session context factory for testing
    class MockSessionContext:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Create URL
    url = URL(
        short_code="batch-test",
        original_url="https://github.com",
        created_at=datetime.now(timezone.utc),
        click_count=0,
        is_active=True,
    )
    db_session.add(url)
    await db_session.commit()

    # Pass mock session factory
    worker = AnalyticsWorker(session_factory=lambda: MockSessionContext())
    batch = [
        {
            "short_code": "batch-test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip_address": "10.0.0.1",
            "referrer": "https://google.com",
            "user_agent": "Mozilla",
            "browser": "Firefox",
            "os": "Linux",
            "country": "US",
        },
        {
            "short_code": "batch-test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip_address": "10.0.0.2",
            "referrer": "https://google.com",
            "user_agent": "Mozilla",
            "browser": "Firefox",
            "os": "Linux",
            "country": "US",
        },
    ]

    await worker.process_batch(batch)

    # Verify that click count on URL incremented by 2
    await db_session.refresh(url)
    assert url.click_count == 2
