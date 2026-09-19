import pytest
from fastapi import HTTPException
from pydantic import HttpUrl
from app.schemas.url import URLCreate
from app.services.cache_service import CacheService
from app.services.url_service import URLService, parse_user_agent


def test_parse_user_agent():
    browser, os_name = parse_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    assert browser == "Chrome"
    assert os_name == "Windows"

    browser, os_name = parse_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1")
    assert browser == "Safari"
    assert os_name == "iOS"


@pytest.mark.asyncio
async def test_shorten_and_resolve(db_session, mock_redis):
    cache = CacheService(mock_redis)
    service = URLService(db=db_session, cache=cache)

    payload = URLCreate(url=HttpUrl("https://deepmind.google/"))
    record = await service.shorten_url(payload)

    assert record.short_code != ""
    assert record.original_url == "https://deepmind.google/"

    # Cache should be warmed immediately
    cached = await cache.get_url(record.short_code)
    assert cached == "https://deepmind.google/"

    # Resolve URL
    resolved = await service.resolve_url(record.short_code, client_metadata={"ip_address": "127.0.0.1"})
    assert resolved == "https://deepmind.google/"


@pytest.mark.asyncio
async def test_custom_alias_and_conflict(db_session, mock_redis):
    cache = CacheService(mock_redis)
    service = URLService(db=db_session, cache=cache)

    payload = URLCreate(url=HttpUrl("https://example.com/"), custom_alias="my-custom-link")
    record = await service.shorten_url(payload)
    assert record.short_code == "my-custom-link"

    # Duplicate alias must raise 409 Conflict
    payload_duplicate = URLCreate(url=HttpUrl("https://another.com/"), custom_alias="my-custom-link")
    with pytest.raises(HTTPException) as exc_info:
        await service.shorten_url(payload_duplicate)
    assert exc_info.value.status_code == 409
