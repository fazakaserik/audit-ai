"""Repository ports and ask session binding."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from backend.application.ports.storage import VectorIndex
from backend.domain.document import Document, DocumentPath, FolderPath
from backend.domain.engagement import Engagement, EngagementId
from backend.domain.session import Session, SessionId, Turn
from backend.domain.upload import Upload, UploadId, UploadItem


class EngagementRepository(Protocol):
    async def create(self, engagement: Engagement) -> Engagement: ...

    async def get(self, engagement_id: EngagementId) -> Engagement | None: ...

    async def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Engagement], int]: ...

    async def count_documents(self, engagement_id: EngagementId) -> int: ...


class DocumentRepository(Protocol):
    async def upsert(self, document: Document) -> Document: ...

    async def get_by_path(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
    ) -> Document | None: ...

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        prefix: FolderPath | None,
        depth: int | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], tuple[str, ...], int]:
        """Return (documents within depth, immediate child folders, document total)."""
        ...


class SessionRepository(Protocol):
    async def create(self, session: Session) -> Session: ...

    async def get(
        self,
        engagement_id: EngagementId,
        session_id: SessionId,
    ) -> Session | None: ...

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Session], int]: ...

    async def add_turn(self, turn: Turn) -> Turn: ...

    async def list_turns(self, session_id: SessionId) -> list[Turn]: ...

    async def bump_turn_count(
        self, session_id: SessionId, *, title: str | None = None
    ) -> Session: ...


class UploadRepository(Protocol):
    async def create(self, upload: Upload, items: Sequence[UploadItem]) -> Upload: ...

    async def get(
        self,
        engagement_id: EngagementId,
        upload_id: UploadId,
    ) -> tuple[Upload, list[UploadItem]] | None: ...

    async def get_by_id(self, upload_id: UploadId) -> Upload | None: ...

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Upload], int]: ...

    async def mark_processing(self, upload_id: UploadId) -> None: ...

    async def refresh_status(self, upload_id: UploadId) -> Upload: ...


class AskSessionBound(Protocol):
    """Repos/session/vector/document ports needed by ask_question (avoids bootstrap import)."""

    @property
    def engagements(self) -> EngagementRepository: ...

    @property
    def documents(self) -> DocumentRepository: ...

    @property
    def sessions(self) -> SessionRepository: ...

    @property
    def vector_index(self) -> VectorIndex: ...
