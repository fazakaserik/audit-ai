"""Unit tests for safe zip handling."""

from __future__ import annotations

import io
import stat
import zipfile

import pytest

from backend.domain.errors import PayloadTooLargeError, UnsafeUploadError
from backend.infrastructure.parsing.archive import extract_zip_files, list_zip_member_paths


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


def test_extract_zip_rejects_member_over_max_file_bytes() -> None:
    payload = _zip_bytes({"big.txt": b"x" * 200})
    with pytest.raises(PayloadTooLargeError, match="exceeds max size"):
        extract_zip_files(payload, max_file_bytes=50)


def test_extract_zip_rejects_total_over_max_total_bytes() -> None:
    payload = _zip_bytes({"a.txt": b"x" * 40, "b.txt": b"y" * 40})
    with pytest.raises(PayloadTooLargeError, match="max total size"):
        extract_zip_files(payload, max_file_bytes=100, max_total_bytes=50)


def test_extract_zip_rejects_over_max_files_before_read() -> None:
    payload = _zip_bytes({f"f{i}.txt": b"x" for i in range(5)})
    with pytest.raises(PayloadTooLargeError, match="max file count"):
        extract_zip_files(payload, max_files=3)


def test_list_zip_rejects_over_max_files() -> None:
    payload = _zip_bytes({f"f{i}.txt": b"x" for i in range(4)})
    with pytest.raises(PayloadTooLargeError, match="max file count"):
        list_zip_member_paths(payload, max_files=2)


def test_extract_zip_rejects_symlink_member() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo("link-to-secret")
        info.create_system = 3  # Unix
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, b"/etc/passwd")
    with pytest.raises(UnsafeUploadError, match="symlink"):
        extract_zip_files(buffer.getvalue())
