"""Application ports (Protocols). Vendor types must not leak through these."""

from __future__ import annotations

from backend.application.dto import (
    AskResult,
    ChatMessage,
    EmbedResult,
    IncompleteStructuredOutputError,
    ParsedChunk,
    ParsedDocument,
    RetrievalScope,
    ScoredChunk,
    StoredFile,
    StructuredResult,
    ThinkingCallbacks,
    ToolCall,
    ToolSpec,
    ToolTurnResult,
)
from backend.application.ports.llm import ChatModel, Embedder
from backend.application.ports.parsing import ArchiveExtractor, DocumentChunker, DocumentParser
from backend.application.ports.repositories import (
    AskSessionBound,
    DocumentRepository,
    EngagementRepository,
    SessionRepository,
    UploadRepository,
)
from backend.application.ports.storage import DocumentStorage, JobQueue, VectorIndex

__all__ = [
    "ArchiveExtractor",
    "AskResult",
    "AskSessionBound",
    "ChatMessage",
    "ChatModel",
    "DocumentChunker",
    "DocumentParser",
    "DocumentRepository",
    "DocumentStorage",
    "EmbedResult",
    "Embedder",
    "EngagementRepository",
    "IncompleteStructuredOutputError",
    "JobQueue",
    "ParsedChunk",
    "ParsedDocument",
    "RetrievalScope",
    "ScoredChunk",
    "SessionRepository",
    "StoredFile",
    "StructuredResult",
    "ThinkingCallbacks",
    "ToolCall",
    "ToolSpec",
    "ToolTurnResult",
    "UploadRepository",
    "VectorIndex",
]
