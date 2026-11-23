"""Load document metadata and raw bytes."""

from __future__ import annotations

from dataclasses import dataclass

from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.storage.document_storage import DocumentStorage
from backend.domain.document import ContentType, Document, DocumentPath
from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError

_CONTENT_TYPE_TO_MEDIA: dict[ContentType, str] = {
    ContentType.MARKDOWN: "text/markdown",
    ContentType.TEXT: "text/plain",
    ContentType.PDF: "application/pdf",
}


def media_type_for_content_type(content_type: ContentType) -> str:
    return _CONTENT_TYPE_TO_MEDIA[content_type]


@dataclass(frozen=True, slots=True)
class GetDocumentResult:
    document: Document
    data: bytes
    media_type: str


async def get_document(
    engagements: EngagementRepository,
    documents: DocumentRepository,
    storage: DocumentStorage,
    *,
    engagement_id: EngagementId,
    path: DocumentPath,
) -> GetDocumentResult:
    engagement = await engagements.get(engagement_id)
    if engagement is None:
        raise NotFoundError(f"engagement not found: {engagement_id}")

    document = await documents.get_by_path(engagement_id, path)
    if document is None:
        raise NotFoundError(f"document not found: {path}")

    data = await storage.get(engagement_id, path)
    media_type = media_type_for_content_type(document.content_type)
    return GetDocumentResult(document=document, data=data, media_type=media_type)
