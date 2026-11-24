# Implementation Plan: Harden Local Security Posture

**Branch**: `002-harden-local-security` | **Date**: 2026-03-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-harden-local-security/spec.md`

## Summary

Close the security-audit run-1 needs-validation leads that matter for a local-only, intentionally unauthenticated AIditor: bind published Compose ports to loopback by default (with documented LAN opt-in), enforce upload size/count limits before full buffering and zip decompression, fail-closed ingest representation ceilings, cap session-history summarization input, require lease-holder checks on job complete/fail, and remove silent Compose/Settings password fallbacks while keeping documented local-demo credentials in `.env.example`. Authentication remains out of scope.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: Existing stack — FastAPI, pydantic-settings, SQLAlchemy 2 async + asyncpg, zipfile stdlib, Docker Compose, Alembic only if schema changes are required for lease mutations (prefer WHERE-clause changes without migration)

**Storage**: PostgreSQL `upload_items` lease columns already exist (`locked_by`, `locked_until`); local FS document storage unchanged

**Testing**: pytest offline (`unit`/`api`) with existing fakes; optional `db` marker for lease race against testcontainers Postgres; no paid APIs

**Target Platform**: Docker Compose on operator workstation (Windows/macOS/Linux hosts); Linux containers for API/worker

**Project Type**: Hardening change set inside existing uv monorepo (`services/backend`, `deployment/docker-compose`, docs)

**Performance Goals**: Reject oversize uploads before unbounded memory growth; ingest fail-closed within configured representation ceilings; ask history prep bounded by `session_max_turns` (new) in addition to `session_context_turns`

**Constraints**: No application auth; offline default tests; constitution layering; Problem Details for new/ clarified limit failures; secret-free repo examples; `just check` must pass

**Scale/Scope**: Local demo / single workstation; 5 user stories (P1 publish + upload, P2 ingest/session + leases, P3 credential bootstrap/docs)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                    | Status | How the plan complies                                                                                                                                                                          |
| -------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Strict Type Safety                        | PASS   | New settings fields typed with Field bounds; domain errors remain typed; no new `Any`                                                                                                          |
| II. Enforced Layering                        | PASS   | Limits enforced in application services + parsing ports; archive size checks in infrastructure adapter implementing existing `ArchiveExtractor` Protocol; Compose/docs outside Python packages |
| III. Tested Behaviour, Offline by Default    | PASS   | FR-015 offline tests for upload-before-expand, representation fail-closed, history ceiling, lease holder; `db` only if needed for SKIP LOCKED race                                             |
| IV. Consistent Errors and Safe Observability | PASS   | Reuse/extend `ErrorCode` + Problem Details; no document bytes or secrets in logs                                                                                                               |
| V. Simplicity Over Breadth                   | PASS   | No new packages/services; auth stays next-step; reject folder-prefix UX as out of scope                                                                                                        |
| VI. Virtual Environment Isolation            | PASS   | All Python via `uv run` / `just`                                                                                                                                                               |
| Product & Security                           | PASS   | Strengthens size/path validation and engagement-scoped worker integrity; loopback publish matches local-only intent                                                                            |
| Workflow & Quality Gates                     | PASS   | Changes land behind `just check`; Alembic only if schema truly required (research prefers no migration)                                                                                        |

**Post-design re-check**: Still PASS. No Complexity Tracking rows required.

## Project Structure

### Documentation (this feature)

```text
specs/002-harden-local-security/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── env-and-compose.md
│   └── error-codes.md
└── tasks.md                 # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
audit-ai/
├── deployment/docker-compose/
│   ├── compose.yaml              # 127.0.0.1:8000:8000; no :-audit password fallback
│   ├── compose.dev.yaml          # 127.0.0.1 binds for 5432/11434
│   ├── .env.example              # explicit POSTGRES_PASSWORD; local-demo warnings
│   └── Caddyfile                 # unchanged proxy behaviour
├── services/backend/src/backend/
│   ├── config.py                 # new representation + session_max_turns; database_url without silent weak default if required
│   ├── application/api/controllers/documents.py
│   ├── application/services/documents.py
│   ├── application/parsing/archive_extractor.py   # Protocol may gain size-aware extract
│   ├── application/rag/worker/… / process_item.py / index_document.py
│   ├── application/agents/research_agent/history.py
│   ├── application/services/ask.py
│   ├── infrastructure/parsing/archive.py
│   ├── infrastructure/parsing/parsers/{pdf,markitdown_convert,default}.py
│   ├── infrastructure/parsing/chunking.py
│   ├── infrastructure/postgres/job_queue.py
│   └── domain/errors.py          # codes for representation_limit / stale_lease if needed
├── services/backend/tests/{unit,api,db}/
├── README.md
└── specs/001-audit-assistant-rag/quickstart.md   # cross-link security notes if needed
```

**Structure Decision**: Extend the existing monorepo paths; no new workspace packages. Compose LAN exposure is a third overlay file rather than changing the default quickstart.

## Complexity Tracking

> None — no constitution violations.
