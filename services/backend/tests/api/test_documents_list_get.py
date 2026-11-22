"""API tests: list documents with prefix/depth and download bytes."""

from __future__ import annotations

import hashlib
import uuid

import httpx

from backend.api.dependencies import get_bound
from backend.api.main import create_app
from domain.common import utc_now
from domain.document import ContentType, Document, DocumentId, DocumentPath
from domain.engagement import Engagement, EngagementId
from support.fakes import (
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
)
from support.test_container import build_fakes_bound, build_test_container


async def _seed_documents(
    *,
    engagement_id: EngagementId,
    engagements: InMemoryEngagementRepository,
    documents: InMemoryDocumentRepository,
    storage: InMemoryDocumentStorage,
) -> None:
    now = utc_now()
    await engagements.create(
        Engagement(id=engagement_id, name="Acme FY2025", created_at=now, updated_at=now)
    )
    payloads = {
        "contracts/contoso.pdf": (b"%PDF-1.4 contoso", ContentType.PDF),
        "contracts/acme.md": (b"# Terms\nPayment in 30 days.", ContentType.MARKDOWN),
        "contracts/nested/deep.txt": (b"nested", ContentType.TEXT),
        "policies/refund.txt": (b"Refunds within 14 days.", ContentType.TEXT),
    }
    for path, (data, content_type) in payloads.items():
        doc_path = DocumentPath(path)
        digest = hashlib.sha256(data).hexdigest()
        await documents.upsert(
            Document(
                id=DocumentId(uuid.uuid4()),
                engagement_id=engagement_id,
                path=doc_path,
                content_type=content_type,
                size_bytes=len(data),
                sha256=digest,
                version=1,
                searchable=True,
                created_at=now,
                updated_at=now,
            )
        )
        await storage.put(engagement_id, doc_path, data)


async def test_list_documents_with_prefix_and_depth() -> None:
    engagement_id = EngagementId("acme-fy2025")
    engagements = InMemoryEngagementRepository()
    documents = InMemoryDocumentRepository()
    storage = InMemoryDocumentStorage()
    await _seed_documents(
        engagement_id=engagement_id,
        engagements=engagements,
        documents=documents,
        storage=storage,
    )

    bound = build_fakes_bound(engagements=engagements, documents=documents)
    container = build_test_container(document_storage=storage)
    app = create_app(settings=container.settings, container=container)

    async def override_bound():
        return bound

    app.dependency_overrides[get_bound] = override_bound

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        listed = await client.get(
            f"/api/v1/engagements/{engagement_id}/documents",
            params={"prefix": "contracts"},
        )
        assert listed.status_code == 200
        body = listed.json()
        paths = {item["path"] for item in body["items"]}
        assert paths == {
            "contracts/acme.md",
            "contracts/contoso.pdf",
            "contracts/nested/deep.txt",
        }
        assert body["folders"] == ["nested"]
        assert body["total"] == 3

        shallow = await client.get(
            f"/api/v1/engagements/{engagement_id}/documents",
            params={"prefix": "contracts", "depth": 1},
        )
        assert shallow.status_code == 200
        shallow_body = shallow.json()
        shallow_paths = {item["path"] for item in shallow_body["items"]}
        assert shallow_paths == {"contracts/acme.md", "contracts/contoso.pdf"}
        assert shallow_body["folders"] == ["nested"]
        assert shallow_body["total"] == 2

        root = await client.get(
            f"/api/v1/engagements/{engagement_id}/documents",
            params={"depth": 1},
        )
        assert root.status_code == 200
        root_body = root.json()
        assert root_body["items"] == []
        assert set(root_body["folders"]) == {"contracts", "policies"}

        missing = await client.get(
            f"/api/v1/engagements/{engagement_id}/documents/contracts/missing.pdf",
        )
        assert missing.status_code == 404

        download = await client.get(
            f"/api/v1/engagements/{engagement_id}/documents/contracts/acme.md",
        )
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("text/markdown")
        assert download.content == b"# Terms\nPayment in 30 days."
