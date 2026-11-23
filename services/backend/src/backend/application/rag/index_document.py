"""Shared embed-and-index path for parsed document chunks."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from backend.application.dto import ParsedChunk
from backend.application.llm.embedder import Embedder
from backend.application.repositories.document import DocumentRepository
from backend.application.storage.vector_index import VectorIndex
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.common import new_uuid
from backend.domain.document import ContentType, Document, DocumentId, DocumentPath
from backend.domain.engagement import EngagementId


async def index_document_chunks(
    *,
    documents: DocumentRepository,
    vector_index: VectorIndex,
    embedder: Embedder,
    engagement_id: EngagementId,
    document_id: DocumentId,
    document_path: DocumentPath,
    content_type: ContentType,
    size_bytes: int,
    sha256: str,
    version: int,
    prior: Document | None,
    now: datetime,
    parsed_chunks: Sequence[ParsedChunk],
    searchable: bool = True,
) -> int:
    """Persist document metadata, embed chunks, and upsert vectors. Returns chunk count."""
    if not parsed_chunks:
        return 0

    document = Document(
        id=document_id,
        engagement_id=engagement_id,
        path=document_path,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        version=version,
        searchable=searchable,
        created_at=prior.created_at if prior is not None else now,
        updated_at=now,
    )
    await documents.upsert(document)

    domain_chunks = [
        Chunk(
            id=ChunkId(new_uuid()),
            document_id=document_id,
            document_version=version,
            ordinal=chunk.ordinal,
            page=chunk.page,
            heading_path=chunk.heading_path,
            text=chunk.text,
            token_count=chunk.token_count,
            created_at=now,
        )
        for chunk in parsed_chunks
    ]
    embedded = await embedder.embed([piece.text for piece in domain_chunks])
    await vector_index.upsert_chunks(
        engagement_id=engagement_id,
        document_id=document_id,
        document_path=document_path,
        document_version=version,
        chunks=domain_chunks,
        embeddings=embedded.vectors,
        embedding_model=embedder.model_name,
    )
    return len(domain_chunks)
