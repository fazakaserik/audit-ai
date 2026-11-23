"""Document repository protocol."""

from __future__ import annotations

from typing import Protocol

from backend.domain.document import Document, DocumentPath, FolderPath
from backend.domain.engagement import EngagementId


class DocumentRepository(Protocol):
    async def upsert(self, document: Document) -> Document: ...

    async def get_by_path(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
    ) -> Document | None: ...

    async def delete_by_path(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
    ) -> bool:
        """Delete the document row; return True if a row was removed."""
        ...

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        prefix: FolderPath | None,
        depth: int | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], tuple[str, ...], int]:
        """Return (documents within depth, immediate child folders, document total)."""
        ...
