"""Unit tests for safe zip handling."""

from __future__ import annotations

import io
import zipfile

import pytest

from backend.ingestion.archive import extract_zip_files, list_zip_member_paths
from domain.errors import UnsafeUploadError


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_list_zip_rejects_parent_traversal() -> None:
    payload = _zip_bytes({"../../outside.txt": b"evil"})
    with pytest.raises(UnsafeUploadError):
        list_zip_member_paths(payload)


def test_extract_zip_rejects_absolute_paths() -> None:
    payload = _zip_bytes({"/etc/passwd": b"evil"})
    with pytest.raises(UnsafeUploadError):
        extract_zip_files(payload)


def test_safe_zip_lists_and_extracts() -> None:
    payload = _zip_bytes({"notes/readme.md": b"# Hello"})
    paths = list_zip_member_paths(payload)
    assert paths == ("notes/readme.md",)
    extracted = extract_zip_files(payload)
    assert extracted == [("notes/readme.md", b"# Hello")]
