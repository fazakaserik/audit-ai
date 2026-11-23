"""Archive extractor protocol."""

from __future__ import annotations

from typing import Protocol


class ArchiveExtractor(Protocol):
    def is_zip_upload(self, *, filename: str, data: bytes) -> bool: ...

    def list_zip_member_paths(self, data: bytes) -> tuple[str, ...]: ...

    def extract_zip_files(self, data: bytes) -> list[tuple[str, bytes]]: ...
