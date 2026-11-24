"""Typed domain errors mapped 1:1 to ErrorCode."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSAFE_UPLOAD = "unsafe_upload"
    REPRESENTATION_LIMIT_EXCEEDED = "representation_limit_exceeded"
    MODEL_TIMEOUT = "model_timeout"
    MODEL_UNAVAILABLE = "model_unavailable"
    CONTEXT_TOO_LARGE = "context_too_large"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    INTERNAL_ERROR = "internal_error"


class DomainError(Exception):
    """Base error for application and domain failures."""

    code: ErrorCode

    def __init__(self, message: str, *, code: ErrorCode | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message


class ValidationError(DomainError):
    code = ErrorCode.VALIDATION_ERROR

    def __init__(self, message: str, *, field_errors: list[tuple[str, str]] | None = None) -> None:
        super().__init__(message)
        self.field_errors = field_errors or []


class NotFoundError(DomainError):
    code = ErrorCode.NOT_FOUND


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT


class PayloadTooLargeError(DomainError):
    code = ErrorCode.PAYLOAD_TOO_LARGE


class UnsafeUploadError(DomainError):
    code = ErrorCode.UNSAFE_UPLOAD


class RepresentationLimitExceededError(DomainError):
    """Parsed or chunked document exceeds configured representation ceilings."""

    code = ErrorCode.REPRESENTATION_LIMIT_EXCEEDED


class ModelTimeoutError(DomainError):
    code = ErrorCode.MODEL_TIMEOUT


class ModelUnavailableError(DomainError):
    code = ErrorCode.MODEL_UNAVAILABLE


class ContextTooLargeError(DomainError):
    """Assembled prompt exceeds the model's context window."""

    code = ErrorCode.CONTEXT_TOO_LARGE


class DependencyUnavailableError(DomainError):
    code = ErrorCode.DEPENDENCY_UNAVAILABLE


class InternalError(DomainError):
    code = ErrorCode.INTERNAL_ERROR
