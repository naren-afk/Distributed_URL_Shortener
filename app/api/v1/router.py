from fastapi import APIRouter

from app.api.v1.endpoints import analytics, health, urls

api_router = APIRouter()
api_router.include_router(urls.router, tags=["URLs"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
