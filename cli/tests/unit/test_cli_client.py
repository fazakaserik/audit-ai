"""Unit tests for the audit-ai HTTP client."""

from __future__ import annotations

import uuid

import httpx
import pytest

from cli.client import AuditApiClient, CliApiError, _problem_to_cli_error
from domain.common import RequestId
from domain.errors import ErrorCode


def test_problem_details_mapping_from_response() -> None:
    request_id = RequestId(uuid.uuid4())
    problem = {
        "type": "https://audit-ai.local/problems/not_found",
        "title": "Not Found",
        "status": 404,
        "detail": "engagement not found: missing",
        "code": "not_found",
        "request_id": str(request_id),
        "errors": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/engagements"
        return httpx.Response(
            404,
            json=problem,
            headers={"content-type": "application/problem+json"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    client = AuditApiClient(http_client=http_client)

    with pytest.raises(CliApiError) as exc_info:
        client.list_engagements()

    err = exc_info.value
    assert err.code == ErrorCode.NOT_FOUND
    assert err.detail == "engagement not found: missing"
    assert err.status == 404
    assert err.request_id == request_id


def test_problem_to_cli_error_helper_non_json() -> None:
    response = httpx.Response(503, text="service unavailable")
    error = _problem_to_cli_error(response)
    assert error.code == ErrorCode.INTERNAL_ERROR
    assert error.status == 503
    assert error.request_id is None


def test_list_engagements_success() -> None:
    payload = {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    client = AuditApiClient(http_client=http_client)

    page = client.list_engagements()
    assert page.total == 0
    assert page.items == ()