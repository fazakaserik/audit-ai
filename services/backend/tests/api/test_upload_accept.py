"""API tests for async document upload acceptance."""

from __future__ import annotations

import io
import zipfile

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.api.dependencies import get_bound
from backend.application.api.main import create_app
from backend.config import Settings
from backend.domain.common import utc_now
from backend.domain.engagement import Engagement, EngagementId
from support.fakes import InMemoryEngagementRepository
from support.test_container import build_fakes_bound, build_test_container


def _build_upload_app(*, settings: Settings | None = None):
    engagements = InMemoryEngagementRepository()

    async def _prepare(engagement_id: EngagementId = "northwind-fy2025"):
        now = utc_now()
        await engagements.create(
            Engagement(
                id=engagement_id,
                name="Northwind",
                created_at=now,
                updated_at=now,
            )
        )
        cfg = settings or Settings()
        bound = build_fakes_bound(engagements=engagements, settings=cfg)
        container = build_test_container(settings=cfg)
        app = create_app(settings=cfg, container=container)

        async def override_bound():
            return bound

        app.dependency_overrides[get_bound] = override_bound
        return app, bound

    return _prepare


@pytest.fixture
def upload_app_factory():
    return _build_upload_app()


async def test_upload_returns_202_queued(upload_app_factory) -> None:
    app, _bound = await upload_app_factory()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/engagements/northwind-fy2025/documents",
            data={"folder": "policies"},
            files=[("files", ("readme.md", b"# Policy", "text/markdown"))],
        )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert "upload_id" in body
    assert "request_id" in body


async def test_oversized_upload_returns_413(upload_app_factory) -> None:
    prepare = _build_upload_app(settings=Settings(upload_max_bytes=10))
    app, _bound = await prepare()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/engagements/northwind-fy2025/documents",
            data={"folder": "inbox"},
            files=[("files", ("big.txt", b"x" * 64, "text/plain"))],
        )
    assert response.status_code == 413, response.text
    assert response.json()["code"] == "payload_too_large"


async def test_unsafe_zip_returns_400(upload_app_factory) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../../escape.txt", b"nope")
    app, bound = await upload_app_factory()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/engagements/northwind-fy2025/documents",
            data={"folder": "inbox"},
            files=[("files", ("evil.zip", buffer.getvalue(), "application/zip"))],
        )
    assert response.status_code == 400
    assert response.json()["code"] == "unsafe_upload"
    assert len(bound.documents._documents._items) == 0


async def test_oversized_file_part_returns_413() -> None:
    prepare = _build_upload_app(settings=Settings(upload_max_file_bytes=32, upload_max_bytes=1024))
    app, _bound = await prepare()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/engagements/northwind-fy2025/documents",
            data={"folder": "inbox"},
            files=[("files", ("big.txt", b"x" * 64, "text/plain"))],
        )
    assert response.status_code == 413, response.text
    assert response.json()["code"] == "payload_too_large"


async def test_too_many_files_returns_413() -> None:
    prepare = _build_upload_app(settings=Settings(upload_max_files=1))
    app, _bound = await prepare()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/engagements/northwind-fy2025/documents",
            data={"folder": "inbox"},
            files=[
                ("files", ("a.txt", b"a", "text/plain")),
                ("files", ("b.txt", b"b", "text/plain")),
            ],
        )
    assert response.status_code == 413, response.text
    assert response.json()["code"] == "payload_too_large"


async def test_zip_member_over_limit_returns_413() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("member.txt", b"x" * 200)
    prepare = _build_upload_app(
        settings=Settings(
            upload_max_file_bytes=50,
            upload_max_bytes=10_000,
            upload_max_files=10,
        )
    )
    app, bound = await prepare()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/engagements/northwind-fy2025/documents",
            data={"folder": "inbox"},
            files=[("files", ("pack.zip", buffer.getvalue(), "application/zip"))],
        )
    assert response.status_code == 413, response.text
    assert response.json()["code"] == "payload_too_large"
    assert len(bound.documents._documents._items) == 0


async def test_zip_rejected_when_prior_files_consume_byte_budget() -> None:
    """Zip that fits under the full cap still 413s when earlier parts leave no room."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("extra.txt", b"y" * 40)
    prepare = _build_upload_app(
        settings=Settings(
            upload_max_file_bytes=100,
            upload_max_bytes=50,
            upload_max_files=10,
        )
    )
    app, bound = await prepare()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/engagements/northwind-fy2025/documents",
            data={"folder": "inbox"},
            files=[
                ("files", ("first.txt", b"x" * 30, "text/plain")),
                ("files", ("pack.zip", buffer.getvalue(), "application/zip")),
            ],
        )
    assert response.status_code == 413, response.text
    assert response.json()["code"] == "payload_too_large"
    assert len(bound.documents._documents._items) == 0
