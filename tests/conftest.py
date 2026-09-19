import asyncio
from typing import AsyncGenerator, Dict, Optional
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import app


class InMemoryMockRedis:
    """Async in-memory mock for Redis cache and queues during testing."""
    def __init__(self):
        self.store: Dict[str, str] = {}
        self.lists: Dict[str, list] = {}

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self.store[key] = value
        return True

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0

    async def lpush(self, key: str, *values: str) -> int:
        if key not in self.lists:
            self.lists[key] = []
        for val in values:
            self.lists[key].insert(0, val)
        return len(self.lists[key])

    async def rpop(self, key: str, count: Optional[int] = None):
        items = self.lists.get(key, [])
        if not items:
            return None if count is None else []
        if count is None:
            return items.pop()
        popped = []
        for _ in range(min(count, len(items))):
            popped.append(items.pop())
        return popped

    async def ping(self) -> bool:
        return True

    async def aclose(self):
        pass


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated in-memory SQLite async database session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_redis() -> InMemoryMockRedis:
    return InMemoryMockRedis()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis: InMemoryMockRedis) -> AsyncGenerator[AsyncClient, None]:
    """Test client with overridden DB session and Redis dependencies."""
    async def override_get_db():
        yield db_session

    async def override_get_redis():
        yield mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
