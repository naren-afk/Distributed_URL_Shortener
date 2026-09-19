from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine, get_db, init_db
from app.core.redis import close_redis_pool, get_redis
from app.services.cache_service import CacheService
from app.services.url_service import URLService

logger = logging.getLogger("App")
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown routines."""
    logger.info("Initializing database schemas...")
    try:
        await init_db()
        logger.info("Database schemas initialized.")
    except Exception as e:
        logger.warning(f"Database initialization deferred or failed: {e}")

    yield

    logger.info("Closing application resources...")
    await close_redis_pool()
    await engine.dispose()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Distributed URL Shortener with Redis Caching and Async Analytics",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 and Health routes
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(health_router, prefix="/health", tags=["Health"])


def extract_client_metadata(request: Request) -> dict:
    """Extracts client IP, user agent, and referrer for analytics tracking."""
    # Check X-Forwarded-For header if behind Nginx reverse proxy
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return {
        "ip_address": ip,
        "user_agent": request.headers.get("user-agent", ""),
        "referrer": request.headers.get("referer") or request.headers.get("referrer", "Direct"),
    }


# Serve static web frontend if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": f"{settings.PROJECT_NAME} API is running."}


@app.get(
    "/{short_code}",
    summary="Redirect short code to destination URL",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
)
async def redirect_short_url(
    short_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Core high-performance redirect handler.
    1. Checks Redis cache (<1ms).
    2. Fallback to PostgreSQL on cache miss.
    3. Emits async click event for background analytics worker.
    4. Returns HTTP 302 redirect.
    """
    # Exclude system prefixes from short_code redirection
    reserved = {"favicon.ico", "docs", "redoc", "openapi.json", "api", "static", "health"}
    if short_code in reserved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    cache = CacheService(redis)
    service = URLService(db=db, cache=cache)

    client_meta = extract_client_metadata(request)
    target_url = await service.resolve_url(short_code, client_metadata=client_meta)

    return RedirectResponse(
        url=target_url,
        status_code=status.HTTP_302_FOUND,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
