"""Worker pipeline: parse, chunk, embed, and upsert one upload item."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from backend.application.llm.embedder import Embedder
from backend.application.parsing.document_chunker import DocumentChunker
from backend.application.parsing.document_parser import DocumentParser
from backend.application.rag.index_document import index_document_chunks
from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.upload import UploadRepository
from backend.application.storage.document_storage import DocumentStorage
from backend.application.storage.vector_index import VectorIndex
from backend.domain.common import new_uuid, utc_now
from backend.domain.document import ContentType, Document, DocumentId, DocumentPath
from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError, UnsafeUploadError, ValidationError
from backend.domain.upload import UploadItem, UploadItemStatus
from backend.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProcessItemOutcome:
    status: UploadItemStatus
    reason: str | None
    embedding_prompt_tokens: int | None = None
    embedding_total_tokens: int | None = None
    chunk_count: int | None = None
    chunk_token_sum: int | None = None


async def process_upload_item(
    *,
    item: UploadItem,
    engagement_id: EngagementId,
    documents: DocumentRepository,
    storage: DocumentStorage,
    vector_index: VectorIndex,
    embedder: Embedder,
    uploads: UploadRepository,
    document_parser: DocumentParser,
    document_chunker: DocumentChunker,
) -> ProcessItemOutcome:
    path = item.document_path
    log.info("ingest_start", path=path, engagement_id=engagement_id)
    try:
        data = await storage.get(engagement_id, path)
    except NotFoundError:
        log.warning("ingest_missing_file", path=path)
        return ProcessItemOutcome(
            status=UploadItemStatus.FAILED,
            reason="stored file missing",
        )

    content_type = document_parser.detect_content_type(path)
    if content_type is None:
        log.info("ingest_skipped", path=path, reason="unsupported file extension")
        return ProcessItemOutcome(
            status=UploadItemStatus.SKIPPED,
            reason="unsupported file extension",
        )

    sha = hashlib.sha256(data).hexdigest()
    now = utc_now()
    prior = await documents.get_by_path(engagement_id, path)
    version = 1 if prior is None else prior.version + 1
    document_id = prior.id if prior is not None else DocumentId(new_uuid())
    log.info(
        "ingest_loaded",
        path=path,
        size_bytes=len(data),
        content_type=content_type.value,
        version=version,
    )

    try:
        parsed = document_parser.parse_bytes(data, path=path)
        chunks = document_chunker.chunk_document(parsed)
    except (UnsafeUploadError, ValidationError) as exc:
        detail = exc.message
        log.warning("ingest_not_searchable", path=path, reason=detail)
        await _upsert_not_searchable(
            documents=documents,
            engagement_id=engagement_id,
            document_id=document_id,
            document_path=path,
            content_type=content_type,
            size_bytes=len(data),
            sha256=sha,
            version=version,
            prior=prior,
            now=now,
        )
        await uploads.refresh_status(item.upload_id)
        return ProcessItemOutcome(status=UploadItemStatus.NOT_SEARCHABLE, reason=detail)

    if not chunks:
        log.info("ingest_skipped", path=path, reason="no indexable text")
        return ProcessItemOutcome(
            status=UploadItemStatus.SKIPPED,
            reason="no indexable text",
        )

    log.info("ingest_chunked", path=path, chunk_count=len(chunks))
    log.info(
        "ingest_embed_start",
        path=path,
        chunk_count=len(chunks),
        model=embedder.model_name,
    )
    indexed = await index_document_chunks(
        documents=documents,
        vector_index=vector_index,
        embedder=embedder,
        engagement_id=engagement_id,
        document_id=document_id,
        document_path=path,
        content_type=content_type,
        size_bytes=len(data),
        sha256=sha,
        version=version,
        prior=prior,
        now=now,
        parsed_chunks=chunks,
    )
    usage = indexed.embedding_usage
    log.info(
        "ingest_embed_done",
        path=path,
        vector_count=indexed.chunk_count,
        embedding_total_tokens=usage.total_tokens,
    )
    await uploads.refresh_status(item.upload_id)
    log.info(
        "ingest_indexed",
        path=path,
        chunk_count=indexed.chunk_count,
        chunk_token_sum=indexed.chunk_token_sum,
        embedding_total_tokens=usage.total_tokens,
        version=version,
    )
    return ProcessItemOutcome(
        status=UploadItemStatus.INDEXED,
        reason=None,
        embedding_prompt_tokens=usage.prompt_tokens,
        embedding_total_tokens=usage.total_tokens,
        chunk_count=indexed.chunk_count,
        chunk_token_sum=indexed.chunk_token_sum,
    )


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
