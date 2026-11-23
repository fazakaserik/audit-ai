"""In-memory document blob storage fake."""

from __future__ import annotations

from pathlib import Path

from backend.domain.document import DocumentPath
from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError


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

    async def delete_engagement(self, engagement_id: EngagementId) -> None:
        stale = [key for key in self._blobs if key[0] == engagement_id]
        for key in stale:
            del self._blobs[key]
