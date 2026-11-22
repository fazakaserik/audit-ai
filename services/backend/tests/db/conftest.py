"""Postgres + pgvector fixtures (marker: db)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

from backend.adapters.postgres.engine import create_engine, create_session_factory


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        yield container.get_connection_url().replace("psycopg2", "asyncpg")
    finally:
        container.stop()


@pytest_asyncio.fixture
async def engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_engine(postgres_url)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)
