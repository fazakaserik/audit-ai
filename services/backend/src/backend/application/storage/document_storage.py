"""Document storage protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from backend.domain.document import DocumentPath
from backend.domain.engagement import EngagementId


class DocumentStorage(Protocol):
    async def put(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
        data: bytes,
    ) -> Path: ...

    async def get(self, engagement_id: EngagementId, path: DocumentPath) -> bytes: ...

    async def delete(self, engagement_id: EngagementId, path: DocumentPath) -> None: ...
