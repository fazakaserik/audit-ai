"""Worker fail-closed when chunk count exceeds ingest_max_chunks."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from backend.application.dto import ParsedChunk, ParsedDocument, ParsedSection
from backend.application.rag.worker.process_item import process_upload_item
from backend.config import Settings
from backend.domain.common import utc_now
from backend.domain.document import ContentType
from backend.domain.engagement import EngagementId
from backend.domain.upload import UploadId, UploadItem, UploadItemId, UploadItemStatus
from support.fakes import FakeEmbedder, InMemoryDocumentRepository, InMemoryDocumentStorage


class _Parser:
    def detect_content_type(self, path: str) -> ContentType | None:
        _ = path
        return ContentType.TEXT

    def parse_bytes(self, data: bytes, *, path: str) -> ParsedDocument:
        _ = (data, path)
        return ParsedDocument(
            content_type=ContentType.TEXT,
            sections=(ParsedSection(text="hello", heading_path=(), page=None),),
        )

    def to_markdown(self, data: bytes, *, path: str) -> str:
        _ = (data, path)
        return "hello"


class _Chunker:
    def chunk_document(self, parsed: ParsedDocument) -> list[ParsedChunk]:
        _ = parsed
        return [
            ParsedChunk(
                text=f"c{i}",
                heading_path=(),
                page=None,
                token_count=1,
                ordinal=i,
            )
            for i in range(5)
        ]


async def test_process_item_fails_when_chunks_exceed_limit() -> None:
    settings = Settings(ingest_max_chunks=2)
    engagement_id = EngagementId("eng-chunks")
    storage = InMemoryDocumentStorage()
    await storage.put(engagement_id, "notes/a.txt", b"hello")
    now = utc_now()
    item = UploadItem(
        id=UploadItemId(uuid.uuid4()),
        upload_id=UploadId(uuid.uuid4()),
        document_path="notes/a.txt",
        status=UploadItemStatus.PROCESSING,
        created_at=now,
        updated_at=now,
    )
    outcome = await process_upload_item(
        item=item,
        engagement_id=engagement_id,
        documents=InMemoryDocumentRepository(),
        storage=storage,
        vector_index=AsyncMock(),
        embedder=FakeEmbedder(),
        document_parser=_Parser(),
        document_chunker=_Chunker(),
        settings=settings,
    )
    assert outcome.status == UploadItemStatus.FAILED
    assert outcome.reason is not None
    assert "max chunks" in outcome.reason
