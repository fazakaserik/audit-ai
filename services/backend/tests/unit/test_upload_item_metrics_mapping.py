"""Upload item timing/token fields map into API responses."""

from __future__ import annotations

import uuid
from datetime import timedelta

from backend.application.api.contracts.v1.mapping import upload_item_to_response
from backend.domain.common import utc_now
from backend.domain.upload import UploadId, UploadItem, UploadItemId, UploadItemStatus


def test_upload_item_to_response_includes_metrics() -> None:
    now = utc_now()
    started = now - timedelta(seconds=2.5)
    item = UploadItem(
        id=UploadItemId(uuid.uuid4()),
        upload_id=UploadId(uuid.uuid4()),
        document_path="policies/a.md",
        status=UploadItemStatus.INDEXED,
        reason=None,
        attempts=1,
        processing_started_at=started,
        processing_finished_at=now,
        embedding_prompt_tokens=120,
        embedding_total_tokens=120,
        chunk_count=3,
        chunk_token_sum=450,
        created_at=started,
        updated_at=now,
    )
    response = upload_item_to_response(item)
    assert response.processing_started_at == started
    assert response.processing_finished_at == now
    assert response.processing_duration_ms == 2500
    assert response.embedding_prompt_tokens == 120
    assert response.embedding_total_tokens == 120
    assert response.chunk_count == 3
    assert response.chunk_token_sum == 450
