"""Storage, vector index, and job queue ports."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from backend.application.dto import RetrievalScope, ScoredChunk
from backend.domain.chunk import Chunk
from backend.domain.document import DocumentId, DocumentPath
from backend.domain.engagement import EngagementId
from backend.domain.upload import UploadItem, UploadItemId


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


class JobQueue(Protocol):
    async def enqueue_items(self, items: Sequence[UploadItem]) -> None: ...

    async def claim_next(self, worker_id: str) -> UploadItem | None: ...

    async def complete(self, item_id: UploadItemId, *, status: str, reason: str | None) -> None: ...

    async def fail_for_retry(self, item_id: UploadItemId, *, reason: str) -> None: ...
