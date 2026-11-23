"""Typed HTTP client for the AIditor API."""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import TypeVar, cast
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import TypeAdapter, ValidationError

from backend.application.api.contracts.v1.page import Page
from backend.application.api.contracts.v1.requests import (
    AskRequest,
    CreateEngagementRequest,
    UpdateEngagementRequest,
)
from backend.application.api.contracts.v1.responses import (
    AnsweredResponse,
    AskResponse,
    AskResponseRoot,
    DocumentListingResponse,
    EngagementResponse,
    InsufficientEvidenceResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    UploadAcceptedResponse,
    UploadResponse,
    UploadSummaryResponse,
)
from backend.domain.common import RequestId
from backend.domain.engagement import EngagementId
from backend.domain.errors import ErrorCode
from backend.domain.problem import ProblemDetails
from backend.domain.upload import UploadStatus

T = TypeVar("T")

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 120.0
UPLOAD_POLL_INTERVAL_SECONDS = 2.0


class CliApiError(Exception):
    """API failure mapped from RFC 9457 Problem Details."""

    def __init__(
        self,
        *,
        code: ErrorCode,
        detail: str,
        status: int,
        request_id: RequestId | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status
        self.request_id = request_id


def _parse_json_object_dict(text: str) -> dict[str, object] | None:
    try:
        loaded = cast(object, json.loads(text))
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    as_dict = cast(dict[object, object], loaded)
    return {str(key): value for key, value in as_dict.items()}


def _problem_to_cli_error(response: httpx.Response) -> CliApiError:
    if response.content:
        try:
            problem = ProblemDetails.model_validate_json(response.content)
            return CliApiError(
                code=problem.code,
                detail=problem.detail,
                status=problem.status,
                request_id=problem.request_id,
            )
        except ValidationError:
            pass
    return CliApiError(
        code=ErrorCode.INTERNAL_ERROR,
        detail=response.text or f"HTTP {response.status_code}",
        status=response.status_code,
        request_id=None,
    )


def _zip_directory(directory: Path) -> tuple[str, bytes]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file():
                arcname = file_path.relative_to(directory).as_posix()
                archive.write(file_path, arcname)
    name = f"{directory.name}.zip" if directory.name else "upload.zip"
    return name, buffer.getvalue()


def prepare_upload_payload(path: Path) -> list[tuple[str, bytes]]:
    """Return (filename, bytes) tuples for multipart upload."""
    if not path.exists():
        msg = f"path not found: {path}"
        raise FileNotFoundError(msg)
    if path.is_file():
        return [(path.name, path.read_bytes())]
    if path.is_dir():
        filename, data = _zip_directory(path)
        return [(filename, data)]
    msg = f"not a file or directory: {path}"
    raise ValueError(msg)


class AuditApiClient:
    """Synchronous httpx client using v1 contract models."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = (
            http_client
            if http_client is not None
            else httpx.Client(base_url=self._base_url, timeout=timeout)
        )

    @classmethod
    def from_env(cls) -> AuditApiClient:
        base = os.environ.get("AUDIT_API_BASE_URL", DEFAULT_BASE_URL)
        raw_timeout = os.environ.get("AUDIT_API_TIMEOUT_SECONDS", str(int(DEFAULT_TIMEOUT_SECONDS)))
        timeout = float(raw_timeout)
        return cls(base_url=base, timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> AuditApiClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _transport_error(self, exc: httpx.RequestError) -> CliApiError:
        return CliApiError(
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            detail=f"cannot reach API at {self._base_url}: {exc}",
            status=0,
        )

    def _raise_for_response(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        raise _problem_to_cli_error(response)

    def check_live(self) -> None:
        """Probe `/health/live`; raise CliApiError if the API is unreachable."""
        try:
            response = self._client.get("/health/live")
        except httpx.RequestError as exc:
            raise self._transport_error(exc) from exc
        self._raise_for_response(response)

    def _get_json(self, response: httpx.Response, adapter: TypeAdapter[T]) -> T:
        self._raise_for_response(response)
        return adapter.validate_json(response.content)

    def list_engagements(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[EngagementResponse]:
        response = self._client.get(
            "/api/v1/engagements",
            params={"limit": limit, "offset": offset},
        )
        adapter: TypeAdapter[Page[EngagementResponse]] = TypeAdapter(Page[EngagementResponse])
        return self._get_json(response, adapter)

    def get_engagement(self, engagement_id: EngagementId) -> EngagementResponse:
        response = self._client.get(f"/api/v1/engagements/{engagement_id}")
        adapter: TypeAdapter[EngagementResponse] = TypeAdapter(EngagementResponse)
        return self._get_json(response, adapter)

    def create_engagement(self, *, engagement_id: EngagementId, name: str) -> EngagementResponse:
        body = CreateEngagementRequest(id=engagement_id, name=name)
        response = self._client.post(
            "/api/v1/engagements",
            json=body.model_dump(mode="json"),
        )
        adapter: TypeAdapter[EngagementResponse] = TypeAdapter(EngagementResponse)
        return self._get_json(response, adapter)

    def update_engagement(
        self,
        engagement_id: EngagementId,
        *,
        name: str,
    ) -> EngagementResponse:
        body = UpdateEngagementRequest(name=name)
        response = self._client.patch(
            f"/api/v1/engagements/{engagement_id}",
            json=body.model_dump(mode="json"),
        )
        adapter: TypeAdapter[EngagementResponse] = TypeAdapter(EngagementResponse)
        return self._get_json(response, adapter)

    def delete_engagement(self, engagement_id: EngagementId) -> None:
        response = self._client.delete(f"/api/v1/engagements/{engagement_id}")
        self._raise_for_response(response)

    def ask(
        self,
        engagement_id: EngagementId,
        *,
        question: str,
        session_id: UUID | None = None,
        folder_prefix: str | None = None,
        auditor_role: str | None = None,
        topic: str | None = None,
    ) -> AskResponse:
        body = AskRequest(
            question=question,
            session_id=session_id,
            folder_prefix=folder_prefix,
            auditor_role=auditor_role,
            topic=topic,
        )
        response = self._client.post(
            f"/api/v1/engagements/{engagement_id}/ask",
            json=body.model_dump(mode="json"),
        )
        self._raise_for_response(response)
        root = AskResponseRoot.model_validate_json(response.content)
        return root.root

    def ask_stream(
        self,
        engagement_id: EngagementId,
        *,
        question: str,
        session_id: UUID | None = None,
        folder_prefix: str | None = None,
        auditor_role: str | None = None,
        topic: str | None = None,
    ) -> Iterator[dict[str, object]]:
        """Yield SSE progress events; final event is type=final with AskResponse."""
        body = AskRequest(
            question=question,
            session_id=session_id,
            folder_prefix=folder_prefix,
            auditor_role=auditor_role,
            topic=topic,
        )
        with self._client.stream(
            "POST",
            f"/api/v1/engagements/{engagement_id}/ask/stream",
            json=body.model_dump(mode="json"),
        ) as response:
            if not response.is_success:
                # Read body for problem details
                content = response.read()
                fake = httpx.Response(
                    status_code=response.status_code,
                    content=content,
                    headers=response.headers,
                    request=response.request,
                )
                raise _problem_to_cli_error(fake)
            event_lines: list[str] = []
            for line in response.iter_lines():
                if line == "":
                    if not event_lines:
                        continue
                    data_lines = [
                        item.removeprefix("data:").strip()
                        for item in event_lines
                        if item.startswith("data:")
                    ]
                    event_lines = []
                    if not data_lines:
                        continue
                    payload = _parse_json_object_dict("\n".join(data_lines))
                    if payload is None:
                        continue
                    event_type = payload.get("type")
                    if event_type == "error":
                        code_value = payload.get("code", "internal_error")
                        detail_value = payload.get("detail", "stream error")
                        status_value = payload.get("status", 500)
                        raise CliApiError(
                            code=ErrorCode(str(code_value)),
                            detail=str(detail_value),
                            status=(
                                status_value
                                if isinstance(status_value, int)
                                else int(str(status_value))
                            ),
                            request_id=None,
                        )
                    if event_type == "final":
                        raw_final = payload.get("response")
                        root = AskResponseRoot.model_validate_json(json.dumps(raw_final))
                        yield {"type": "final", "response": root.root}
                    else:
                        yield payload
                else:
                    event_lines.append(line)

    def upload_documents(
        self,
        engagement_id: EngagementId,
        *,
        folder: str,
        files: list[tuple[str, bytes]],
    ) -> UploadAcceptedResponse:
        multipart: list[tuple[str, tuple[str, bytes, str]]] = [
            ("files", (name, data, "application/octet-stream")) for name, data in files
        ]
        response = self._client.post(
            f"/api/v1/engagements/{engagement_id}/documents",
            data={"folder": folder},
            files=multipart,
        )
        adapter: TypeAdapter[UploadAcceptedResponse] = TypeAdapter(UploadAcceptedResponse)
        return self._get_json(response, adapter)

    def upload_path(
        self,
        engagement_id: EngagementId,
        path: Path,
        *,
        folder: str,
    ) -> UploadAcceptedResponse:
        payload = prepare_upload_payload(path)
        return self.upload_documents(engagement_id, folder=folder, files=payload)

    def list_uploads(
        self,
        engagement_id: EngagementId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[UploadSummaryResponse]:
        response = self._client.get(
            f"/api/v1/engagements/{engagement_id}/uploads",
            params={"limit": limit, "offset": offset},
        )
        adapter: TypeAdapter[Page[UploadSummaryResponse]] = TypeAdapter(Page[UploadSummaryResponse])
        return self._get_json(response, adapter)

    def get_upload_status(
        self,
        engagement_id: EngagementId,
        upload_id: UUID,
    ) -> UploadResponse:
        response = self._client.get(
            f"/api/v1/engagements/{engagement_id}/uploads/{upload_id}",
        )
        adapter: TypeAdapter[UploadResponse] = TypeAdapter(UploadResponse)
        return self._get_json(response, adapter)

    def wait_upload(
        self,
        engagement_id: EngagementId,
        upload_id: UUID,
        *,
        poll_interval: float = UPLOAD_POLL_INTERVAL_SECONDS,
    ) -> UploadResponse:
        while True:
            status = self.get_upload_status(engagement_id, upload_id)
            if status.status in (UploadStatus.COMPLETED, UploadStatus.FAILED):
                return status
            time.sleep(poll_interval)

    def list_sessions(
        self,
        engagement_id: EngagementId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[SessionSummaryResponse]:
        response = self._client.get(
            f"/api/v1/engagements/{engagement_id}/sessions",
            params={"limit": limit, "offset": offset},
        )
        adapter: TypeAdapter[Page[SessionSummaryResponse]] = TypeAdapter(
            Page[SessionSummaryResponse]
        )
        return self._get_json(response, adapter)

    def get_session(
        self,
        engagement_id: EngagementId,
        session_id: UUID,
    ) -> SessionDetailResponse:
        response = self._client.get(
            f"/api/v1/engagements/{engagement_id}/sessions/{session_id}",
        )
        adapter: TypeAdapter[SessionDetailResponse] = TypeAdapter(SessionDetailResponse)
        return self._get_json(response, adapter)

    def list_documents(
        self,
        engagement_id: EngagementId,
        *,
        prefix: str | None = None,
        depth: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DocumentListingResponse:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if prefix is not None:
            params["prefix"] = prefix
        if depth is not None:
            params["depth"] = depth
        response = self._client.get(
            f"/api/v1/engagements/{engagement_id}/documents",
            params=params,
        )
        adapter: TypeAdapter[DocumentListingResponse] = TypeAdapter(DocumentListingResponse)
        return self._get_json(response, adapter)

    def get_document_content(self, engagement_id: EngagementId, document_path: str) -> bytes:
        encoded = quote(document_path, safe="")
        response = self._client.get(
            f"/api/v1/engagements/{engagement_id}/documents/{encoded}",
        )
        self._raise_for_response(response)
        return response.content

    def delete_document(self, engagement_id: EngagementId, document_path: str) -> None:
        encoded = quote(document_path, safe="")
        response = self._client.delete(
            f"/api/v1/engagements/{engagement_id}/documents/{encoded}",
        )
        self._raise_for_response(response)


def unwrap_answer(response: AskResponse) -> AnsweredResponse | None:
    if isinstance(response, AnsweredResponse):
        return response
    return None


def unwrap_insufficient(response: AskResponse) -> InsufficientEvidenceResponse | None:
    if isinstance(response, InsufficientEvidenceResponse):
        return response
    return None
