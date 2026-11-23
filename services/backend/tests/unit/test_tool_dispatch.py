"""Unit tests for LLM tool argument dispatch / coercion."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from backend.application.dto import ToolCall
from backend.application.tools import dispatch_tool
from backend.application.tools.base import ToolContext, parse_optional_folder_prefix
from backend.config import Settings
from backend.domain.document import ContentType, Document, DocumentId, DocumentPath
from backend.domain.engagement import Engagement, EngagementId
from support.fakes import (
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)


def _ctx(
    *,
    engagement_id: EngagementId,
    engagements: InMemoryEngagementRepository,
    documents: InMemoryDocumentRepository,
    storage: InMemoryDocumentStorage,
) -> ToolContext:
    return ToolContext(
        engagement_id=engagement_id,
        folder_scope=None,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        engagements=engagements,
        documents=documents,
        storage=storage,
        settings=Settings(relevance_threshold=0.0, retrieval_top_k=8),
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("/", None),
        ("  /  ", None),
        ("finance", "finance"),
        ("finance/", "finance"),
        ("/finance/", "finance"),
    ],
)
def test_parse_optional_folder_prefix(raw: str | None, expected: str | None) -> None:
    assert parse_optional_folder_prefix(raw) == expected


async def test_list_documents_coerces_string_depth_and_limit() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    now = datetime.now(UTC)
    engagements = InMemoryEngagementRepository()
    await engagements.create(Engagement(id=engagement_id, name="N", created_at=now, updated_at=now))
    documents = InMemoryDocumentRepository()
    storage = InMemoryDocumentStorage()
    doc = Document(
        id=DocumentId(uuid.uuid4()),
        engagement_id=engagement_id,
        path=DocumentPath("finance/q1-summary.md"),
        content_type=ContentType.MARKDOWN,
        size_bytes=10,
        sha256="a" * 64,
        version=1,
        searchable=True,
        created_at=now,
        updated_at=now,
    )
    await documents.upsert(doc)

    result = await dispatch_tool(
        _ctx(
            engagement_id=engagement_id,
            engagements=engagements,
            documents=documents,
            storage=storage,
        ),
        ToolCall(
            id="t1",
            name="list_documents",
            # Models commonly emit integers as JSON strings.
            arguments=json.dumps({"prefix": "/", "depth": "1", "limit": "50"}),
        ),
    )
    assert "validation error" not in result.summary
    assert "folders:" in result.content
    assert "finance" in result.content


async def test_get_current_time_returns_host_local() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    now = datetime.now(UTC)
    engagements = InMemoryEngagementRepository()
    await engagements.create(Engagement(id=engagement_id, name="N", created_at=now, updated_at=now))
    documents = InMemoryDocumentRepository()
    storage = InMemoryDocumentStorage()

    ctx = _ctx(
        engagement_id=engagement_id,
        engagements=engagements,
        documents=documents,
        storage=storage,
    )
    result = await dispatch_tool(
        ctx,
        ToolCall(id="t1", name="get_current_time", arguments="{}"),
    )
    assert "validation error" not in result.summary
    assert result.content.startswith("current_time=")
    assert "timezone=" in result.content
    assert "weekday=" in result.content
    assert "get_current_time →" in result.summary
    assert ctx.tool_facts == [result.content]
