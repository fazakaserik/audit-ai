"""Build a FastAPI test container with in-memory Protocol fakes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.application.llm.chat_model import ChatModel
from backend.application.llm.embedder import Embedder
from backend.application.parsing.archive_extractor import ArchiveExtractor
from backend.application.parsing.document_parser import DocumentParser
from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.session import SessionRepository
from backend.application.repositories.upload import UploadRepository
from backend.application.storage.document_storage import DocumentStorage
from backend.application.storage.job_queue import JobQueue
from backend.application.storage.vector_index import VectorIndex
from backend.application.wiring import wire_session_bound
from backend.bootstrap import Container, SessionBound
from backend.config import Settings
from backend.infrastructure.parsing.archive import build_archive_extractor
from backend.infrastructure.parsing.chunking import build_document_chunker
from backend.infrastructure.parsing.parsers.default import build_document_parser
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
    agent_search_tool_turns,
)


@dataclass
class _DummyEngine:
    dispose: AsyncMock


def build_fakes_bound(
    *,
    engagements: EngagementRepository | None = None,
    documents: DocumentRepository | None = None,
    sessions: SessionRepository | None = None,
    uploads: UploadRepository | None = None,
    vector_index: VectorIndex | None = None,
    jobs: JobQueue | None = None,
    storage: DocumentStorage | None = None,
    archives: ArchiveExtractor | None = None,
    settings: Settings | None = None,
    chat: ChatModel | None = None,
    embedder: Embedder | None = None,
    document_parser: DocumentParser | None = None,
) -> SessionBound:
    eng = engagements or InMemoryEngagementRepository()
    docs = documents or InMemoryDocumentRepository()
    sess = sessions or InMemorySessionRepository()
    ups = uploads or InMemoryUploadRepository()
    vectors = vector_index or InMemoryVectorIndex()
    job_queue = jobs or NoopJobQueue()
    document_storage = storage or InMemoryDocumentStorage()
    cfg = settings or Settings(relevance_threshold=0.0, retrieval_top_k=8)
    archive_extractor = archives or build_archive_extractor()
    chat_model = chat or FakeChatModel(tool_turns=agent_search_tool_turns())
    emb = embedder or FakeEmbedder()
    parser = document_parser or build_document_parser()
    return wire_session_bound(
        engagements=eng,
        documents=docs,
        sessions=sess,
        uploads=ups,
        chat=chat_model,
        embedder=emb,
        storage=document_storage,
        archives=archive_extractor,
        settings=cfg,
        jobs=job_queue,
        vector_index=vectors,
        document_parser=parser,
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
        document_parser=build_document_parser(),
        document_chunker=build_document_chunker(),
        archive_extractor=build_archive_extractor(),
    )
