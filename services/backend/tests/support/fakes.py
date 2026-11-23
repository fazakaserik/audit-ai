"""In-memory fakes for application ports (offline unit/api tests)."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from backend.application.dto import (
    ChatMessage,
    EmbedResult,
    IncompleteStructuredOutputError,
    RetrievalScope,
    ScoredChunk,
    StructuredResult,
    ThinkingCallbacks,
    ToolCall,
    ToolSpec,
    ToolTurnResult,
)
from backend.domain.chunk import Chunk
from backend.domain.document import (
    Document,
    DocumentId,
    DocumentPath,
    FolderPath,
    child_folder_name,
    normalize_list_prefix,
    relative_segments,
    within_depth,
)
from backend.domain.engagement import Engagement, EngagementId
from backend.domain.errors import ModelTimeoutError, ModelUnavailableError, NotFoundError
from backend.domain.session import LlmUsage, Session, SessionId, Turn
from backend.domain.upload import (
    Upload,
    UploadId,
    UploadItem,
    UploadItemId,
    UploadItemStatus,
    UploadStatus,
)

TModel = TypeVar("TModel", bound=BaseModel)


def _last_user_text(messages: Sequence[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user" and message.content:
            return message.content
    return "search"


class FakeChatModel:
    """Configurable ChatModel: return a pydantic instance or raise a model error.

    By default, the first ``complete_tool_turn`` issues ``search_relevant_chunks``
    using the last user message, then subsequent turns return no tool calls so the
    agent can run ``generate_structured``. Pass ``tool_turns`` to script exact turns.
    """

    def __init__(
        self,
        *,
        response: BaseModel | None = None,
        responses: Sequence[BaseModel] | None = None,
        error: (
            ModelTimeoutError | ModelUnavailableError | IncompleteStructuredOutputError | None
        ) = None,
        supports_thinking: bool = False,
        thinking_text: str = "",
        thinking_seconds: float = 0.0,
        usage: LlmUsage | None = None,
        tool_turns: Sequence[ToolTurnResult] | None = None,
        auto_search: bool = True,
    ) -> None:
        self._response = response
        self._responses = list(responses) if responses is not None else None
        self._error = error
        self._supports_thinking = supports_thinking
        self._thinking_text = thinking_text
        self._thinking_seconds = thinking_seconds
        self._usage = usage or LlmUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        self._tool_turns = list(tool_turns) if tool_turns is not None else None
        self._auto_search = auto_search
        self.calls: list[tuple[tuple[ChatMessage, ...], type[BaseModel]]] = []
        self.tool_turn_calls: list[tuple[tuple[ChatMessage, ...], tuple[ToolSpec, ...]]] = []

    @property
    def supports_thinking(self) -> bool:
        return self._supports_thinking

    def configure(
        self,
        *,
        response: BaseModel | None = None,
        responses: Sequence[BaseModel] | None = None,
        error: (
            ModelTimeoutError | ModelUnavailableError | IncompleteStructuredOutputError | None
        ) = None,
        tool_turns: Sequence[ToolTurnResult] | None = None,
        auto_search: bool | None = None,
    ) -> None:
        self._response = response
        self._responses = list(responses) if responses is not None else None
        self._error = error
        if tool_turns is not None:
            self._tool_turns = list(tool_turns)
        if auto_search is not None:
            self._auto_search = auto_search

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> StructuredResult[TModel]:
        self.calls.append((tuple(messages), schema))
        if thinking is not None and self._supports_thinking:
            if self._thinking_text:
                await thinking.on_delta(self._thinking_text)
            thinking.on_seconds(self._thinking_seconds)
        if self._error is not None:
            raise self._error
        if self._responses:
            next_item = self._responses.pop(0)
            if not isinstance(next_item, schema):
                msg = (
                    f"FakeChatModel response type {type(next_item).__name__} "
                    f"does not match schema {schema.__name__}"
                )
                raise TypeError(msg)
            return StructuredResult(value=next_item, usage=self._usage)
        if self._response is None:
            msg = "FakeChatModel has no response configured"
            raise AssertionError(msg)
        if not isinstance(self._response, schema):
            msg = (
                f"FakeChatModel response type {type(self._response).__name__} "
                f"does not match schema {schema.__name__}"
            )
            raise TypeError(msg)
        return StructuredResult(value=self._response, usage=self._usage)

    async def complete_tool_turn(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> ToolTurnResult:
        self.tool_turn_calls.append((tuple(messages), tuple(tools)))
        if thinking is not None and self._supports_thinking:
            if self._thinking_text:
                await thinking.on_delta(self._thinking_text)
            thinking.on_seconds(self._thinking_seconds)
        if self._error is not None:
            raise self._error
        if self._tool_turns is not None:
            if not self._tool_turns:
                return ToolTurnResult(content=None, tool_calls=(), usage=self._usage)
            return self._tool_turns.pop(0)
        # Once per agent run: if no tool results yet, issue search_relevant_chunks.
        has_tool_results = any(message.role == "tool" for message in messages)
        if self._auto_search and not has_tool_results:
            query = _last_user_text(messages)
            for line in reversed(query.splitlines()):
                stripped = line.strip()
                if stripped.lower().startswith("question:"):
                    query = stripped.split(":", 1)[1].strip() or query
                    break
            return ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id=f"fake_search_{len(self.tool_turn_calls)}",
                        name="search_relevant_chunks",
                        arguments=json.dumps({"query": query}),
                    ),
                ),
                usage=self._usage,
            )
        return ToolTurnResult(content=None, tool_calls=(), usage=self._usage)


class FakeEmbedder:
    def __init__(
        self,
        *,
        model_name: str = "fake-embed",
        dimensions: int = 8,
        usage: LlmUsage | None = None,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._usage = usage or LlmUsage(prompt_tokens=3, completion_tokens=0, total_tokens=3)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> EmbedResult:
        # Deterministic unit vector shared across texts so offline retrieval
        # tests are not sensitive to cosine thresholds.
        base = [1.0] + [0.0] * (self._dimensions - 1)
        return EmbedResult(vectors=[list(base) for _ in texts], usage=self._usage)


@dataclass
class _IndexedChunk:
    engagement_id: EngagementId
    document_id: DocumentId
    document_path: DocumentPath
    document_version: int
    chunk: Chunk
    embedding: tuple[float, ...]
    embedding_model: str


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class InMemoryVectorIndex:
    def __init__(self) -> None:
        self._rows: list[_IndexedChunk] = []

    async def upsert_chunks(
        self,
        *,
        engagement_id: EngagementId,
        document_id: DocumentId,
        document_path: DocumentPath,
        document_version: int,
        chunks: Sequence[Chunk],
        embeddings: Sequence[Sequence[float]],
        embedding_model: str,
    ) -> None:
        if len(chunks) != len(embeddings):
            msg = "chunks and embeddings length mismatch"
            raise ValueError(msg)
        self._rows = [
            row
            for row in self._rows
            if not (row.engagement_id == engagement_id and row.document_id == document_id)
        ]
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            self._rows.append(
                _IndexedChunk(
                    engagement_id=engagement_id,
                    document_id=document_id,
                    document_path=document_path,
                    document_version=document_version,
                    chunk=chunk,
                    embedding=tuple(float(value) for value in embedding),
                    embedding_model=embedding_model,
                )
            )

    async def search(
        self,
        query: str,
        query_embedding: Sequence[float],
        scope: RetrievalScope,
        *,
        embedding_model: str,
        min_score: float,
    ) -> list[ScoredChunk]:
        _ = query
        scored: list[ScoredChunk] = []
        for row in self._rows:
            if row.engagement_id != scope.engagement_id:
                continue
            if row.embedding_model != embedding_model:
                continue
            if scope.folder_prefix is not None and scope.folder_prefix != "":
                prefix = scope.folder_prefix.rstrip("/") + "/"
                path = row.document_path
                if path != scope.folder_prefix and not path.startswith(prefix):
                    continue
            score = _cosine(query_embedding, row.embedding)
            if score < min_score:
                continue
            scored.append(
                ScoredChunk(
                    chunk=row.chunk,
                    document_path=row.document_path,
                    score=score,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: scope.top_k]


class InMemoryDocumentStorage:
    def __init__(self) -> None:
        self._blobs: dict[tuple[EngagementId, DocumentPath], bytes] = {}

    async def put(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
        data: bytes,
    ) -> Path:
        self._blobs[(engagement_id, path)] = data
        return Path("memory") / engagement_id / path

    async def get(self, engagement_id: EngagementId, path: DocumentPath) -> bytes:
        key = (engagement_id, path)
        if key not in self._blobs:
            raise NotFoundError(f"document blob not found: {engagement_id}/{path}")
        return self._blobs[key]

    async def delete(self, engagement_id: EngagementId, path: DocumentPath) -> None:
        self._blobs.pop((engagement_id, path), None)


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
