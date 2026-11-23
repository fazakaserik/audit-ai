"""Document entity, path types, and listing helpers."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, NewType

from pydantic import AfterValidator, BaseModel, Field

from backend.domain.common import MODEL_CONFIG
from backend.domain.engagement import EngagementId

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

DocumentId = NewType("DocumentId", uuid.UUID)


def normalize_posix_path(value: str, *, allow_empty: bool) -> str:
    raw = value.replace("\\", "/")
    if _CONTROL_CHARS_RE.search(raw):
        raise ValueError("path must not contain control characters")
    if raw.startswith("/") or re.match(r"^[a-zA-Z]:", raw):
        raise ValueError("path must be relative")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise ValueError("path must not contain '..'")
    if not parts:
        if allow_empty:
            return ""
        raise ValueError("path must not be empty")
    return "/".join(parts)


def validate_folder_path(value: str) -> str:
    return normalize_posix_path(value, allow_empty=True)


def validate_document_path(value: str) -> str:
    path = normalize_posix_path(value, allow_empty=False)
    name = path.rsplit("/", 1)[-1]
    if "." not in name or name.startswith(".") or name.endswith("."):
        raise ValueError("document path must end with a filename that has an extension")
    return path


FolderPath = Annotated[str, AfterValidator(validate_folder_path)]
DocumentPath = Annotated[str, AfterValidator(validate_document_path)]


class ContentType(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    PDF = "pdf"


class Document(BaseModel):
    model_config = MODEL_CONFIG

    id: DocumentId
    engagement_id: EngagementId
    path: DocumentPath
    content_type: ContentType
    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")]
    version: Annotated[int, Field(ge=1)]
    searchable: bool
    created_at: datetime
    updated_at: datetime


def normalize_list_prefix(prefix: str | None) -> str:
    if prefix is None or prefix == "":
        return ""
    return prefix.rstrip("/")


def relative_segments(path: str, prefix: str) -> list[str] | None:
    """Return path segments under prefix, or None if path is not under prefix."""
    if prefix == "":
        return path.split("/") if path else []
    if not path.startswith(prefix + "/"):
        return None
    relative = path[len(prefix) + 1 :]
    if not relative:
        return []
    return relative.split("/")


def within_depth(segments: list[str], depth: int | None) -> bool:
    if depth is None:
        return True
    return len(segments) <= depth


def child_folder_name(segments: list[str]) -> str | None:
    """Immediate child folder under the listing prefix, if the path is nested."""
    if len(segments) > 1:
        return segments[0]
    return None
