"""Document list, download, and upload application service."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.application.api.contracts.v1.mapping import document_to_response
from backend.application.api.contracts.v1.responses import (
    DocumentListingResponse,
    UploadAcceptedResponse,
)
from backend.application.parsing.archive_extractor import ArchiveExtractor
from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.upload import UploadRepository
from backend.application.storage.document_storage import DocumentStorage
from backend.application.storage.job_queue import JobQueue
from backend.config import Settings
from backend.domain.common import RequestId, new_uuid, utc_now
from backend.domain.document import (
    ContentType,
    DocumentPath,
    FolderPath,
    validate_document_path,
    validate_folder_path,
)
from backend.domain.engagement import EngagementId
from backend.domain.errors import (
    NotFoundError,
    PayloadTooLargeError,
    UnsafeUploadError,
    ValidationError,
)
from backend.domain.upload import (
    Upload,
    UploadId,
    UploadItem,
    UploadItemId,
    UploadItemStatus,
    UploadStatus,
)

_CONTENT_TYPE_TO_MEDIA: dict[ContentType, str] = {
    ContentType.MARKDOWN: "text/markdown",
    ContentType.TEXT: "text/plain",
    ContentType.PDF: "application/pdf",
}


@dataclass(frozen=True, slots=True)
class IncomingUploadFile:
    filename: str
    data: bytes


@dataclass(frozen=True, slots=True)
class DocumentContent:
    data: bytes
    media_type: str


def media_type_for_content_type(content_type: ContentType) -> str:
    return _CONTENT_TYPE_TO_MEDIA[content_type]


def _basename(filename: str) -> str:
    cleaned = filename.replace("\\", "/")
    name = cleaned.rsplit("/", 1)[-1]
    if not name or name in (".", ".."):
        raise UnsafeUploadError(f"invalid upload filename: {filename!r}")
    return name


def _join_folder(target_folder: FolderPath, relative: str) -> DocumentPath:
    combined = f"{target_folder.rstrip('/')}/{relative}" if target_folder else relative
    try:
        return validate_document_path(combined)
    except ValueError as exc:
        raise UnsafeUploadError(f"invalid document path: {combined}") from exc


def _expand_incoming(
    files: Sequence[IncomingUploadFile],
    target_folder: FolderPath,
    archives: ArchiveExtractor,
) -> list[tuple[DocumentPath, bytes]]:
    planned: list[tuple[DocumentPath, bytes]] = []
    for incoming in files:
        if archives.is_zip_upload(filename=incoming.filename, data=incoming.data):
            archives.list_zip_member_paths(incoming.data)
            for rel, payload in archives.extract_zip_files(incoming.data):
                planned.append((_join_folder(target_folder, rel), payload))
        else:
            rel = _basename(incoming.filename)
            planned.append((_join_folder(target_folder, rel), incoming.data))
    if not planned:
        raise ValidationError("upload must include at least one file")
    return planned


def _enforce_limits(
    planned: Sequence[tuple[DocumentPath, bytes]],
    *,
    settings: Settings,
) -> None:
    if len(planned) > settings.upload_max_files:
        raise PayloadTooLargeError(f"upload exceeds max file count ({settings.upload_max_files})")
    total = sum(len(data) for _, data in planned)
    if total > settings.upload_max_bytes:
        raise PayloadTooLargeError(
            f"upload exceeds max total size ({settings.upload_max_bytes} bytes)"
        )
    for path, data in planned:
        if len(data) > settings.upload_max_file_bytes:
            raise PayloadTooLargeError(
                f"file {path} exceeds max size ({settings.upload_max_file_bytes} bytes)"
            )


class DocumentService:
    def __init__(
        self,
        engagements: EngagementRepository,
        documents: DocumentRepository,
        uploads: UploadRepository,
        storage: DocumentStorage,
        jobs: JobQueue,
        archives: ArchiveExtractor,
        settings: Settings,
    ) -> None:
        self._engagements = engagements
        self._documents = documents
        self._uploads = uploads
        self._storage = storage
        self._jobs = jobs
        self._archives = archives
        self._settings = settings

    async def list_documents(
        self,
        *,
        engagement_id: EngagementId,
        prefix: FolderPath | None,
        depth: int | None,
        limit: int,
        offset: int,
    ) -> DocumentListingResponse:
        engagement = await self._engagements.get(engagement_id)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")

        items, folders, total = await self._documents.list(
            engagement_id,
            prefix=prefix,
            depth=depth,
            limit=limit,
            offset=offset,
        )
        return DocumentListingResponse(
            items=tuple(document_to_response(doc) for doc in items),
            folders=folders,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_document_content(
        self,
        *,
        engagement_id: EngagementId,
        path: DocumentPath,
    ) -> DocumentContent:
        engagement = await self._engagements.get(engagement_id)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")

        document = await self._documents.get_by_path(engagement_id, path)
        if document is None:
            raise NotFoundError(f"document not found: {path}")

        data = await self._storage.get(engagement_id, path)
        return DocumentContent(
            data=data,
            media_type=media_type_for_content_type(document.content_type),
        )

    async def upload_documents(
        self,
        *,
        engagement_id: EngagementId,
        target_folder: str,
        files: Sequence[IncomingUploadFile],
        request_id: RequestId,
    ) -> UploadAcceptedResponse:
        engagement = await self._engagements.get(engagement_id)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")

        folder: FolderPath = validate_folder_path(target_folder)
        if not files:
            raise ValidationError("upload must include at least one file")

        planned = _expand_incoming(files, folder, self._archives)
        _enforce_limits(planned, settings=self._settings)

        now = utc_now()
        upload_id = UploadId(new_uuid())
        items: list[UploadItem] = []

        for document_path, data in planned:
            await self._storage.put(engagement_id, document_path, data)
            items.append(
                UploadItem(
                    id=UploadItemId(new_uuid()),
                    upload_id=upload_id,
                    document_path=document_path,
                    status=UploadItemStatus.PENDING,
                    reason=None,
                    attempts=0,
                    created_at=now,
                    updated_at=now,
                )
            )

        upload = Upload(
            id=upload_id,
            engagement_id=engagement_id,
            target_folder=folder,
            status=UploadStatus.QUEUED,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._uploads.create(upload, items)
        await self._jobs.enqueue_items(items)

        return UploadAcceptedResponse(upload_id=upload.id, request_id=request_id)
