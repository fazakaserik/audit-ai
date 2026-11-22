"""Build a FastAPI test container with in-memory port fakes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.application.ports import DocumentStorage
from backend.bootstrap import Container, SessionBound
from backend.config import Settings
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemorySessionRepository,
    InMemoryUploadRepository,
    InMemoryVectorIndex,
    NoopJobQueue,
)


@dataclass
class _DummyEngine:
    dispose: AsyncMock


def build_fakes_bound(
    *,
    engagements: InMemoryEngagementRepository | None = None,
    documents: InMemoryDocumentRepository | None = None,
    sessions: InMemorySessionRepository | None = None,
    uploads: InMemoryUploadRepository | None = None,
    vector_index: InMemoryVectorIndex | None = None,
    jobs: NoopJobQueue | None = None,
) -> SessionBound:
    return SessionBound(
        engagements=engagements or InMemoryEngagementRepository(),
        documents=documents or InMemoryDocumentRepository(),
        sessions=sessions or InMemorySessionRepository(),
        uploads=uploads or InMemoryUploadRepository(),
        vector_index=vector_index or InMemoryVectorIndex(),
        jobs=jobs or NoopJobQueue(),
    )


def build_test_container(
    *,
    settings: Settings | None = None,
    chat: FakeChatModel | None = None,
    embedder: FakeEmbedder | None = None,
    document_storage: DocumentStorage | None = None,
) -> Container:
    cfg = settings or Settings(relevance_threshold=0.0, retrieval_top_k=8)
    engine = cast(AsyncEngine, _DummyEngine(dispose=AsyncMock()))
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        async_sessionmaker(),
    )
    return Container(
        settings=cfg,
        engine=engine,
        session_factory=session_factory,
        chat_model=chat or FakeChatModel(),
        embedder=embedder or FakeEmbedder(),
        document_storage=document_storage or InMemoryDocumentStorage(),
    )
