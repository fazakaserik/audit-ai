"""Application-layer DTOs (not domain entities, not vendor types)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

from backend.domain.answer import Answer
from backend.domain.chunk import Chunk
from backend.domain.document import ContentType, DocumentPath, FolderPath
from backend.domain.engagement import EngagementId
from backend.domain.session import LlmUsage, SessionId, TurnId


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
