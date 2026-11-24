"""Postgres job queue using FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.errors import ConflictError
from backend.domain.upload import UploadItem, UploadItemId, UploadItemStatus
from backend.infrastructure.postgres.models import UploadItemRow
from backend.infrastructure.postgres.repositories._mappers import upload_item_from_row

_LEASE_SECONDS = 300
_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 30


class PostgresJobQueue:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue_items(self, items: Sequence[UploadItem]) -> None:
        # Items are persisted by UploadRepository.create; rows are already queued.
        _ = items
        await self._session.flush()

    async def claim_next(self, worker_id: str) -> UploadItem | None:
        now = datetime.now(UTC)
        while True:
            pending_ready = (UploadItemRow.status == UploadItemStatus.PENDING.value) & (
                UploadItemRow.next_attempt_at.is_(None) | (UploadItemRow.next_attempt_at <= now)
            )
            expired_lease = (
                (UploadItemRow.status == UploadItemStatus.PROCESSING.value)
                & UploadItemRow.locked_until.is_not(None)
                & (UploadItemRow.locked_until < now)
            )
            stmt = (
                select(UploadItemRow)
                .where(or_(pending_ready, expired_lease))
                .order_by(UploadItemRow.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            row = (await self._session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None

            expired = (
                row.status == UploadItemStatus.PROCESSING.value
                and row.locked_until is not None
                and row.locked_until < now
            )
            if expired:
                attempts = int(row.attempts) + 1
                row.attempts = attempts
                row.locked_by = None
                row.locked_until = None
                row.updated_at = now
                if attempts >= _MAX_ATTEMPTS:
                    row.status = UploadItemStatus.FAILED.value
                    row.reason = "lease expired too many times"
                    row.next_attempt_at = None
                    row.processing_finished_at = now
                    await self._session.flush()
                    continue
                row.reason = "lease expired; reclaiming"
                # Fall through and re-lock for this worker (counts as a new attempt).

            row.status = UploadItemStatus.PROCESSING.value
            row.locked_by = worker_id
            row.locked_until = now + timedelta(seconds=_LEASE_SECONDS)
            row.processing_started_at = now
            row.processing_finished_at = None
            row.embedding_prompt_tokens = None
            row.embedding_total_tokens = None
            row.chunk_count = None
            row.chunk_token_sum = None
            row.updated_at = now
            await self._session.flush()
            return upload_item_from_row(row)

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
    ) -> None:
        terminal = {
            UploadItemStatus.INDEXED.value,
            UploadItemStatus.SKIPPED.value,
            UploadItemStatus.NOT_SEARCHABLE.value,
            UploadItemStatus.FAILED.value,
        }
        if status not in terminal:
            msg = f"complete status must be terminal, got {status!r}"
            raise ValueError(msg)

        now = datetime.now(UTC)
        stmt = (
            update(UploadItemRow)
            .where(
                UploadItemRow.id == item_id,
                UploadItemRow.locked_by == worker_id,
                UploadItemRow.status == UploadItemStatus.PROCESSING.value,
            )
            .values(
                status=status,
                reason=reason,
                locked_until=None,
                locked_by=None,
                next_attempt_at=None,
                processing_finished_at=now,
                embedding_prompt_tokens=embedding_prompt_tokens,
                embedding_total_tokens=embedding_total_tokens,
                chunk_count=chunk_count,
                chunk_token_sum=chunk_token_sum,
                updated_at=now,
            )
        )
        result = await self._session.execute(stmt)
        if int(getattr(result, "rowcount", 0) or 0) == 0:
            raise ConflictError(f"stale job lease for item {item_id}")
        await self._session.flush()

    async def fail_for_retry(
        self,
        item_id: UploadItemId,
        *,
        worker_id: str,
        reason: str,
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            select(UploadItemRow)
            .where(
                UploadItemRow.id == item_id,
                UploadItemRow.locked_by == worker_id,
                UploadItemRow.status == UploadItemStatus.PROCESSING.value,
            )
            .with_for_update()
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ConflictError(f"stale job lease for item {item_id}")

        attempts: int = int(row.attempts) + 1
        row.attempts = attempts
        row.reason = reason
        row.locked_until = None
        row.locked_by = None
        row.updated_at = now

        if attempts >= _MAX_ATTEMPTS:
            row.status = UploadItemStatus.FAILED.value
            row.next_attempt_at = None
            row.processing_finished_at = now
        else:
            exponent = max(attempts - 1, 0)
            backoff_seconds = float(_BASE_BACKOFF_SECONDS) * (2.0**exponent)
            row.status = UploadItemStatus.PENDING.value
            row.next_attempt_at = now + timedelta(seconds=backoff_seconds)

        await self._session.flush()
