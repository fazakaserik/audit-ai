"""Sync directory ingest for sample loading (before async upload exists)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from backend.application.llm.embedder import Embedder
from backend.application.parsing.document_chunker import DocumentChunker
from backend.application.parsing.document_parser import DocumentParser
from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.storage.document_storage import DocumentStorage
from backend.application.storage.vector_index import VectorIndex
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.common import new_uuid, utc_now
from backend.domain.document import Document, DocumentId, DocumentPath
from backend.domain.engagement import Engagement, EngagementId
from backend.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class IngestDirectoryResult:
    engagement_id: EngagementId
    documents_indexed: int
    chunks_indexed: int
    skipped: tuple[str, ...]


class IngestDirectoryService:
    def __init__(
        self,
        engagements: EngagementRepository,
        documents: DocumentRepository,
        storage: DocumentStorage,
        vector_index: VectorIndex,
        embedder: Embedder,
        document_parser: DocumentParser,
        document_chunker: DocumentChunker,
    ) -> None:
        self._engagements = engagements
        self._documents = documents
        self._storage = storage
        self._vector_index = vector_index
        self._embedder = embedder
        self._document_parser = document_parser
        self._document_chunker = document_chunker

    async def ingest(
        self,
        *,
        engagement_id: EngagementId,
        engagement_name: str,
        source_dir: Path,
    ) -> IngestDirectoryResult:
        if not source_dir.is_dir():  # noqa: ASYNC240 — sync sample loader
            raise ValidationError(f"source directory not found: {source_dir}")

        existing = await self._engagements.get(engagement_id)
        if existing is None:
            now = utc_now()
            await self._engagements.create(
                Engagement(
                    id=engagement_id,
                    name=engagement_name,
                    created_at=now,
                    updated_at=now,
                )
            )

        skipped: list[str] = []
        docs_indexed = 0
        chunks_indexed = 0

        for path in sorted(source_dir.rglob("*")):  # noqa: ASYNC240 — sync sample loader
            if not path.is_file():
                continue
            rel = path.relative_to(source_dir).as_posix()
            content_type = self._document_parser.detect_content_type(rel)
            if content_type is None:
                skipped.append(rel)
                continue
            data = path.read_bytes()
            document_path: DocumentPath = rel
            await self._storage.put(engagement_id, document_path, data)
            parsed = self._document_parser.parse_bytes(data, path=rel)
            parsed_chunks = self._document_chunker.chunk_document(parsed)
            if not parsed_chunks:
                skipped.append(rel)
                continue

            sha = hashlib.sha256(data).hexdigest()
            prior = await self._documents.get_by_path(engagement_id, document_path)
            version = 1 if prior is None else prior.version + 1
            document_id = prior.id if prior is not None else DocumentId(new_uuid())
            now = utc_now()
            document = Document(
                id=document_id,
                engagement_id=engagement_id,
                path=document_path,
                content_type=content_type,
                size_bytes=len(data),
                sha256=sha,
                version=version,
                searchable=True,
                created_at=prior.created_at if prior is not None else now,
                updated_at=now,
            )
            await self._documents.upsert(document)

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
            embedded = await self._embedder.embed([p.text for p in domain_chunks])
            await self._vector_index.upsert_chunks(
                engagement_id=engagement_id,
                document_id=document_id,
                document_path=document_path,
                document_version=version,
                chunks=domain_chunks,
                embeddings=embedded.vectors,
                embedding_model=self._embedder.model_name,
            )
            docs_indexed += 1
            chunks_indexed += len(domain_chunks)

        return IngestDirectoryResult(
            engagement_id=engagement_id,
            documents_indexed=docs_indexed,
            chunks_indexed=chunks_indexed,
            skipped=tuple(skipped),
        )
