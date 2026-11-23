"""Seed AI-generated sample engagements via HTTP upload (same path as the CLI client)."""

from __future__ import annotations

import sys
from pathlib import Path

from backend.domain.errors import ErrorCode
from cli.client import AuditApiClient, CliApiError

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = ROOT / "docs" / "samples" / "ai-generated"

# Display names for engagement folders under SAMPLES_ROOT (skip README-only files).
ENGAGEMENTS: tuple[tuple[str, str], ...] = (
    ("northwind-fy2025", "Northwind FY2025"),
    ("fabrikam-sox-fy2025", "Fabrikam SOX FY2025"),
    ("adventureworks-itgc-fy2025", "Adventure Works ITGC FY2025"),
)


def _ensure_engagement(client: AuditApiClient, engagement_id: str, name: str) -> None:
    try:
        client.create_engagement(engagement_id=engagement_id, name=name)
        print(f"created engagement {engagement_id}")
    except CliApiError as exc:
        if exc.code == ErrorCode.CONFLICT or exc.status == 409:
            print(f"engagement {engagement_id} already present")
            return
        existing = {item.id for item in client.list_engagements().items}
        if engagement_id not in existing:
            raise
        print(f"engagement {engagement_id} already present")


def _seed_engagement(client: AuditApiClient, engagement_id: str, name: str) -> None:
    sample_dir = SAMPLES_ROOT / engagement_id
    if not sample_dir.is_dir():
        raise SystemExit(f"sample directory missing: {sample_dir}")

    print(f"\n=== {engagement_id} ({name}) ===")
    _ensure_engagement(client, engagement_id, name)

    folders = sorted(path for path in sample_dir.iterdir() if path.is_dir())
    if not folders:
        raise SystemExit(f"no document folders under {sample_dir}")

    for folder in folders:
        accepted = client.upload_path(
            engagement_id,
            folder,
            folder=folder.name,
        )
        print(f"queued {folder.name} → {accepted.upload_id}")


def main() -> None:
    if not SAMPLES_ROOT.is_dir():
        raise SystemExit(f"samples root missing: {SAMPLES_ROOT}")

    client = AuditApiClient.from_env()
    try:
        for engagement_id, name in ENGAGEMENTS:
            _seed_engagement(client, engagement_id, name)
        print("\nseed queued (processing continues in the background)")
    except CliApiError as exc:
        print(f"API error {exc.status} {exc.code}: {exc.detail}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        client.close()


if __name__ == "__main__":
    main()
