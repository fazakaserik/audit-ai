# Audit Assistant

Document-grounded Q&A for auditors. Clients upload engagement documents; auditors ask
questions and receive cited answers drawn only from those documents, or suggested client
questions when evidence is insufficient.

## Status

Implementation in progress. See [specs/001-audit-assistant-rag/](specs/001-audit-assistant-rag/)
for the specification, plan, and tasks.

## Workspace

| Path | Package | Role |
|------|---------|------|
| `packages/domain` | `domain` | Domain models (feature packages) |
| `services/backend` | `backend` | HTTP API, business logic, adapters, worker, migrations |
| `cli` | `cli` | `audit-ai` terminal client (HTTP) |

Compose can run a second container of the same backend image with `audit-worker` for background ingest.

## Quick start (dev)

```bash
uv sync
just check
```

Requires Python 3.13, [uv](https://docs.astral.sh/uv/), and [just](https://github.com/casey/just).
All Python commands go through `uv run` / `.venv` (never global pip).
