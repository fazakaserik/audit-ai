"""Vector index protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from backend.application.dto import RetrievalScope, ScoredChunk
from backend.domain.chunk import Chunk
from backend.domain.document import DocumentId, DocumentPath
from backend.domain.engagement import EngagementId


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
