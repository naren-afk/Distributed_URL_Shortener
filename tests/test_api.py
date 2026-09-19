import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["database"] == "connected"
    assert data["services"]["redis"] == "connected"


@pytest.mark.asyncio
async def test_shorten_api_and_redirect(client):
    # 1. Shorten URL
    resp = await client.post(
        "/api/v1/shorten",
        json={"url": "https://python.org", "custom_alias": "python-home"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["short_code"] == "python-home"
    assert data["original_url"] == "https://python.org/"

    # 2. Query URL Metadata
    resp_meta = await client.get("/api/v1/urls/python-home")
    assert resp_meta.status_code == 200
    assert resp_meta.json()["short_code"] == "python-home"

    # 3. Test Redirect (302)
    resp_redirect = await client.get("/python-home", follow_redirects=False)
    assert resp_redirect.status_code == 302
    assert resp_redirect.headers["location"] == "https://python.org/"

    # 4. Analytics Endpoint
    resp_analytics = await client.get("/api/v1/analytics/python-home")
    assert resp_analytics.status_code == 200
    analytics_data = resp_analytics.json()
    assert analytics_data["short_code"] == "python-home"
    assert "total_clicks" in analytics_data


@pytest.mark.asyncio
async def test_404_nonexistent_redirect(client):
    resp = await client.get("/nonexistent-code-12345", follow_redirects=False)
    assert resp.status_code == 404
