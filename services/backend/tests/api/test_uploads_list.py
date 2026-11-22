"""API tests for listing upload jobs."""

from __future__ import annotations

import uuid
from datetime import timedelta

from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_bound
from backend.api.main import create_app
from domain.common import utc_now
from domain.engagement import Engagement, EngagementId
from domain.upload import Upload, UploadId, UploadStatus
from support.fakes import InMemoryEngagementRepository, InMemoryUploadRepository
from support.test_container import build_fakes_bound, build_test_container


async def test_list_uploads_newest_first() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    engagements = InMemoryEngagementRepository()
    uploads = InMemoryUploadRepository()
    now = utc_now()
    await engagements.create(
        Engagement(id=engagement_id, name="Northwind", created_at=now, updated_at=now)
    )
    older_id = UploadId(uuid.uuid4())
    newer_id = UploadId(uuid.uuid4())
    await uploads.create(
        Upload(
            id=older_id,
            engagement_id=engagement_id,
            target_folder="policies",
            status=UploadStatus.COMPLETED,
            completed_at=now,
            created_at=now,
            updated_at=now,
        ),
        [],
    )
    await uploads.create(
        Upload(
            id=newer_id,
            engagement_id=engagement_id,
            target_folder="contracts",
            status=UploadStatus.QUEUED,
            completed_at=None,
            created_at=now + timedelta(seconds=1),
            updated_at=now + timedelta(seconds=1),
        ),
        [],
    )

    bound = build_fakes_bound(engagements=engagements, uploads=uploads)
    container = build_test_container()
    app = create_app(settings=container.settings, container=container)

    async def override_bound():
        return bound

    app.dependency_overrides[get_bound] = override_bound

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/engagements/{engagement_id}/uploads")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [str(newer_id), str(older_id)]
    assert "items" not in body["items"][0]
    assert body["items"][0]["target_folder"] == "contracts"
