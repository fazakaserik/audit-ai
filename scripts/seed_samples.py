"""Seed northwind sample via HTTP upload (same path as the CLI client)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import UUID

from backend.application.api.contracts.v1.responses import UploadResponse
from backend.domain.engagement import EngagementId
from backend.domain.errors import ErrorCode
from backend.domain.upload import UploadItemStatus, UploadStatus
from cli.client import UPLOAD_POLL_INTERVAL_SECONDS, AuditApiClient, CliApiError

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "docs" / "samples" / "ai-generated" / "northwind-fy2025"
ENGAGEMENT_ID = "northwind-fy2025"
ENGAGEMENT_NAME = "Northwind FY2025"

_TERMINAL_ITEM = frozenset(
    {
        UploadItemStatus.INDEXED,
        UploadItemStatus.SKIPPED,
        UploadItemStatus.NOT_SEARCHABLE,
        UploadItemStatus.FAILED,
    }
)


def _wait_with_progress(
    client: AuditApiClient,
    engagement_id: EngagementId,
    upload_id: UUID,
) -> UploadResponse:
    last_summary = ""
    while True:
        status = client.get_upload_status(engagement_id, upload_id)
        done = sum(1 for item in status.items if item.status in _TERMINAL_ITEM)
        active = next(
            (item for item in status.items if item.status not in _TERMINAL_ITEM),
            None,
        )
        active_bit = f", working on {active.document_path}" if active is not None else ""
        summary = f"{status.status.value}: {done}/{len(status.items)} items done{active_bit}"
        if summary != last_summary:
            print(f"  … {summary}")
            last_summary = summary
        if status.status in (UploadStatus.COMPLETED, UploadStatus.FAILED):
            return status
        time.sleep(UPLOAD_POLL_INTERVAL_SECONDS)


def main() -> None:
    if not SAMPLE_DIR.is_dir():
        raise SystemExit(f"sample directory missing: {SAMPLE_DIR}")

    client = AuditApiClient.from_env()
    try:
        try:
            client.create_engagement(engagement_id=ENGAGEMENT_ID, name=ENGAGEMENT_NAME)
            print(f"created engagement {ENGAGEMENT_ID}")
        except CliApiError as exc:
            if exc.code == ErrorCode.CONFLICT or exc.status == 409:
                print(f"engagement {ENGAGEMENT_ID} already present")
            else:
                existing = {item.id for item in client.list_engagements().items}
                if ENGAGEMENT_ID not in existing:
                    raise
                print(f"engagement {ENGAGEMENT_ID} already present")

        for folder in sorted(path for path in SAMPLE_DIR.iterdir() if path.is_dir()):
            accepted = client.upload_path(
                ENGAGEMENT_ID,
                folder,
                folder=folder.name,
            )
            print(f"queued {folder.name} → {accepted.upload_id}")
            final = _wait_with_progress(client, ENGAGEMENT_ID, accepted.upload_id)
            print(f"upload {accepted.upload_id} → {final.status}")
            if final.status.value == "failed":
                raise SystemExit(f"upload failed: {accepted.upload_id}")
        print("seed complete")
    except CliApiError as exc:
        print(f"API error {exc.status} {exc.code}: {exc.detail}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        client.close()


if __name__ == "__main__":
    main()
