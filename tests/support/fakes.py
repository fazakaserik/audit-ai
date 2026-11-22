"""In-memory fakes for application ports (offline unit/api tests)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from backend.application.ports import (
    ChatMessage,
    RetrievalScope,
    ScoredPassage,
)
from domain.document import Document, DocumentId, DocumentPath, FolderPath
from domain.engagement import Engagement, EngagementId
from domain.errors import ModelTimeoutError, ModelUnavailableError, NotFoundError
from domain.passage import Passage
from domain.session import Session, SessionId, Turn

TModel = TypeVar("TModel", bound=BaseModel)


class FakeChatModel:
    """Configurable ChatModel: return a pydantic instance or raise a model error."""

    def __init__(
        self,
        *,
        response: BaseModel | None = None,
        error: ModelTimeoutError | ModelUnavailableError | None = None,
    ) -> None:
        self._response = response
        self._error = error
        self.calls: list[tuple[tuple[ChatMessage, ...], type[BaseModel]]] = []

    def configure(
        self,
        *,
        response: BaseModel | None = None,
        error: ModelTimeoutError | ModelUnavailableError | None = None,
    ) -> None:
        self._response = response
        self._error = error

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
    ) -> TModel:
        self.calls.append((tuple(messages), schema))
        if self._error is not None:
            raise self._error
        if self._response is None:
            msg = "FakeChatModel has no response configured"
            raise AssertionError(msg)
        if not isinstance(self._response, schema):
            msg = (
                f"FakeChatModel response type {type(self._response).__name__} "
                f"does not match schema {schema.__name__}"
            )
            raise TypeError(msg)
        return self._response


class FakeEmbedder:
    def __init__(
        self,
        *,
        model_name: str = "fake-embed",
        dimensions: int = 8,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            seed = sum(ord(ch) for ch in text) or 1
            vector = [
                math.sin(seed * (index + 1) * 0.17) for index in range(self._dimensions)
            ]
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


@dataclass
class _IndexedPassage:
    engagement_id: EngagementId
    document_id: DocumentId
    document_path: DocumentPath
    document_version: int
    passage: Passage
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
        self._rows: list[_IndexedPassage] = []

    async def upsert_passages(
        self,
        *,
        engagement_id: EngagementId,
        document_id: DocumentId,
        document_path: DocumentPath,
        document_version: int,
        passages: Sequence[Passage],
        embeddings: Sequence[Sequence[float]],
        embedding_model: str,
    ) -> None:
        if len(passages) != len(embeddings):
            msg = "passages and embeddings length mismatch"
            raise ValueError(msg)
        self._rows = [
            row
            for row in self._rows
            if not (row.engagement_id == engagement_id and row.document_id == document_id)
        ]
        for passage, embedding in zip(passages, embeddings, strict=True):
            self._rows.append(
                _IndexedPassage(
                    engagement_id=engagement_id,
                    document_id=document_id,
                    document_path=document_path,
                    document_version=document_version,
                    passage=passage,
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
    ) -> list[ScoredPassage]:
        _ = query
        scored: list[ScoredPassage] = []
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
                ScoredPassage(
                    passage=row.passage,
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
        limit: int,
        offset: int,
    ) -> tuple[list[Document], int]:
        matched = [
            document
            for (eng_id, path), document in self._items.items()
            if eng_id == engagement_id
            and (
                prefix is None
                or prefix == ""
                or path == prefix
                or path.startswith(prefix.rstrip("/") + "/")
            )
        ]
        matched.sort(key=lambda item: item.path)
        total = len(matched)
        return matched[offset : offset + limit], total


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
            session
            for session in self._sessions.values()
            if session.engagement_id == engagement_id
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
