"""Wire application services from repository and infrastructure ports."""

from __future__ import annotations

from dataclasses import dataclass

from backend.application.llm.chat_model import ChatModel
from backend.application.llm.embedder import Embedder
from backend.application.parsing.archive_extractor import ArchiveExtractor
from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.session import SessionRepository
from backend.application.repositories.upload import UploadRepository
from backend.application.services.ask import AskService
from backend.application.services.documents import DocumentService
from backend.application.services.engagements import EngagementService
from backend.application.services.sessions import SessionService
from backend.application.services.uploads import UploadService
from backend.application.storage.document_storage import DocumentStorage
from backend.application.storage.job_queue import JobQueue
from backend.application.storage.vector_index import VectorIndex
from backend.config import Settings


@dataclass(frozen=True, slots=True)
class WorkerDeps:
    """Ingestion worker adapters (repos/jobs/vector — not HTTP-facing)."""

    jobs: JobQueue
    vector_index: VectorIndex
    document_repository: DocumentRepository
    upload_repository: UploadRepository


@dataclass(frozen=True, slots=True)
class SessionBound:
    """Per-request application services bound to one AsyncSession."""

    engagements: EngagementService
    documents: DocumentService
    uploads: UploadService
    sessions: SessionService
    ask: AskService
    _worker: WorkerDeps

    @property
    def worker(self) -> WorkerDeps:
        return self._worker

    # Backward-compatible aliases used by the in-process worker loop.
    @property
    def jobs(self) -> JobQueue:
        return self._worker.jobs

    @property
    def vector_index(self) -> VectorIndex:
        return self._worker.vector_index

    @property
    def document_repository(self) -> DocumentRepository:
        return self._worker.document_repository

    @property
    def upload_repository(self) -> UploadRepository:
        return self._worker.upload_repository


def wire_session_bound(
    *,
    engagements: EngagementRepository,
    documents: DocumentRepository,
    sessions: SessionRepository,
    uploads: UploadRepository,
    chat: ChatModel,
    embedder: Embedder,
    storage: DocumentStorage,
    archives: ArchiveExtractor,
    settings: Settings,
    jobs: JobQueue,
    vector_index: VectorIndex,
) -> SessionBound:
    worker = WorkerDeps(
        jobs=jobs,
        vector_index=vector_index,
        document_repository=documents,
        upload_repository=uploads,
    )
    return SessionBound(
        engagements=EngagementService(engagements, storage=storage),
        documents=DocumentService(
            engagements,
            documents,
            uploads,
            storage=storage,
            jobs=worker.jobs,
            archives=archives,
            settings=settings,
        ),
        uploads=UploadService(engagements, uploads),
        sessions=SessionService(engagements, sessions),
        ask=AskService(
            engagements,
            documents,
            sessions,
            worker.vector_index,
            chat=chat,
            embedder=embedder,
            storage=storage,
            settings=settings,
        ),
        _worker=worker,
    )
