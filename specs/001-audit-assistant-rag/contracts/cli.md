# CLI Contract: `audit-ai`

Package: `cli/` (import name `cli`). Speaks only HTTP using `domain.contracts.v1` models. Base URL from `AUDIT_API_BASE_URL` (default `http://localhost:8000`).

## Entry points

| Invocation                  | Behaviour                                                                           |
| --------------------------- | ----------------------------------------------------------------------------------- |
| `audit-ai` (no args)        | Interactive REPL                                                                    |
| `audit-ai <subcommand> ...` | Non-interactive command; exit `0` on success, non-zero on API/Problem Details error |

## Non-interactive commands

```text
audit-ai engagements list [--limit N] [--offset N]
audit-ai engagements create --id <slug> --name <name>

audit-ai upload <path> --engagement <id> --folder <folder> [--wait]
  # <path> is a file, directory (zipped client-side), or .zip
  # --wait polls GET .../uploads/{id} until completed|failed

audit-ai uploads status --engagement <id> --upload <uuid>

audit-ai sessions list --engagement <id> [--limit N] [--offset N]
audit-ai sessions show --engagement <id> --session <uuid>
```

No sample-specific or test-only commands. Seeding is `scripts/seed_samples.py` (calls these commands).

## Interactive REPL

On start:

1. Fetch engagements; prompt to select one (or create via slash command).
2. Offer: start new session (implicit on first question) or resume from `sessions list`.
3. Prompt `>` for questions; send `POST .../ask` with the current `session_id` once known; keep the returned `session_id`.

### Slash commands

| Command                | Action                                                                      |
| ---------------------- | --------------------------------------------------------------------------- |
| `/engagement`          | Switch engagement (clears current session)                                  |
| `/new`                 | Drop `session_id` so the next question starts a new session                 |
| `/sessions`            | List recent sessions                                                        |
| `/resume <session_id>` | Load session turns and continue                                             |
| `/open <marker>`       | Fetch and display the document for citation marker `[n]` of the last answer |
| `/help`                | List commands                                                               |
| `/quit`                | Exit                                                                        |

### Rendering

- Progress spinner while waiting on ask/upload.
- Answer body as Markdown (Rich).
- Citations as a numbered footnote panel matching `[n]` markers.
- Insufficient evidence: reason + suggested client questions panel.
- Errors: `code`, `detail`, `request_id` from Problem Details; REPL stays open.

## Configuration

| Variable                    | Default                 | Purpose               |
| --------------------------- | ----------------------- | --------------------- |
| `AUDIT_API_BASE_URL`        | `http://localhost:8000` | API root              |
| `AUDIT_API_TIMEOUT_SECONDS` | `120`                   | httpx timeout for ask |
