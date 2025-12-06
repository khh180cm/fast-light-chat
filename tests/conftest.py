"""Pytest configuration and shared fixtures."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.postgres import Base
from app.main import create_app


# Test database URL (uses test_ prefix)
TEST_DATABASE_URL = settings.postgres_dsn.replace(
    settings.postgres_db, f"test_{settings.postgres_db}"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def sample_organization_data() -> dict:
    """Sample organization data for tests."""
    return {
        "name": "Test Company",
        "slug": "test-company",
    }


@pytest.fixture
def sample_agent_data() -> dict:
    """Sample agent data for tests."""
    return {
        "email": "agent@test.com",
        "password": "testpassword123",
        "name": "Test Agent",
    }
