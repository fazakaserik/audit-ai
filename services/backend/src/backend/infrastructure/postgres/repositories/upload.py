"""Postgres upload repository adapter."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError
from backend.domain.upload import (
    Upload,
    UploadId,
    UploadItem,
    UploadItemStatus,
    UploadStatus,
)
from backend.infrastructure.postgres.models import UploadItemRow, UploadRow
from backend.infrastructure.postgres.repositories._mappers import (
    upload_from_row,
    upload_item_from_row,
)


class PostgresUploadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, upload: Upload, items: Sequence[UploadItem]) -> Upload:
        now = datetime.now(UTC)
        self._session.add(
            UploadRow(
                id=upload.id,
                engagement_id=upload.engagement_id,
                target_folder=upload.target_folder,
                status=upload.status.value,
                completed_at=upload.completed_at,
                created_at=upload.created_at,
                updated_at=upload.updated_at,
            )
        )
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
        return upload

    async def get(
        self,
        engagement_id: EngagementId,
        upload_id: UploadId,
    ) -> tuple[Upload, list[UploadItem]] | None:
        stmt = select(UploadRow).where(
            UploadRow.id == upload_id,
            UploadRow.engagement_id == engagement_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        items_stmt = (
            select(UploadItemRow)
            .where(UploadItemRow.upload_id == upload_id)
            .order_by(UploadItemRow.created_at.asc())
        )
        item_rows = (await self._session.execute(items_stmt)).scalars().all()
        return upload_from_row(row), [upload_item_from_row(r) for r in item_rows]

    async def get_by_id(self, upload_id: UploadId) -> Upload | None:
        row = await self._session.get(UploadRow, upload_id)
        if row is None:
            return None
        return upload_from_row(row)

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Upload], int]:
        filters = [UploadRow.engagement_id == engagement_id]
        total_stmt = select(func.count()).select_from(UploadRow).where(*filters)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(UploadRow)
            .where(*filters)
            .order_by(UploadRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [upload_from_row(row) for row in rows], total

    async def mark_processing(self, upload_id: UploadId) -> None:
        row = await self._session.get(UploadRow, upload_id)
        if row is None:
            return
        if row.status == UploadStatus.QUEUED.value:
            now = datetime.now(UTC)
            row.status = UploadStatus.PROCESSING.value
            row.updated_at = now
            await self._session.flush()

    async def refresh_status(self, upload_id: UploadId) -> Upload:
        row = await self._session.get(UploadRow, upload_id)
        if row is None:
            raise NotFoundError(f"upload not found: {upload_id}")

        items_stmt = select(UploadItemRow).where(UploadItemRow.upload_id == upload_id)
        item_rows = (await self._session.execute(items_stmt)).scalars().all()
        statuses = {UploadItemStatus(r.status) for r in item_rows}
        terminal = {
            UploadItemStatus.INDEXED,
            UploadItemStatus.SKIPPED,
            UploadItemStatus.NOT_SEARCHABLE,
            UploadItemStatus.FAILED,
        }
        now = datetime.now(UTC)
        if statuses and statuses <= terminal:
            row.status = UploadStatus.COMPLETED.value
            row.completed_at = now
        elif UploadItemStatus.PROCESSING in statuses or any(s in terminal for s in statuses):
            row.status = UploadStatus.PROCESSING.value
        else:
            row.status = UploadStatus.QUEUED.value
        row.updated_at = now
        await self._session.flush()
        return upload_from_row(row)
