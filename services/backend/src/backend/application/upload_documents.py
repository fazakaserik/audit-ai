"""Accept multipart uploads, store bytes, queue per-file jobs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.application.ports import (
    DocumentStorage,
    EngagementRepository,
    JobQueue,
    UploadRepository,
)
from backend.config import Settings
from backend.ingestion.archive import extract_zip_files, is_zip_upload, list_zip_member_paths
from domain.common import new_uuid, utc_now
from domain.document import DocumentPath, FolderPath
from domain.document.validators import validate_document_path, validate_folder_path
from domain.engagement import EngagementId
from domain.errors import NotFoundError, PayloadTooLargeError, UnsafeUploadError, ValidationError
from domain.upload import Upload, UploadId, UploadItem, UploadItemId, UploadItemStatus, UploadStatus


@dataclass(frozen=True, slots=True)
class IncomingUploadFile:
    filename: str
    data: bytes


@dataclass(frozen=True, slots=True)
class UploadDocumentsResult:
    upload: Upload
    item_count: int


def _basename(filename: str) -> str:
    cleaned = filename.replace("\\", "/")
    name = cleaned.rsplit("/", 1)[-1]
    if not name or name in (".", ".."):
        raise UnsafeUploadError(f"invalid upload filename: {filename!r}")
    return name


def _join_folder(target_folder: FolderPath, relative: str) -> DocumentPath:
    if target_folder:
        combined = f"{target_folder.rstrip('/')}/{relative}"
    else:
        combined = relative
    try:
        return validate_document_path(combined)
    except ValueError as exc:
        raise UnsafeUploadError(f"invalid document path: {combined}") from exc


def _expand_incoming(
    files: Sequence[IncomingUploadFile],
    target_folder: FolderPath,
) -> list[tuple[DocumentPath, bytes]]:
    planned: list[tuple[DocumentPath, bytes]] = []
    for incoming in files:
        if is_zip_upload(filename=incoming.filename, data=incoming.data):
            # Validate listing before extract (traversal / symlink checks).
            list_zip_member_paths(incoming.data)
            for rel, payload in extract_zip_files(incoming.data):
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
        raise PayloadTooLargeError(
            f"upload exceeds max file count ({settings.upload_max_files})"
        )
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


async def upload_documents(
    *,
    engagements: EngagementRepository,
    uploads: UploadRepository,
    storage: DocumentStorage,
    jobs: JobQueue,
    settings: Settings,
    engagement_id: EngagementId,
    target_folder: str,
    files: Sequence[IncomingUploadFile],
) -> UploadDocumentsResult:
    engagement = await engagements.get(engagement_id)
    if engagement is None:
        raise NotFoundError(f"engagement not found: {engagement_id}")

    folder: FolderPath = validate_folder_path(target_folder)
    if not files:
        raise ValidationError("upload must include at least one file")

    planned = _expand_incoming(files, folder)
    _enforce_limits(planned, settings=settings)

    now = utc_now()
    upload_id = UploadId(new_uuid())
    items: list[UploadItem] = []

    for document_path, data in planned:
        await storage.put(engagement_id, document_path, data)
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
    await uploads.create(upload, items)
    await jobs.enqueue_items(items)

    return UploadDocumentsResult(upload=upload, item_count=len(items))