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

    async def list_document_chunks(
        self,
        *,
        engagement_id: EngagementId,
        document_id: DocumentId,
    ) -> list[ScoredChunk]:
        rows = [
            row
            for row in self._rows
            if row.engagement_id == engagement_id and row.document_id == document_id
        ]
        rows.sort(key=lambda row: row.chunk.ordinal)
        return [
            ScoredChunk(chunk=row.chunk, document_path=row.document_path, score=1.0)
            for row in rows
        ]

    async def search(
        self,
        query: str,
        query_embedding: Sequence[float],
        scope: RetrievalScope,
        *,
        embedding_model: str,
        min_score: float,
    ) -> list[ScoredChunk]:
        """Cosine survivors RRF-merged with simple token FTS (mirrors Postgres adapter)."""
        tokens = {token.lower() for token in query.split() if len(token) > 1}
        vector_hits: list[ScoredChunk] = []
        fts_hits: list[ScoredChunk] = []
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
            if score >= min_score:
                vector_hits.append(
                    ScoredChunk(
                        chunk=row.chunk,
                        document_path=row.document_path,
                        score=score,
                    )
                )
            text_lower = row.chunk.text.lower()
            if tokens and any(token in text_lower for token in tokens):
                fts_hits.append(
                    ScoredChunk(
                        chunk=row.chunk,
                        document_path=row.document_path,
                        score=min_score if score < min_score else score,
                    )
                )
        vector_hits.sort(key=lambda item: item.score, reverse=True)
        # Prefer chunks that appear in both lists, then fill from each.
        by_id: dict[object, ScoredChunk] = {}
        for hit in vector_hits:
            by_id[hit.chunk.id] = hit
        for hit in fts_hits:
            by_id.setdefault(hit.chunk.id, hit)
        fused = sorted(by_id.values(), key=lambda item: item.score, reverse=True)
        return fused[: scope.top_k]
