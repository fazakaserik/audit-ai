# CLI Contract: `aiditor`

Package: `cli/` (import name `cli`). Speaks only HTTP using `backend.application.api.contracts.v1` models. Base URL from `AUDIT_API_BASE_URL` (default `http://localhost:8000`).

Shared HTTP access for other workspace clients (including `tui`) is `cli.client.AuditApiClient`.

## Entry points

| Invocation                 | Behaviour                                                                           |
| -------------------------- | ----------------------------------------------------------------------------------- |
| `aiditor` (no args)        | Print help (non-interactive). For the fullscreen UI, run `aiditor-tui`.             |
| `aiditor <subcommand> ...` | Non-interactive command; exit `0` on success, non-zero on API/Problem Details error |

## Non-interactive commands

```text
aiditor engagements list [--limit N] [--offset N]
aiditor engagements create --id <slug> --name <name>
aiditor engagements show --id <slug>

aiditor upload <path> --engagement <id> --folder <folder> [--wait]
  # <path> is a file, directory (zipped client-side), or .zip
  # --wait polls GET .../uploads/{id} until completed|failed

aiditor uploads list --engagement <id> [--limit N] [--offset N]
aiditor uploads status --engagement <id> --upload <uuid>

aiditor sessions list --engagement <id> [--limit N] [--offset N]
aiditor sessions show --engagement <id> --session <uuid>

aiditor documents list --engagement <id> [--prefix P] [--depth N] [--limit N] [--offset N]
aiditor documents get --engagement <id> --path <path>

aiditor version
```

No sample-specific or test-only commands. Seeding is `scripts/seed_samples.py` (calls these commands).

Interactive fullscreen chat lives in package `tui` (`aiditor-tui`); see [tui.md](./tui.md).

## Configuration

| Variable                    | Default                 | Purpose               |
| --------------------------- | ----------------------- | --------------------- |
| `AUDIT_API_BASE_URL`        | `http://localhost:8000` | API root              |
| `AUDIT_API_TIMEOUT_SECONDS` | `120`                   | httpx timeout for ask |
