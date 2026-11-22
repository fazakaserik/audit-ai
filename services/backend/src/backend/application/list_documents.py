"""List documents under an engagement with optional folder prefix."""

from __future__ import annotations

from dataclasses import dataclass

from backend.application.ports import DocumentRepository, EngagementRepository
from domain.document import Document, FolderPath
from domain.engagement import EngagementId
from domain.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class ListDocumentsResult:
    items: tuple[Document, ...]
    total: int


async def list_documents(
    engagements: EngagementRepository,
    documents: DocumentRepository,
    *,
    engagement_id: EngagementId,
    prefix: FolderPath | None,
    limit: int,
    offset: int,
) -> ListDocumentsResult:
    engagement = await engagements.get(engagement_id)
    if engagement is None:
        raise NotFoundError(f"engagement not found: {engagement_id}")

    items, total = await documents.list(
        engagement_id,
        prefix=prefix,
        limit=limit,
        offset=offset,
    )
    return ListDocumentsResult(items=tuple(items), total=total)