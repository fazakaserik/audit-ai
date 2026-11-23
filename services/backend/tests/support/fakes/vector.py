"""In-memory vector index fake."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from backend.application.dto import RetrievalScope, ScoredChunk
from backend.domain.chunk import Chunk
from backend.domain.document import DocumentId, DocumentPath
from backend.domain.engagement import EngagementId


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
