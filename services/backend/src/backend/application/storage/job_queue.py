"""Job queue protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from backend.domain.upload import UploadItem, UploadItemId


class JobQueue(Protocol):
    async def enqueue_items(self, items: Sequence[UploadItem]) -> None: ...

    async def claim_next(self, worker_id: str) -> UploadItem | None: ...

    async def complete(
        self,
        item_id: UploadItemId,
        *,
        worker_id: str,
        status: str,
        reason: str | None,
        embedding_prompt_tokens: int | None = None,
        embedding_total_tokens: int | None = None,
        chunk_count: int | None = None,
        chunk_token_sum: int | None = None,
    ) -> None: ...

    async def fail_for_retry(
        self,
        item_id: UploadItemId,
        *,
        worker_id: str,
        reason: str,
    ) -> None: ...
