"""Postgres engagement repository adapter."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.engagement import Engagement, EngagementId
from backend.domain.errors import ConflictError
from backend.infrastructure.postgres.models import DocumentRow, EngagementRow
from backend.infrastructure.postgres.repositories._mappers import engagement_from_row


class PostgresEngagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, engagement: Engagement) -> Engagement:
        row = EngagementRow(
            id=engagement.id,
            name=engagement.name,
            created_at=engagement.created_at,
            updated_at=engagement.updated_at,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(f"engagement already exists: {engagement.id}") from exc
        return engagement_from_row(row)

    async def get(self, engagement_id: EngagementId) -> Engagement | None:
        row = await self._session.get(EngagementRow, engagement_id)
        if row is None:
            return None
        return engagement_from_row(row)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Engagement], int]:
        total_stmt = select(func.count()).select_from(EngagementRow)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(EngagementRow)
            .order_by(EngagementRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [engagement_from_row(row) for row in rows], total

    async def count_documents(self, engagement_id: EngagementId) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentRow)
            .where(DocumentRow.engagement_id == engagement_id)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def count_documents_for_engagements(
        self,
        engagement_ids: Sequence[EngagementId],
    ) -> dict[EngagementId, int]:
        if not engagement_ids:
            return {}
        stmt = (
            select(DocumentRow.engagement_id, func.count())
            .where(DocumentRow.engagement_id.in_(engagement_ids))
            .group_by(DocumentRow.engagement_id)
        )
        rows = (await self._session.execute(stmt)).all()
        counts = {engagement_id: 0 for engagement_id in engagement_ids}
        for engagement_id, count in rows:
            counts[engagement_id] = int(count)
        return counts
