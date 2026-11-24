"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create an async engine from ``Settings.database_url``.

    Pool sizing is explicit so two API replicas (compose default) do not
    exhaust Postgres with unbounded overflow while long Ask graphs hold a
    request-scoped session. Full release of the connection during LLM waits
    still needs short-lived sessions per DB op (tracked follow-up).
    """
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to ``engine``."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
