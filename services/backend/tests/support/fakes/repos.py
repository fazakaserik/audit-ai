"""In-memory repository and job queue fakes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from backend.domain.document import (
    Document,
    DocumentPath,
    FolderPath,
    child_folder_name,
    normalize_list_prefix,
    relative_segments,
    within_depth,
)
from backend.domain.engagement import Engagement, EngagementId
from backend.domain.errors import NotFoundError
from backend.domain.session import Session, SessionId, Turn
from backend.domain.upload import (
    Upload,
    UploadId,
    UploadItem,
    UploadItemId,
    UploadItemStatus,
    UploadStatus,
)


class InMemoryEngagementRepository:
    def __init__(self) -> None:
        self._items: dict[EngagementId, Engagement] = {}
        self._document_counts: dict[EngagementId, int] = {}

    def set_document_count(self, engagement_id: EngagementId, count: int) -> None:
        self._document_counts[engagement_id] = count

    async def create(self, engagement: Engagement) -> Engagement:
        self._items[engagement.id] = engagement
        self._document_counts.setdefault(engagement.id, 0)
        return engagement

    async def get(self, engagement_id: EngagementId) -> Engagement | None:
        return self._items.get(engagement_id)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Engagement], int]:
        ordered = sorted(self._items.values(), key=lambda item: item.created_at)
        total = len(ordered)
        return ordered[offset : offset + limit], total

    async def count_documents(self, engagement_id: EngagementId) -> int:
        return self._document_counts.get(engagement_id, 0)

    async def count_documents_for_engagements(
        self,
        engagement_ids: Sequence[EngagementId],
    ) -> dict[EngagementId, int]:
        return {eid: self._document_counts.get(eid, 0) for eid in engagement_ids}


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[EngagementId, DocumentPath], Document] = {}

    async def upsert(self, document: Document) -> Document:
        self._items[(document.engagement_id, document.path)] = document
        return document

    async def get_by_path(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
    ) -> Document | None:
        return self._items.get((engagement_id, path))

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        prefix: FolderPath | None,
        depth: int | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], tuple[str, ...], int]:
        base = normalize_list_prefix(prefix)
        under_prefix: list[Document] = []
        folders: set[str] = set()
        for (eng_id, path), document in self._items.items():
            if eng_id != engagement_id:
                continue
            segments = relative_segments(path, base)
            if segments is None:
                continue
            folder = child_folder_name(segments)
            if folder is not None:
                folders.add(folder)
            if within_depth(segments, depth):
                under_prefix.append(document)
        under_prefix.sort(key=lambda item: item.path)
        total = len(under_prefix)
        return under_prefix[offset : offset + limit], tuple(sorted(folders)), total


@dataclass
class InMemoryUploadRepository:
    _uploads: dict[UploadId, Upload] = field(default_factory=dict)
    _items: dict[UploadId, list[UploadItem]] = field(default_factory=dict)

    async def create(self, upload: Upload, items: Sequence[UploadItem]) -> Upload:
        self._uploads[upload.id] = upload
        self._items[upload.id] = list(items)
        return upload

    async def get(
        self,
        engagement_id: EngagementId,
        upload_id: UploadId,
    ) -> tuple[Upload, list[UploadItem]] | None:
        upload = self._uploads.get(upload_id)
        if upload is None or upload.engagement_id != engagement_id:
            return None
        return upload, list(self._items.get(upload_id, []))

    async def get_by_id(self, upload_id: UploadId) -> Upload | None:
        return self._uploads.get(upload_id)

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Upload], int]:
        matched = [
            upload for upload in self._uploads.values() if upload.engagement_id == engagement_id
        ]
        matched.sort(key=lambda item: item.created_at, reverse=True)
        total = len(matched)
        return matched[offset : offset + limit], total

    async def mark_processing(self, upload_id: UploadId) -> None:
        upload = self._uploads.get(upload_id)
        if upload is None or upload.status != UploadStatus.QUEUED:
            return
        self._uploads[upload_id] = upload.model_copy(update={"status": UploadStatus.PROCESSING})

    async def refresh_status(self, upload_id: UploadId) -> Upload:
        upload = self._uploads.get(upload_id)
        if upload is None:
            raise NotFoundError(f"upload not found: {upload_id}")
        items = self._items.get(upload_id, [])
        terminal = {
            UploadItemStatus.INDEXED,
            UploadItemStatus.SKIPPED,
            UploadItemStatus.NOT_SEARCHABLE,
            UploadItemStatus.FAILED,
        }
        statuses = {item.status for item in items}
        if statuses and statuses <= terminal:
            updated = upload.model_copy(
                update={"status": UploadStatus.COMPLETED, "completed_at": items[-1].updated_at}
            )
        elif UploadItemStatus.PROCESSING in statuses or any(s in terminal for s in statuses):
            updated = upload.model_copy(update={"status": UploadStatus.PROCESSING})
        else:
            updated = upload.model_copy(update={"status": UploadStatus.QUEUED})
        self._uploads[upload_id] = updated
        return updated


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._items: dict[UploadItemId, UploadItem] = {}

    async def enqueue_items(self, items: Sequence[UploadItem]) -> None:
        for item in items:
            self._items[item.id] = item

    async def claim_next(self, worker_id: str) -> UploadItem | None:
        _ = worker_id
        for item in sorted(self._items.values(), key=lambda row: row.created_at):
            if item.status == UploadItemStatus.PENDING:
                claimed = item.model_copy(update={"status": UploadItemStatus.PROCESSING})
                self._items[item.id] = claimed
                return claimed
        return None

    async def complete(
        self,
        item_id: UploadItemId,
        *,
        status: str,
        reason: str | None,
    ) -> None:
        item = self._items.get(item_id)
        if item is None:
            return
        self._items[item_id] = item.model_copy(
            update={
                "status": UploadItemStatus(status),
                "reason": reason,
            }
        )

    async def fail_for_retry(self, item_id: UploadItemId, *, reason: str) -> None:
        item = self._items.get(item_id)
        if item is None:
            return
        attempts = item.attempts + 1
        if attempts >= 3:
            self._items[item_id] = item.model_copy(
                update={
                    "status": UploadItemStatus.FAILED,
                    "attempts": attempts,
                    "reason": reason,
                }
            )
        else:
            self._items[item_id] = item.model_copy(
                update={
                    "status": UploadItemStatus.PENDING,
                    "attempts": attempts,
                    "reason": reason,
                }
            )


class NoopJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[UploadItem] = []

    async def enqueue_items(self, items: Sequence[UploadItem]) -> None:
        self.enqueued.extend(items)

    async def claim_next(self, worker_id: str) -> UploadItem | None:
        _ = worker_id
        return None

    async def complete(
        self,
        item_id: UploadItemId,
        *,
        status: str,
        reason: str | None,
    ) -> None:
        _ = (item_id, status, reason)

    async def fail_for_retry(self, item_id: UploadItemId, *, reason: str) -> None:
        _ = (item_id, reason)


@dataclass
class InMemorySessionRepository:
    _sessions: dict[SessionId, Session] = field(default_factory=dict)
    _turns: dict[SessionId, list[Turn]] = field(default_factory=dict)

    async def create(self, session: Session) -> Session:
        self._sessions[session.id] = session
        self._turns.setdefault(session.id, [])
        return session

    async def get(
        self,
        engagement_id: EngagementId,
        session_id: SessionId,
    ) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None or session.engagement_id != engagement_id:
            return None
        return session

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Session], int]:
        matched = [
            session for session in self._sessions.values() if session.engagement_id == engagement_id
        ]
        matched.sort(key=lambda item: item.created_at, reverse=True)
        total = len(matched)
        return matched[offset : offset + limit], total

    async def add_turn(self, turn: Turn) -> Turn:
        self._turns.setdefault(turn.session_id, []).append(turn)
        return turn

    async def list_turns(self, session_id: SessionId) -> list[Turn]:
        turns = list(self._turns.get(session_id, []))
        turns.sort(key=lambda item: item.ordinal)
        return turns

    async def bump_turn_count(
        self,
        session_id: SessionId,
        *,
        title: str | None = None,
    ) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise NotFoundError(f"session not found: {session_id}")
        updated = session.model_copy(
            update={
                "turn_count": session.turn_count + 1,
                **({"title": title} if title is not None else {}),
            }
        )
        self._sessions[session_id] = updated
        return updated
