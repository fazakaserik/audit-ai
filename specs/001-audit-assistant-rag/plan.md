# Implementation Plan: Audit Assistant (Document-Grounded Q&A for Auditors)

**Branch**: `001-audit-assistant-rag` | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-audit-assistant-rag/spec.md`

## Summary

Build a backend-only, document-grounded auditor assistant as a uv monorepo. Clients upload documents (files or zip) into an engagement folder tree; auditors ask questions and receive answers grounded only in those documents, with inline numbered citations, or `insufficient_evidence` with suggested client questions. Follow-up questions live in server-side sessions. Upload indexing runs asynchronously in a worker. Cloud (OpenAI) and free local (Ollama) modes switch by configuration. An interactive terminal CLI (`audit-ai`) is the primary demo client. Postgres + pgvector is the single datastore (metadata, jobs, hybrid search). Azure AI Search is the documented cloud search target.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: FastAPI, LangGraph (graph only), pydantic v2, pydantic-settings, SQLAlchemy 2.0 async + asyncpg + Alembic + pgvector-python, openai SDK, ollama SDK, tenacity, structlog, httpx, Typer, prompt_toolkit, Rich, ruff, basedpyright, import-linter, pytest + pytest-asyncio + testcontainers, uv, just

**Storage**: PostgreSQL 16 with pgvector (metadata, passages, embeddings, job queue, sessions); local filesystem volume for raw document bytes (Azure Blob documented as cloud target)

**Testing**: pytest; markers `unit` (default, offline fakes), `db` (testcontainers Postgres+pgvector), `integration` (real Ollama/OpenAI, opt-in)

**Target Platform**: Linux containers via Docker Compose (dev/demo); Windows/macOS hosts for CLI and optional host-side Ollama

**Project Type**: uv workspace monorepo — library packages + HTTP API service + worker service + terminal CLI

**Performance Goals**: Cloud mode: 90% of sample-engagement questions answered under 10 seconds (SC-007). Upload acceptance under 1 second for uploads within limits. Seed-to-first-answer under 15 minutes for a reviewer (SC-001).

**Constraints**: Offline default test suite (no network, no paid keys, no Docker). Answers MUST NOT use model general knowledge. Engagement isolation enforced in data access. No auth/users. No OCR. No streaming. Secret-free config samples. basedpyright strict + import-linter + ruff must pass (`just check`).

**Scale/Scope**: Demo / interview prototype: 1–few engagements, hundreds of documents, tens of thousands of passages. Designed so API and worker scale independently; multi-instance ready (stateless API, shared Postgres, SKIP LOCKED jobs).

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                    | Status | How the plan complies                                                                                                                                |
| -------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Strict Type Safety                        | PASS   | basedpyright strict in `just check`; frozen pydantic domain models; distinct id NewTypes; `assert_never` on unions; `Any` only inside adapters       |
| II. Enforced Layering                        | PASS   | five workspace members with import-linter contracts; ports in `core.application`; vendors only in adapters; CLI depends only on `domain` |
| III. Tested Behaviour, Offline by Default    | PASS   | required paths listed in research; fakes behind the same ports; `db` and `integration` markers opt-in                                                |
| IV. Consistent Errors and Safe Observability | PASS   | RFC 9457 Problem Details + stable `ErrorCode` enum; single mapper in `api`; structlog JSON; no document content/secrets in logs                |
| V. Simplicity Over Breadth                   | PASS   | scope matches spec P1→P3; auth/OCR/frontend/streaming stay as next steps; ports have ≥2 implementations (real + fake, or openai + ollama)            |
| Product & Security                           | PASS   | grounded answers with citation post-filter; engagement filters in SQL; zip path traversal rejected; OpenAI and Ollama modes by config                |
| Workflow & Quality Gates                     | PASS   | `just check` = ruff + basedpyright + import-linter + offline tests; Alembic-only schema changes                                                      |

No unjustified violations. Justified complexity (worker process, hybrid search, interactive CLI) is recorded in [research.md](./research.md), not as constitution breaches.

## Project Structure

### Documentation (this feature)

```text
specs/001-audit-assistant-rag/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   └── cli.md
└── tasks.md                 # created by /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
audit-ai/
├── packages/
│   ├── domain/                          # domain
│   │   ├── pyproject.toml
│   │   └── src/domain/
│   │       ├── __init__.py
│   │       ├── ids.py                   # NewTypes, EngagementId, DocumentPath, ...
│   │       ├── enums.py                 # ErrorCode, UploadStatus, AnswerStatus, ...
│   │       ├── models.py                # entities + Answer union
│   │       ├── errors.py                # DomainError hierarchy
│   │       ├── problem.py               # ProblemDetails model
│   │       └── contracts/
│   │           └── v1/
│   │               ├── requests.py
│   │               ├── responses.py
│   │               ├── mapping.py
│   │               └── page.py
│   └── core/                            # core
│       ├── pyproject.toml
│       └── src/core/
│           ├── __init__.py
│           ├── config.py                # pydantic-settings (flat env names)
│           ├── bootstrap.py             # composition root → frozen Container
│           ├── application/
│           │   ├── ports.py             # Protocols
│           │   ├── create_engagement.py
│           │   ├── upload_documents.py
│           │   ├── get_upload.py
│           │   ├── list_documents.py
│           │   ├── get_document.py
│           │   ├── ask_question.py
│           │   ├── list_sessions.py
│           │   └── get_session.py
│           ├── rag/
│           │   ├── state.py
│           │   ├── graph.py
│           │   ├── nodes.py
│           │   ├── prompts.py
│           │   └── citations.py         # marker post-filter / renumber
│           ├── ingestion/
│           │   ├── archive.py           # zip validation + safe extract listing
│           │   ├── parsers.py           # md / txt / pdf
│           │   ├── chunking.py
│           │   └── process_item.py      # per-file pipeline used by worker
│           └── adapters/
│               ├── openai_chat.py
│               ├── openai_embed.py
│               ├── ollama_chat.py
│               ├── ollama_embed.py
│               ├── postgres/
│               │   ├── engine.py
│               │   ├── models.py        # SQLAlchemy Mapped[...] tables
│               │   ├── repositories.py
│               │   ├── vector_index.py  # hybrid search + RRF
│               │   └── job_queue.py
│               └── local_fs.py
├── services/
│   ├── api/                             # api
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   └── src/api/
│   │       ├── main.py
│   │       ├── dependencies.py
│   │       ├── middleware.py
│   │       ├── problem_handlers.py
│   │       └── routers/
│   │           ├── health.py
│   │           ├── engagements.py
│   │           ├── documents.py
│   │           ├── uploads.py
│   │           ├── ask.py
│   │           └── sessions.py
│   └── worker/                          # worker
│       ├── pyproject.toml
│       ├── Dockerfile
│       └── src/worker/
│           └── main.py                  # claim loop + graceful shutdown
├── cli/                                 # cli (command: audit-ai)
│   ├── pyproject.toml
│   └── src/cli/
│       ├── __init__.py
│       ├── main.py                      # Typer app
│       ├── client.py                    # httpx client using contracts/v1
│       ├── render.py                    # Rich rendering
│       └── repl.py                      # prompt_toolkit interactive session
├── packages/core/migrations/            # Alembic (owned by core)
│   ├── env.py
│   └── versions/
├── scripts/
│   └── seed_samples.py
├── docs/
│   └── samples/
│       ├── ai-generated/
│       └── real/
├── deployment/
│   ├── docker-compose/
│   │   ├── docker-compose.yml
│   │   └── .env.example
│   └── cloud/
│       └── README.md
├── tests/                               # workspace-root tests (or per-package; see note)
│   ├── unit/
│   ├── api/
│   ├── db/
│   ├── integration/
│   └── support/                         # shared fakes implementing ports
├── justfile
├── pyproject.toml                       # uv workspace root
├── uv.lock
├── importlinter.ini
├── pyrightconfig.json
└── README.md
```

**Structure Decision**: Five-member uv workspace as decided in [research.md](./research.md). Tests live at the repo root so one `pytest` invocation covers all packages; packages remain importable as installed workspace members. Alembic migrations live under `packages/core` because schema ownership belongs with the Postgres adapters.

## Complexity Tracking

> No constitution violations requiring justification. The following are scope decisions already justified in research.md (listed here for reviewer visibility only).

| Choice                             | Why Needed                                           | Simpler Alternative Rejected Because                                                                  |
| ---------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Separate worker process            | Embedding is slow/rate-limited; HTTP must return 202 | Sync indexing blocks requests; in-process tasks die on restart and break multi-instance               |
| Hybrid search (vector + FTS + RRF) | Audit questions contain exact ids/amounts            | Vector-only ranks exact identifiers poorly                                                            |
| Interactive terminal CLI           | Live demo + proves public API completeness           | curl-only demo is weaker for interview; assignment frontend earns no credit                           |
| Server-side sessions               | Follow-ups + resume across CLI restarts              | Stateless ask only cannot resolve pronouns; client-only history cannot be resumed from another client |

## Phase 0 / Phase 1 outputs

- [research.md](./research.md) — decisions complete; open items (embedding dimensions, relevance threshold) resolved
- [data-model.md](./data-model.md) — entities, validation, state transitions, SQL sketch
- [contracts/openapi.yaml](./contracts/openapi.yaml) — HTTP API contract
- [contracts/cli.md](./contracts/cli.md) — terminal client command contract
- [quickstart.md](./quickstart.md) — end-to-end validation scenarios

## Post-design Constitution Check

Re-evaluated after Phase 1 artifacts: **PASS**. Contracts use discriminated unions and Problem Details; data model keeps embeddings/job leases out of the domain; quickstart exercises offline-capable seeding and both answer outcomes; no new ports without dual implementations; no auth/OCR/streaming introduced.
