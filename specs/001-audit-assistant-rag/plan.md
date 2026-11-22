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

**Project Type**: uv workspace monorepo — `domain` + single `backend` service (API + logic + worker) + terminal CLI

**Performance Goals**: Cloud mode: 90% of sample-engagement questions answered under 10 seconds (SC-007). Upload acceptance under 1 second for uploads within limits. Seed-to-first-answer under 15 minutes for a reviewer (SC-001).

**Constraints**: Offline default test suite (no network, no paid keys, no Docker). Answers MUST NOT use model general knowledge. Engagement isolation enforced in data access. No auth/users. No OCR. No streaming. Secret-free config samples. basedpyright strict + import-linter + ruff must pass (`just check`).

**Scale/Scope**: Demo / interview prototype: 1–few engagements, hundreds of documents, tens of thousands of passages. Single backend service; optional second worker container from the same image; shared Postgres with SKIP LOCKED jobs.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                    | Status | How the plan complies                                                                                                                          |
| -------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Strict Type Safety                        | PASS   | basedpyright strict in `just check`; frozen pydantic domain models; distinct id NewTypes; `assert_never` on unions; `Any` only inside adapters |
| II. Enforced Layering                        | PASS   | three workspace members; ports in `backend.application`; vendors only in adapters; CLI uses `backend.api.contracts` over HTTP                  |
| III. Tested Behaviour, Offline by Default    | PASS   | required paths listed in research; fakes behind the same ports; `db` and `integration` markers opt-in                                          |
| IV. Consistent Errors and Safe Observability | PASS   | RFC 9457 Problem Details + stable `ErrorCode` enum; single mapper in `backend.api`; structlog JSON; no document content/secrets in logs        |
| V. Simplicity Over Breadth                   | PASS   | single backend (not split api/core/worker packages); scope matches spec P1→P3; auth/OCR/frontend/streaming stay as next steps                  |
| Product & Security                           | PASS   | grounded answers with citation post-filter; engagement filters in SQL; zip path traversal rejected; OpenAI and Ollama modes by config          |
| Workflow & Quality Gates                     | PASS   | `just check` = ruff + basedpyright + import-linter + offline tests; Alembic-only schema changes under `services/backend`                       |

No unjustified violations. Justified complexity (optional worker process, hybrid search, interactive CLI) is recorded in [research.md](./research.md), not as constitution breaches.

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
│   └── domain/                          # domain (feature packages)
│       ├── pyproject.toml
│       └── src/domain/
│           ├── common.py / errors.py / problem.py / providers.py
│           ├── engagement/ document/ upload/ passage/ answer/ session/
├── services/
│   └── backend/                         # single backend service
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── alembic.ini
│       ├── migrations/
│       └── src/backend/
│           ├── config.py / bootstrap.py / logging.py
│           ├── application/             # ports + use cases
│           ├── adapters/                # postgres, openai, ollama, local_fs
│           ├── rag/ ingestion/          # ask graph + ingest pipeline
│           ├── api/                     # FastAPI + contracts/v1
│           └── worker/main.py           # claim loop (same image)
├── cli/                                 # audit-ai (HTTP client)
├── scripts/ docs/samples/ deployment/ tests/
├── justfile / pyproject.toml / uv.lock / importlinter.ini / README.md
```

**Structure Decision**: Three-member uv workspace (`domain`, `backend`, `cli`) as decided in [research.md](./research.md). Tests live at the repo root. Alembic migrations are owned by `services/backend`.

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
