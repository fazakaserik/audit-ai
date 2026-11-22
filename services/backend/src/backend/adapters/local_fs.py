"""Local filesystem document storage adapter."""

from __future__ import annotations

import asyncio
from pathlib import Path

from domain.document import DocumentPath
from domain.engagement import EngagementId
from domain.errors import NotFoundError, UnsafeUploadError


class LocalDocumentStorage:
    """Store document bytes under ``root / engagement_id / path``."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _resolve(self, engagement_id: EngagementId, path: DocumentPath) -> Path:
        base = (self._root / engagement_id).resolve()
        target = (base / path).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise UnsafeUploadError(
                f"path escapes engagement storage: {path}"
            ) from exc
        return target

    async def put(
        self,
        engagement_id: EngagementId,
        path: DocumentPath,
        data: bytes,
    ) -> Path:
        target = self._resolve(engagement_id, path)

        def _write() -> Path:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return target

        return await asyncio.to_thread(_write)

    async def get(self, engagement_id: EngagementId, path: DocumentPath) -> bytes:
        target = self._resolve(engagement_id, path)

        def _read() -> bytes:
            if not target.is_file():
                raise NotFoundError(f"document not found: {engagement_id}/{path}")
            return target.read_bytes()

        return await asyncio.to_thread(_read)

    async def delete(self, engagement_id: EngagementId, path: DocumentPath) -> None:
        target = self._resolve(engagement_id, path)

        def _delete() -> None:
            if target.is_file():
                target.unlink()

        await asyncio.to_thread(_delete)
