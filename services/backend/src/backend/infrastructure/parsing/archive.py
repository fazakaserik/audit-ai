"""Safe zip archive listing and extraction (no path escape, no symlinks)."""

from __future__ import annotations

import io
import re
import stat
import zipfile

from backend.application.parsing.archive_extractor import ArchiveExtractor
from backend.domain.document import normalize_posix_path
from backend.domain.errors import UnsafeUploadError, ValidationError


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


def list_zip_member_paths(data: bytes) -> tuple[str, ...]:
    """List safe member paths without extracting file bytes."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationError("archive is corrupted or not a zip file") from exc
    paths: list[str] = []
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            _reject_symlink(info)
            paths.append(_safe_member_path(info.filename))
    return tuple(paths)


def extract_zip_files(data: bytes) -> list[tuple[str, bytes]]:
    """Extract file members as ``(relative_path, bytes)`` pairs."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationError("archive is corrupted or not a zip file") from exc
    extracted: list[tuple[str, bytes]] = []
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            _reject_symlink(info)
            relative = _safe_member_path(info.filename)
            try:
                payload = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise ValidationError(f"failed to read archive entry: {info.filename}") from exc
            extracted.append((relative, payload))
    return extracted


class DefaultArchiveExtractor:
    """Infrastructure adapter for ArchiveExtractor."""

    def is_zip_upload(self, *, filename: str, data: bytes) -> bool:
        return is_zip_upload(filename=filename, data=data)

    def list_zip_member_paths(self, data: bytes) -> tuple[str, ...]:
        return list_zip_member_paths(data)

    def extract_zip_files(self, data: bytes) -> list[tuple[str, bytes]]:
        return extract_zip_files(data)


def build_archive_extractor() -> ArchiveExtractor:
    return DefaultArchiveExtractor()
