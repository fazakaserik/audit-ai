"""Hybrid vector + FTS index with reciprocal rank fusion."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.adapters.postgres.models import DocumentRow, PassageRow
from backend.application.ports import RetrievalScope, ScoredPassage
from domain.document import DocumentId, DocumentPath
from domain.engagement import EngagementId
from domain.passage import Passage, PassageId

_RRF_K = 60


def _passage_from_row(row: PassageRow) -> Passage:
    heading = tuple(row.heading_path) if row.heading_path else ()
    return Passage(
        id=PassageId(row.id),
        document_id=DocumentId(row.document_id),
        document_version=row.document_version,
        ordinal=row.ordinal,
        page=row.page,
        heading_path=heading,
        text=row.text,
        token_count=row.token_count,
        created_at=row.created_at,
    )


def _rrf_merge(
    vector_ids: Sequence[UUID],
    fts_ids: Sequence[UUID],
    *,
    k: int = _RRF_K,
) -> list[UUID]:
    scores: dict[UUID, float] = {}
    for rank, passage_id in enumerate(vector_ids, start=1):
        scores[passage_id] = scores.get(passage_id, 0.0) + 1.0 / (k + rank)
    for rank, passage_id in enumerate(fts_ids, start=1):
        scores[passage_id] = scores.get(passage_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.keys(), key=lambda pid: scores[pid], reverse=True)


def _scoped_passage_filters(
    scope: RetrievalScope,
    *,
    embedding_model: str,
) -> list[object]:
    filters: list[object] = [
        DocumentRow.engagement_id == scope.engagement_id,
        DocumentRow.version == PassageRow.document_version,
        DocumentRow.searchable.is_(True),
        PassageRow.embedding_model == embedding_model,
        PassageRow.embedding.is_not(None),
    ]
    if scope.folder_prefix is not None and scope.folder_prefix != "":
        filters.append(DocumentRow.path.like(f"{scope.folder_prefix}%"))
    return filters


class PostgresVectorIndex:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_passages(
        self,
        *,
        engagement_id: EngagementId,
        document_id: DocumentId,
        document_path: DocumentPath,
        document_version: int,
        passages: Sequence[Passage],
        embeddings: Sequence[Sequence[float]],
        embedding_model: str,
    ) -> None:
        if len(passages) != len(embeddings):
            msg = "passages and embeddings must have the same length"
            raise ValueError(msg)

        doc_stmt = select(DocumentRow.id).where(
            DocumentRow.id == document_id,
            DocumentRow.engagement_id == engagement_id,
            DocumentRow.path == document_path,
        )
        found = (await self._session.execute(doc_stmt)).scalar_one_or_none()
        if found is None:
            msg = (
                f"document {document_id} not found in engagement {engagement_id} "
                f"at path {document_path}"
            )
            raise ValueError(msg)

        await self._session.execute(
            delete(PassageRow).where(PassageRow.document_id == document_id)
        )

        for passage, embedding in zip(passages, embeddings, strict=True):
            if passage.document_id != document_id:
                msg = "passage.document_id must match document_id"
                raise ValueError(msg)
            if passage.document_version != document_version:
                msg = "passage.document_version must match document_version"
                raise ValueError(msg)
            self._session.add(
                PassageRow(
                    id=passage.id,
                    document_id=passage.document_id,
                    document_version=passage.document_version,
                    ordinal=passage.ordinal,
                    page=passage.page,
                    heading_path=list(passage.heading_path),
                    text=passage.text,
                    token_count=passage.token_count,
                    embedding=list(embedding),
                    embedding_model=embedding_model,
                    created_at=passage.created_at,
                )
            )
        await self._session.flush()

    async def search(
        self,
        query: str,
        query_embedding: Sequence[float],
        scope: RetrievalScope,
        *,
        embedding_model: str,
        min_score: float,
    ) -> list[ScoredPassage]:
        filters = _scoped_passage_filters(scope, embedding_model=embedding_model)
        embedding_list = list(query_embedding)
        distance = PassageRow.embedding.cosine_distance(embedding_list)
        similarity = (1.0 - distance).label("similarity")

        vector_stmt: Select[tuple[PassageRow, str, float]] = (
            select(PassageRow, DocumentRow.path, similarity)
            .join(DocumentRow, DocumentRow.id == PassageRow.document_id)
            .where(*filters)
            .order_by(distance.asc())
            .limit(max(scope.top_k * 4, scope.top_k))
        )
        vector_rows = (await self._session.execute(vector_stmt)).all()

        vector_survivors: list[tuple[PassageRow, str, float]] = []
        for row, path, score in vector_rows:
            if float(score) >= min_score:
                vector_survivors.append((row, path, float(score)))

        if not vector_survivors:
            return []

        survivor_ids = {row.id for row, _, _ in vector_survivors}
        vector_ranked_ids = [row.id for row, _, _ in vector_survivors]
        score_by_id = {row.id: score for row, _, score in vector_survivors}
        path_by_id = {row.id: path for row, path, _ in vector_survivors}
        row_by_id = {row.id: row for row, _, _ in vector_survivors}

        fts_ranked_ids = await self._fts_ranked_ids(
            query=query,
            scope=scope,
            embedding_model=embedding_model,
            allowed_ids=survivor_ids,
            limit=max(scope.top_k * 4, scope.top_k),
        )

        fused_ids = _rrf_merge(vector_ranked_ids, fts_ranked_ids)[: scope.top_k]
        results: list[ScoredPassage] = []
        for passage_id in fused_ids:
            row = row_by_id[passage_id]
            results.append(
                ScoredPassage(
                    passage=_passage_from_row(row),
                    document_path=path_by_id[passage_id],
                    score=score_by_id[passage_id],
                )
            )
        return results

    async def _fts_ranked_ids(
        self,
        *,
        query: str,
        scope: RetrievalScope,
        embedding_model: str,
        allowed_ids: set[UUID],
        limit: int,
    ) -> list[UUID]:
        if not query.strip() or not allowed_ids:
            return []

        filters = _scoped_passage_filters(scope, embedding_model=embedding_model)
        ts_query = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(PassageRow.search_vector, ts_query)

        stmt = (
            select(PassageRow.id)
            .join(DocumentRow, DocumentRow.id == PassageRow.document_id)
            .where(
                *filters,
                PassageRow.id.in_(allowed_ids),
                PassageRow.search_vector.op("@@")(ts_query),
            )
            .order_by(rank.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows)
