"""API tests for engagement rename/delete and document delete."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from backend.application.api.dependencies import get_bound
from backend.application.api.main import create_app
from backend.domain.common import utc_now
from backend.domain.document import ContentType, Document, DocumentId, DocumentPath
from backend.domain.engagement import Engagement, EngagementId
from support.fakes import (
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
)
from support.test_container import build_fakes_bound, build_test_container


async def test_rename_and_delete_engagement() -> None:
    engagement_id = EngagementId("acme-fy2025")
    engagements = InMemoryEngagementRepository()
    storage = InMemoryDocumentStorage()
    now = utc_now()
    await engagements.create(
        Engagement(id=engagement_id, name="Acme", created_at=now, updated_at=now)
    )
    await storage.put(engagement_id, "policies/a.md", b"hello")

    bound = build_fakes_bound(engagements=engagements, storage=storage)
    container = build_test_container()
    app = create_app(settings=container.settings, container=container)

    async def override_bound():
        return bound

    app.dependency_overrides[get_bound] = override_bound

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        renamed = await client.patch(
            f"/api/v1/engagements/{engagement_id}",
            json={"name": "Acme Renamed"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Acme Renamed"

        deleted = await client.delete(f"/api/v1/engagements/{engagement_id}")
        assert deleted.status_code == 204

        missing = await client.get(f"/api/v1/engagements/{engagement_id}")
        assert missing.status_code == 404

    assert await engagements.get(engagement_id) is None
    assert storage._blobs == {}


async def test_delete_document() -> None:
    engagement_id = EngagementId("acme-fy2025")
    path: DocumentPath = "policies/a.md"
    engagements = InMemoryEngagementRepository()
    documents = InMemoryDocumentRepository()
    storage = InMemoryDocumentStorage()
    now = utc_now()
    await engagements.create(
        Engagement(id=engagement_id, name="Acme", created_at=now, updated_at=now)
    )
    await documents.upsert(
        Document(
            id=DocumentId(uuid.uuid4()),
            engagement_id=engagement_id,
            path=path,
            content_type=ContentType.MARKDOWN,
            size_bytes=5,
            sha256="a" * 64,
            version=1,
            searchable=True,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    await storage.put(engagement_id, path, b"hello")
    engagements.set_document_count(engagement_id, 1)

    bound = build_fakes_bound(
        engagements=engagements,
        documents=documents,
        storage=storage,
    )
    container = build_test_container()
    app = create_app(settings=container.settings, container=container)

    async def override_bound():
        return bound

    app.dependency_overrides[get_bound] = override_bound

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        deleted = await client.delete(f"/api/v1/engagements/{engagement_id}/documents/{path}")
        assert deleted.status_code == 204
        missing = await client.get(f"/api/v1/engagements/{engagement_id}/documents/{path}")
        assert missing.status_code == 404

    assert await documents.get_by_path(engagement_id, path) is None
    assert (engagement_id, path) not in storage._blobs
