"""Postgres job queue using FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.adapters.postgres.models import UploadItemRow
from domain.upload import UploadId, UploadItem, UploadItemId, UploadItemStatus

_LEASE_SECONDS = 300
_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 30


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _item_from_row(row: UploadItemRow) -> UploadItem:
    return UploadItem(
        id=UploadItemId(row.id),
        upload_id=UploadId(row.upload_id),
        document_path=row.document_path,
        status=UploadItemStatus(row.status),
        reason=row.reason,
        attempts=row.attempts,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


class PostgresJobQueue:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue_items(self, items: Sequence[UploadItem]) -> None:
        now = datetime.now(UTC)
        for item in items:
            self._session.add(
                UploadItemRow(
                    id=item.id,
                    upload_id=item.upload_id,
                    document_path=item.document_path,
                    status=item.status.value,
                    reason=item.reason,
                    attempts=item.attempts,
                    locked_until=None,
                    locked_by=None,
                    next_attempt_at=None,
                    raw_storage_key=item.document_path,
                    created_at=item.created_at,
                    updated_at=item.updated_at if item.updated_at else now,
                )
            )
        await self._session.flush()

    async def claim_next(self, worker_id: str) -> UploadItem | None:
        now = datetime.now(UTC)
        pending_ready = (
            (UploadItemRow.status == UploadItemStatus.PENDING.value)
            & (
                UploadItemRow.next_attempt_at.is_(None)
                | (UploadItemRow.next_attempt_at <= now)
            )
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

        row.status = UploadItemStatus.PROCESSING.value
        row.locked_by = worker_id
        row.locked_until = now + timedelta(seconds=_LEASE_SECONDS)
        row.updated_at = now
        await self._session.flush()
        return _item_from_row(row)

    async def complete(
        self,
        item_id: UploadItemId,
        *,
        status: str,
        reason: str | None,
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
            .where(UploadItemRow.id == item_id)
            .values(
                status=status,
                reason=reason,
                locked_until=None,
                locked_by=None,
                next_attempt_at=None,
                updated_at=now,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def fail_for_retry(self, item_id: UploadItemId, *, reason: str) -> None:
        now = datetime.now(UTC)
        row = await self._session.get(UploadItemRow, item_id)
        if row is None:
            return

        attempts = row.attempts + 1
        row.attempts = attempts
        row.reason = reason
        row.locked_until = None
        row.locked_by = None
        row.updated_at = now

        if attempts >= _MAX_ATTEMPTS:
            row.status = UploadItemStatus.FAILED.value
            row.next_attempt_at = None
        else:
            backoff = _BASE_BACKOFF_SECONDS * (2 ** (attempts - 1))
            row.status = UploadItemStatus.PENDING.value
            row.next_attempt_at = now + timedelta(seconds=backoff)

        await self._session.flush()
