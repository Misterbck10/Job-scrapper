from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from arq import ArqRedis
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.core import queue as queue_module
from app.core.config import get_settings
from app.db import session as session_module
from app.domain.models import Base, Country


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer]:
    with RedisContainer("valkey/valkey:8-alpine") as container:
        yield container


@pytest_asyncio.fixture
async def app_client(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient]:
    monkeypatch.setenv("DATABASE_URL", postgres_container.get_connection_url())
    monkeypatch.setenv(
        "REDIS_URL",
        f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0",
    )
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "test")
    monkeypatch.setenv("S3_SECRET_KEY", "test")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    get_settings.cache_clear()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_module._engine = engine
    session_module._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_module._session_factory() as seed_session:
        seed_session.add(Country(code="AT", name="Austria"))
        await seed_session.commit()
    queue_module._pool = None

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()
    pool: ArqRedis | None = queue_module._pool
    if pool is not None:
        await pool.aclose()
        queue_module._pool = None
