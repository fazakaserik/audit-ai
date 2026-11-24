"""Safe zip archive listing and extraction (no path escape, no symlinks)."""

from __future__ import annotations

import io
import re
import stat
import zipfile

from backend.application.parsing.archive_extractor import ArchiveExtractor
from backend.domain.document import normalize_posix_path
from backend.domain.errors import PayloadTooLargeError, UnsafeUploadError, ValidationError


def is_zip_upload(*, filename: str, data: bytes) -> bool:
    if filename.lower().endswith(".zip"):
        return True
    return len(data) >= 4 and data[:2] == b"PK"


def _safe_member_path(name: str) -> str:
    if name.startswith("/") or re.match(r"^[a-zA-Z]:", name.replace("\\", "/")):
        raise UnsafeUploadError(f"unsafe archive entry: {name}")
    cleaned = name.replace("\\", "/").lstrip("/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if not cleaned or cleaned.endswith("/"):
        msg = f"archive entry is not a file: {name!r}"
        raise ValidationError(msg)
    try:
        return normalize_posix_path(cleaned, allow_empty=False)
    except ValueError as exc:
        raise UnsafeUploadError(f"unsafe archive entry: {name}") from exc


def _reject_symlink(info: zipfile.ZipInfo) -> None:
    mode = (info.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK:
        raise UnsafeUploadError(f"archive entry is a symlink: {info.filename}")
    # Unix symlinks sometimes set the top bits in external_attr without full mode.
    if (info.external_attr >> 28) & 0xF == 0xA:
        raise UnsafeUploadError(f"archive entry is a symlink: {info.filename}")


def _file_infos(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    return [info for info in archive.infolist() if not info.is_dir()]


def _enforce_max_files(infos: list[zipfile.ZipInfo], max_files: int | None) -> None:
    if max_files is not None and len(infos) > max_files:
        raise PayloadTooLargeError(f"upload exceeds max file count ({max_files})")


def list_zip_member_paths(
    data: bytes,
    *,
    max_files: int | None = None,
) -> tuple[str, ...]:
    """List safe member paths without extracting file bytes."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationError("archive is corrupted or not a zip file") from exc
    paths: list[str] = []
    with archive:
        infos = _file_infos(archive)
        _enforce_max_files(infos, max_files)
        for info in infos:
            _reject_symlink(info)
            paths.append(_safe_member_path(info.filename))
    return tuple(paths)


def extract_zip_files(
    data: bytes,
    *,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
    max_files: int | None = None,
) -> list[tuple[str, bytes]]:
    """Extract file members as ``(relative_path, bytes)`` pairs."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationError("archive is corrupted or not a zip file") from exc
    extracted: list[tuple[str, bytes]] = []
    total = 0
    with archive:
        infos = _file_infos(archive)
        _enforce_max_files(infos, max_files)
        for info in infos:
            _reject_symlink(info)
            relative = _safe_member_path(info.filename)
            declared = int(info.file_size)
            if max_file_bytes is not None and declared > max_file_bytes:
                raise PayloadTooLargeError(
                    f"archive entry {info.filename} exceeds max size ({max_file_bytes} bytes)"
                )
            if max_total_bytes is not None and total + declared > max_total_bytes:
                raise PayloadTooLargeError(
                    f"upload exceeds max total size ({max_total_bytes} bytes)"
                )
            try:
                payload = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise ValidationError(f"failed to read archive entry: {info.filename}") from exc
            if max_file_bytes is not None and len(payload) > max_file_bytes:
                raise PayloadTooLargeError(
                    f"archive entry {info.filename} exceeds max size ({max_file_bytes} bytes)"
                )
            total += len(payload)
            if max_total_bytes is not None and total > max_total_bytes:
                raise PayloadTooLargeError(
                    f"upload exceeds max total size ({max_total_bytes} bytes)"
                )
            extracted.append((relative, payload))
    return extracted


class DefaultArchiveExtractor:
    """Infrastructure adapter for ArchiveExtractor."""

    def is_zip_upload(self, *, filename: str, data: bytes) -> bool:
        return is_zip_upload(filename=filename, data=data)

    def list_zip_member_paths(
        self,
        data: bytes,
        *,
        max_files: int | None = None,
    ) -> tuple[str, ...]:
        return list_zip_member_paths(data, max_files=max_files)

    def extract_zip_files(
        self,
        data: bytes,
        *,
        max_file_bytes: int | None = None,
        max_total_bytes: int | None = None,
        max_files: int | None = None,
    ) -> list[tuple[str, bytes]]:
        return extract_zip_files(
            data,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            max_files=max_files,
        )


def build_archive_extractor() -> ArchiveExtractor:
    return DefaultArchiveExtractor()
