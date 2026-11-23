"""Job queue protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from backend.domain.upload import UploadItem, UploadItemId


class JobQueue(Protocol):
    async def enqueue_items(self, items: Sequence[UploadItem]) -> None: ...

    async def claim_next(self, worker_id: str) -> UploadItem | None: ...

    async def complete(self, item_id: UploadItemId, *, status: str, reason: str | None) -> None: ...

    async def fail_for_retry(self, item_id: UploadItemId, *, reason: str) -> None: ...
