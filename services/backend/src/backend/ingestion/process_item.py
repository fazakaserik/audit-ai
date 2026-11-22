"""Worker pipeline: parse, chunk, embed, and upsert one upload item."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from pypdf.errors import PdfReadError

from backend.application.ports import (
    DocumentRepository,
    DocumentStorage,
    Embedder,
    UploadRepository,
    VectorIndex,
)
from backend.ingestion.chunking import chunk_document
from backend.ingestion.parsers import detect_content_type, parse_bytes
from domain.common import new_uuid, utc_now
from domain.document import ContentType, Document, DocumentId, DocumentPath
from domain.engagement import EngagementId
from domain.errors import NotFoundError, UnsafeUploadError, ValidationError
from domain.passage import Passage, PassageId
from domain.upload import UploadItem, UploadItemStatus


@dataclass(frozen=True, slots=True)
class ProcessItemOutcome:
    status: UploadItemStatus
    reason: str | None


async def process_upload_item(
    *,
    item: UploadItem,
    engagement_id: EngagementId,
    documents: DocumentRepository,
    storage: DocumentStorage,
    vector_index: VectorIndex,
    embedder: Embedder,
    uploads: UploadRepository,
) -> ProcessItemOutcome:
    try:
        data = await storage.get(engagement_id, item.document_path)
    except NotFoundError:
        return ProcessItemOutcome(
            status=UploadItemStatus.FAILED,
            reason="stored file missing",
        )

    content_type = detect_content_type(item.document_path)
    if content_type is None:
        return ProcessItemOutcome(
            status=UploadItemStatus.SKIPPED,
            reason="unsupported file extension",
        )

    sha = hashlib.sha256(data).hexdigest()
    now = utc_now()
    prior = await documents.get_by_path(engagement_id, item.document_path)
    version = 1 if prior is None else prior.version + 1
    document_id = prior.id if prior is not None else DocumentId(new_uuid())

    try:
        parsed = parse_bytes(data, path=item.document_path)
        chunks = chunk_document(parsed)
    except (UnsafeUploadError, ValidationError) as exc:
        detail = exc.message
        await _upsert_not_searchable(
            documents=documents,
            engagement_id=engagement_id,
            document_id=document_id,
            document_path=item.document_path,
            content_type=content_type,
            size_bytes=len(data),
            sha256=sha,
            version=version,
            prior=prior,
            now=now,
        )
        await uploads.refresh_status(item.upload_id)
        return ProcessItemOutcome(status=UploadItemStatus.NOT_SEARCHABLE, reason=detail)
    except PdfReadError as exc:
        reason = f"pdf parse failed: {exc}"
        await _upsert_not_searchable(
            documents=documents,
            engagement_id=engagement_id,
            document_id=document_id,
            document_path=item.document_path,
            content_type=content_type,
            size_bytes=len(data),
            sha256=sha,
            version=version,
            prior=prior,
            now=now,
        )
        await uploads.refresh_status(item.upload_id)
        return ProcessItemOutcome(
            status=UploadItemStatus.NOT_SEARCHABLE,
            reason=reason,
        )

    if not chunks:
        return ProcessItemOutcome(
            status=UploadItemStatus.SKIPPED,
            reason="no indexable text",
        )

    document = Document(
        id=document_id,
        engagement_id=engagement_id,
        path=item.document_path,
        content_type=content_type,
        size_bytes=len(data),
        sha256=sha,
        version=version,
        searchable=True,
        created_at=prior.created_at if prior is not None else now,
        updated_at=now,
    )
    await documents.upsert(document)

    passages = [
        Passage(
            id=PassageId(new_uuid()),
            document_id=document_id,
            document_version=version,
            ordinal=chunk.ordinal,
            page=chunk.page,
            heading_path=chunk.heading_path,
            text=chunk.text,
            token_count=chunk.token_count,
            created_at=now,
        )
        for chunk in chunks
    ]
    embeddings = await embedder.embed([p.text for p in passages])
    await vector_index.upsert_passages(
        engagement_id=engagement_id,
        document_id=document_id,
        document_path=item.document_path,
        document_version=version,
        passages=passages,
        embeddings=embeddings,
        embedding_model=embedder.model_name,
    )
    await uploads.refresh_status(item.upload_id)
    return ProcessItemOutcome(status=UploadItemStatus.INDEXED, reason=None)


async def _upsert_not_searchable(
    *,
    documents: DocumentRepository,
    engagement_id: EngagementId,
    document_id: DocumentId,
    document_path: DocumentPath,
    content_type: ContentType,
    size_bytes: int,
    sha256: str,
    version: int,
    prior: Document | None,
    now: datetime,
) -> None:
    document = Document(
        id=document_id,
        engagement_id=engagement_id,
        path=document_path,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        version=version,
        searchable=False,
        created_at=prior.created_at if prior is not None else now,
        updated_at=now,
    )
    await documents.upsert(document)