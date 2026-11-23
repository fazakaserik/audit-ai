"""Application ports (Protocols). Vendor types must not leak through these."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from domain.answer import Answer
from domain.document import Document, DocumentId, DocumentPath, FolderPath
from domain.engagement import Engagement, EngagementId
from domain.chunk import Chunk
from domain.session import LlmUsage, Session, SessionId, Turn, TurnId
from domain.upload import Upload, UploadId, UploadItem, UploadItemId

TModel = TypeVar("TModel", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Model-requested tool invocation."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Provider-agnostic tool definition (JSON Schema parameters)."""

    name: str
    description: str
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ThinkingCallbacks:
    """Optional native thinking stream hooks for ChatModel adapters."""

    on_delta: Callable[[str], Awaitable[None]]
    on_seconds: Callable[[float], None]


@dataclass(frozen=True, slots=True)
class StructuredResult[TModel: BaseModel]:
    value: TModel
    usage: LlmUsage


@dataclass(frozen=True, slots=True)
class ToolTurnResult:
    """One assistant turn that may request tools or continue with text only."""

    content: str | None
    tool_calls: tuple[ToolCall, ...]
    usage: LlmUsage


class IncompleteStructuredOutputError(Exception):
    """Chat finished without usable structured JSON (e.g. thinking loop / empty body)."""


@dataclass(frozen=True, slots=True)
class EmbedResult:
    vectors: list[list[float]]
    usage: LlmUsage


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    chunk: Chunk
    document_path: DocumentPath
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    engagement_id: EngagementId
    folder_prefix: FolderPath | None = None
    top_k: int = 8


class ChatModel(Protocol):
    @property
    def supports_thinking(self) -> bool: ...

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> StructuredResult[TModel]: ...

    async def complete_tool_turn(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        *,
        thinking: ThinkingCallbacks | None = None,
    ) -> ToolTurnResult: ...


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> EmbedResult: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...


class VectorIndex(Protocol):
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
    ) -> None: ...

    async def search(
        self,
        query: str,
        query_embedding: Sequence[float],
        scope: RetrievalScope,
        *,
        embedding_model: str,
        min_score: float,
    ) -> list[ScoredChunk]: ...


class DocumentStorage(Protocol):
    async def put(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
        data: bytes,
    ) -> Path: ...

    async def get(self, engagement_id: EngagementId, path: DocumentPath) -> bytes: ...

    async def delete(self, engagement_id: EngagementId, path: DocumentPath) -> None: ...


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

    async def bump_turn_count(self, session_id: SessionId, *, title: str | None = None) -> Session: ...


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


class JobQueue(Protocol):
    async def enqueue_items(self, items: Sequence[UploadItem]) -> None: ...

    async def claim_next(self, worker_id: str) -> UploadItem | None: ...

    async def complete(self, item_id: UploadItemId, *, status: str, reason: str | None) -> None: ...

    async def fail_for_retry(self, item_id: UploadItemId, *, reason: str) -> None: ...


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


@dataclass(frozen=True, slots=True)
class AskResult:
    answer: Answer
    session_id: SessionId
    turn_id: TurnId
    standalone_question: str
    usage: LlmUsage
    session_total_tokens: int


@dataclass(frozen=True, slots=True)
class StoredFile:
    engagement_id: EngagementId
    path: DocumentPath
    size_bytes: int
    sha256: str
