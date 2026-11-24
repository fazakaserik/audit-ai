"""Offline lease-holder checks for the in-memory JobQueue fake."""

from __future__ import annotations

import uuid

import pytest

from backend.domain.common import utc_now
from backend.domain.errors import ConflictError
from backend.domain.upload import UploadId, UploadItem, UploadItemId, UploadItemStatus
from support.fakes import InMemoryJobQueue


def _pending_item() -> UploadItem:
    now = utc_now()
    return UploadItem(
        id=UploadItemId(uuid.uuid4()),
        upload_id=UploadId(uuid.uuid4()),
        document_path="docs/a.md",
        status=UploadItemStatus.PENDING,
        created_at=now,
        updated_at=now,
    )


async def test_holder_complete_succeeds() -> None:
    queue = InMemoryJobQueue()
    item = _pending_item()
    await queue.enqueue_items([item])
    claimed = await queue.claim_next("worker-a")
    assert claimed is not None
    await queue.complete(
        claimed.id,
        worker_id="worker-a",
        status="indexed",
        reason=None,
        chunk_count=1,
    )
    done = queue.get(claimed.id)
    assert done is not None
    assert done.status == UploadItemStatus.INDEXED
    assert done.chunk_count == 1


async def test_stale_complete_after_reclaim_raises() -> None:
    queue = InMemoryJobQueue()
    item = _pending_item()
    await queue.enqueue_items([item])
    claimed = await queue.claim_next("worker-a")
    assert claimed is not None
    queue.force_reclaim(claimed.id, worker_id="worker-b")
    with pytest.raises(ConflictError, match="stale job lease"):
        await queue.complete(
            claimed.id,
            worker_id="worker-a",
            status="indexed",
            reason=None,
        )
    current = queue.get(claimed.id)
    assert current is not None
    assert current.status == UploadItemStatus.PROCESSING
    assert queue.locked_by(claimed.id) == "worker-b"


async def test_stale_fail_for_retry_after_reclaim_raises() -> None:
    queue = InMemoryJobQueue()
    item = _pending_item()
    await queue.enqueue_items([item])
    claimed = await queue.claim_next("worker-a")
    assert claimed is not None
    queue.force_reclaim(claimed.id, worker_id="worker-b")
    with pytest.raises(ConflictError, match="stale job lease"):
        await queue.fail_for_retry(claimed.id, worker_id="worker-a", reason="boom")
    assert queue.locked_by(claimed.id) == "worker-b"


async def test_holder_fail_for_retry_returns_to_pending() -> None:
    queue = InMemoryJobQueue()
    item = _pending_item()
    await queue.enqueue_items([item])
    claimed = await queue.claim_next("worker-a")
    assert claimed is not None
    await queue.fail_for_retry(claimed.id, worker_id="worker-a", reason="transient")
    retry = queue.get(claimed.id)
    assert retry is not None
    assert retry.status == UploadItemStatus.PENDING
    assert retry.attempts == 1
    assert retry.reason == "transient"
