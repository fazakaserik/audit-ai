"""Application-layer DTOs (not domain entities, not vendor types)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

from pydantic import BaseModel

from backend.domain.answer import Answer
from backend.domain.chunk import Chunk
from backend.domain.document import ContentType, Document, DocumentPath, FolderPath
from backend.domain.engagement import Engagement, EngagementId
from backend.domain.session import LlmUsage, Session, SessionId, Turn, TurnId
from backend.domain.upload import Upload, UploadId, UploadItem


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


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page[T]:
    """Offset-based pagination (application layer, not HTTP contracts)."""

    items: tuple[T, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class EngagementWithDocumentCount:
    engagement: Engagement
    document_count: int


@dataclass(frozen=True, slots=True)
class DocumentListing:
    items: tuple[Document, ...]
    folders: tuple[str, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class UploadAccepted:
    upload_id: UploadId


@dataclass(frozen=True, slots=True)
class SessionDetail:
    session: Session
    turns: tuple[Turn, ...]


@dataclass(frozen=True, slots=True)
class UploadDetail:
    upload: Upload
    items: tuple[UploadItem, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class AskStreamFinal:
    result: AskResult
    type: Literal["final"] = "final"


@dataclass(frozen=True, slots=True, kw_only=True)
class AskStreamError:
    error: BaseException
    type: Literal["error"] = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class AskStreamThinkingDone:
    duration_seconds: float
    type: Literal["thinking_done"] = "thinking_done"


AskProgressEvent = dict[str, object]
AskStreamEvent = AskProgressEvent | AskStreamFinal | AskStreamError | AskStreamThinkingDone


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


@dataclass(frozen=True, slots=True)
class ParsedSection:
    text: str
    heading_path: tuple[str, ...]
    page: int | None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    content_type: ContentType
    sections: tuple[ParsedSection, ...]


@dataclass(frozen=True, slots=True)
class ParsedChunk:
    """Pre-persist chunk produced by infrastructure chunking."""

    text: str
    heading_path: tuple[str, ...]
    page: int | None
    token_count: int
    ordinal: int
