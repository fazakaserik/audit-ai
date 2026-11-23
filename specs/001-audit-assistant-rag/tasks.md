---
description: "Task list for Audit Assistant implementation"
---

# Tasks: Audit Assistant (Document-Grounded Q&A for Auditors)

**Input**: Design documents from `/specs/001-audit-assistant-rag/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution III and SC-006 require automated coverage of required paths with an offline default suite.

**Organization**: Phases follow user-story priority (P1 → P2 → P3). MVP = US1 + US2 (both P1; US1 scenario 4 depends on insufficient-evidence behaviour).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (`[US1]`…`[US7]`)
- Exact file paths in every description

## Path Conventions

Workspace layout from [plan.md](./plan.md): `services/backend (domain layer)`, `services/backend`, `cli/` (tests colocated under each), `deployment/docker-compose/`, `docs/samples/`, `scripts/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: uv workspace, tooling, empty package skeletons

- [x] T001 Create uv workspace root `pyproject.toml` (Python 3.13, workspace members) and directory tree per plan.md (`services/backend (domain layer)`, `services/backend`, `cli/` (tests colocated under each), `scripts/`, `docs/samples/ai-generated`, `docs/samples/real`)
- [x] T002 [P] Initialize `services/backend (domain layer)/pyproject.toml` package `domain` (pydantic only) with `src/domain/__init__.py`
- [x] T003 [P] Initialize `services/backend/pyproject.toml` package `backend` (legacy task text; now `backend`) with `src/core/__init__.py` and dependency on `domain`
- [x] T004 [P] Initialize `services/api/pyproject.toml` package `api` with `src/api/__init__.py` and dependencies on `core`, `domain`, FastAPI
- [x] T005 [P] Initialize `services/worker/pyproject.toml` package `worker` with `src/worker/__init__.py` and dependency on `core`
- [x] T006 [P] Initialize `cli/pyproject.toml` package `cli` (console script `audit-ai`) with dependency on `domain` only (plus httpx/typer/rich/prompt_toolkit); MUST NOT import backend application/adapters (HTTP + contracts only)
- [x] T007 [P] Add `pyrightconfig.json` (basedpyright strict, workspace extraPaths) and `ruff` config in root `pyproject.toml`
- [x] T008 [P] Add `importlinter.ini` contracts: domain→nothing; application→domain only; vendors only in `core.adapters`; api/worker↛each other; cli→domain only
- [x] T009 [P] Add root `justfile` recipes: `check`, `test`, `test-db`, `test-integration`, `migrate`, `up`, `seed` wrapping `uv run` / `docker compose`
- [x] T010 [P] Add secret-free `deployment/docker-compose/.env.example` with flat env names from research.md (`LLM_PROVIDER`, `DATABASE_URL`, …)
- [x] T011 [P] Add `.gitignore` entries for `.venv`, `__pycache__`, `.env`, `uv.lock` exception (commit lock), storage volumes, pytest cache
- [x] T012 Generate and commit `uv.lock` via `uv sync` for all workspace members

**Checkpoint**: `uv sync` succeeds; empty packages importable

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain types, config, ports, Postgres, fakes, API shell, sync sample ingest — MUST complete before story work

**⚠️ CRITICAL**: No user story work begins until this phase is complete

- [x] T013 [P] Implement id/value types in `services/backend/src/backend/domain/ids.py` citing [data-model.md](./data-model.md) `EngagementId`, `FolderPath`, `DocumentPath`, and UUID `NewType`s (`UploadId`, `DocumentId`, `ChunkId`, `SessionId`, `TurnId`, `RequestId`, …)
- [x] T014 [P] Implement enums in `services/backend/src/backend/domain/enums.py` citing [data-model.md](./data-model.md) `ContentType`, `ErrorCode`, upload/item status enums, `InsufficientEvidence.reason` literals
- [x] T015 [P] Implement `DomainError` hierarchy in `services/backend/src/backend/domain/errors.py` mapped 1:1 to `ErrorCode`
- [x] T016 [P] Implement `ProblemDetails` + `FieldError` in `services/backend/src/backend/domain/problem.py` per contracts/openapi.yaml
- [x] T017 Implement frozen entity models + `Answer` union in `services/backend/src/backend/domain/models.py` citing [data-model.md](./data-model.md) `Engagement`, `Document`, `Chunk`, `Question`, `Citation`, `SuggestedClientQuestion`, `Answered`, `InsufficientEvidence` (Upload/Session/Turn can be stubs completed in later stories)
- [x] T018 [P] Implement `contracts/v1/page.py` generic `Page[T]` (`items`, `total`, `limit`, `offset`) in `services/backend/src/backend/domain/contracts/v1/page.py`
- [x] T019 [P] Implement request DTOs in `services/backend/src/backend/domain/contracts/v1/requests.py` (`CreateEngagementRequest`, `AskRequest`) matching contracts/openapi.yaml
- [x] T020 Implement response DTOs + mappers in `services/backend/src/backend/domain/contracts/v1/responses.py` and `mapping.py` (Engagement, Document, AskResponse union, Health, ProblemDetails)
- [x] T021 Implement `Settings` in `services/backend/src/backend/config.py` (pydantic-settings, flat env names, `SecretStr`, startup validation e.g. openai without key fails)
- [x] T022 [P] Configure structlog JSON logging helper in `services/backend/src/backend/logging.py` (bind `request_id`; never log document/chunk/prompt content)
- [x] T023 Define application ports in `services/backend/src/backend/application/ports.py`: `ChatModel`, `Embedder`, `VectorIndex`, `DocumentStorage`, `EngagementRepository`, `DocumentRepository`, `SessionRepository`, `JobQueue` (Protocols only)
- [x] T024 [P] Implement in-memory fakes for all ports in `services/backend/tests/support/fakes.py` for offline unit/api tests
- [x] T025 Implement SQLAlchemy async engine + session factory in `services/backend/src/backend/infrastructure/postgres/engine.py`
- [x] T026 Implement SQLAlchemy `Mapped` tables in `services/backend/src/backend/infrastructure/postgres/models.py` for `engagements`, `documents`, `chunks` (incl. adapter-only `embedding`, `embedding_model`, `search_vector`) per data-model.md SQL sketch
- [x] T027 Initialize Alembic under `services/backend/` (`alembic.ini`, `migrations/env.py`) and create initial migration for T026 tables + pgvector extension + partial HNSW placeholders + GIN on `search_vector`
- [x] T028 Implement `EngagementRepository` + `DocumentRepository` Postgres adapters in `services/backend/src/backend/infrastructure/postgres/repositories.py` with mandatory `engagement_id` filters
- [x] T029 [P] Implement `local_fs` `DocumentStorage` in `services/backend/src/backend/infrastructure/local_fs.py`
- [x] T030 Implement hybrid `VectorIndex` (vector + FTS + RRF; threshold on cosine similarity before fusion) in `services/backend/src/backend/infrastructure/postgres/vector_index.py`
- [x] T031 [P] Implement OpenAI `ChatModel` + `Embedder` adapters with tenacity retries in `services/backend/src/backend/infrastructure/openai_chat.py` and `openai_embed.py`
- [x] T032 [P] Implement Ollama `ChatModel` + `Embedder` adapters with tenacity retries in `services/backend/src/backend/infrastructure/ollama_chat.py` and `ollama_embed.py`
- [x] T033 Implement composition root `Container` in `services/backend/src/backend/bootstrap.py` wiring Settings → adapters by `LLM_PROVIDER` / `EMBEDDING_PROVIDER`
- [x] T034 Implement sync `IngestDirectory` use case in `services/backend/src/backend/application/ingest_directory.py` (parse→chunk→embed→atomic chunk swap) for sample loading before async upload exists
- [x] T035 [P] Implement Markdown/text/PDF parsers in `services/backend/src/backend/ingestion/parsers.py`
- [x] T036 [P] Implement structure-aware chunker in `services/backend/src/backend/ingestion/chunking.py` (~500 tokens, ~15% overlap; keep heading_path/page)
- [x] T037 Implement FastAPI app factory in `services/backend/src/backend/api/main.py` with request-id middleware (`services/backend/src/backend/api/middleware.py`) and single Problem Details exception mapper (`services/backend/src/backend/api/problem_handlers.py`)
- [x] T038 [P] Implement `GET /health/live` and `GET /health/ready` in `services/backend/src/backend/api/routers/health.py`
- [x] T039 Implement `CreateEngagement` use case + `POST/GET /api/v1/engagements` routers in `services/backend/src/backend/application/create_engagement.py` and `services/backend/src/backend/api/routers/engagements.py` citing [data-model.md](./data-model.md) `Engagement.id`, `Engagement.name`
- [x] T040 Add `deployment/docker-compose/docker-compose.yml` services: `postgres` (pgvector image), `api`, `worker` (stub entrypoint ok), volumes; Dockerfiles for api/worker
- [x] T041 [P] Add pytest config in root `pyproject.toml` (markers `unit`, `db`, `integration`; asyncio mode; default = offline)
- [x] T042 [P] Unit tests for ids/paths/Answer union validation in `services/backend/tests/unit/domain/unit/test_domain_models.py`
- [x] T043 [P] Unit tests for chunking/parsers in `services/backend/tests/unit/test_ingestion.py`
- [x] T044 Db tests scaffold with testcontainers Postgres+pgvector in `services/backend/tests/db/conftest.py`

**Checkpoint**: Foundation ready — engagements creatable; health works; sync ingest + fakes available; `just check` can run (may have few tests)

---

## Phase 3: User Story 1 — Grounded question with citations (Priority: P1) 🎯 MVP part A

**Goal**: Ask a question on an engagement with indexed docs; get `answered` with inline `[n]` citations from retrieved chunks only

**Independent Test**: Sync-ingest sample docs for `northwind-fy2025`, `POST .../ask` with a question whose answer is in a sample file; verify `status=answered`, markers, and citation `document_path`

### Tests for User Story 1

- [x] T045 [P] [US1] Offline unit test: citation post-filter drops unknown markers / empty markers → insufficient in `services/backend/tests/unit/test_citations.py`
- [x] T046 [P] [US1] Offline API test: successful ask returns AnsweredResponse shape in `services/backend/tests/api/test_ask_answered.py` (fake ChatModel/Embedder/VectorIndex)
- [x] T047 [P] [US1] Offline API test: folder_prefix scopes retrieval in `services/backend/tests/api/test_ask_folder_scope.py`
- [x] T048 [P] [US1] Offline API test: cross-engagement isolation (no foreign chunks) in `services/backend/tests/api/test_ask_isolation.py`
- [x] T049 [P] [US1] Offline API test: invalid/empty question → 422 `validation_error` Problem Details in `services/backend/tests/api/test_ask_validation.py` citing [data-model.md](./data-model.md) `Question.text`

### Implementation for User Story 1

- [x] T050 [P] [US1] Implement citation post-filter/renumber in `services/backend/src/backend/rag/citations.py` citing [data-model.md](./data-model.md) `Citation.marker`, `Citation.score`, `Citation.snippet`
- [x] T051 [P] [US1] Implement RAG prompts in `services/backend/src/backend/rag/prompts.py` (forbid general knowledge; require `[n]` markers)
- [x] T052 [US1] Implement LangGraph state + nodes (`retrieve`, `grade_evidence`, `generate_answer`, `finalize`) in `services/backend/src/backend/rag/state.py`, `nodes.py`, `graph.py` (no condense yet)
- [x] T053 [US1] Implement `AskQuestion` use case in `services/backend/src/backend/application/ask_question.py` (creates Session/Turn minimally: persist question+answer; return `session_id`/`turn_id`) citing [data-model.md](./data-model.md) `Answered.text`, `Answered.citations`
- [x] T054 [US1] Add Alembic migration for `sessions` + `session_turns` tables if not in T027; extend Postgres session repository in `services/backend/src/backend/infrastructure/postgres/repositories.py` citing [data-model.md](./data-model.md) `Session.title`, `Session.turn_count`, `Turn.question`, `Turn.standalone_question`, `Turn.answer`
- [x] T055 [US1] Implement `POST /api/v1/engagements/{engagement_id}/ask` in `services/backend/src/backend/api/routers/ask.py` per contracts/openapi.yaml
- [x] T056 [US1] Create minimal AI sample docs under `docs/samples/ai-generated/northwind-fy2025/` (finance/contracts/policies/…) sufficient for ≥6 answerable questions
- [x] T057 [US1] Add `scripts/seed_samples.py` calling sync `IngestDirectory` (temporary until US3 HTTP seed) to load northwind sample

**Checkpoint**: US1 demoable with seed + ask; MVP part A green under fakes + manual cloud/local smoke

---

## Phase 4: User Story 2 — Insufficient evidence + suggested client questions (Priority: P1) 🎯 MVP part B

**Goal**: When evidence is missing/weak, return `insufficient_evidence` with 1–3 suggested client questions; never fabricate facts

**Independent Test**: Ask an uncovered question on sample engagement; assert status, suggestions, no factual answer

### Tests for User Story 2

- [x] T058 [P] [US2] Offline unit test: grade_evidence empty → no LLM generate in `services/backend/tests/unit/test_grade_evidence.py`
- [x] T059 [P] [US2] Offline API test: no hits → `insufficient_evidence` + 1..3 suggestions in `services/backend/tests/api/test_ask_insufficient.py`
- [x] T060 [P] [US2] Offline API test: role/topic influence suggestion text in `services/backend/tests/api/test_ask_suggestions_role_topic.py`
- [x] T061 [P] [US2] Offline API test: model timeout → 504 `model_timeout`; provider error → 502 `model_unavailable` in `services/backend/tests/api/test_ask_model_errors.py`

### Implementation for User Story 2

- [x] T062 [US2] Implement `suggest_client_questions` node + wiring from grade/generate branches in `services/backend/src/backend/rag/nodes.py` citing [data-model.md](./data-model.md) `InsufficientEvidence.reason`, `InsufficientEvidence.suggested_client_questions`, `InsufficientEvidence.partial_citations`
- [x] T063 [US2] Ensure `AskResponse` mapping emits `InsufficientEvidenceResponse` only (no answer field) in `services/backend/src/backend/domain/contracts/v1/mapping.py`
- [x] T064 [US2] Document ≥3 insufficient-evidence example questions next to sample data in `docs/samples/ai-generated/northwind-fy2025/README.md`

**Checkpoint**: US1+US2 = MVP; both answer outcomes work offline and via quickstart scenarios A/C

---

## Phase 5: User Story 3 — Async document upload (Priority: P2)

**Goal**: Accept multipart/zip uploads to a folder, process in worker, poll status; atomic replace; reject unsafe zips

**Independent Test**: Create engagement, upload nested zip, poll to completed, ask a question answered by an uploaded file

### Tests for User Story 3

- [x] T065 [P] [US3] Offline unit test: zip path-traversal rejected in `services/backend/tests/unit/test_archive_safety.py`
- [x] T066 [P] [US3] Offline API test: upload returns 202 queued; oversized → 413; unsafe → 400 `unsafe_upload` in `services/backend/tests/api/test_upload_accept.py`
- [ ] T067 [P] [US3] Db test: `SKIP LOCKED` claim does not double-process in `services/backend/tests/db/test_job_queue.py`
- [ ] T068 [P] [US3] Db test: atomic document version swap leaves no mixed chunks in `services/backend/tests/db/test_document_replace.py` citing [data-model.md](./data-model.md) `Document.version`, `Chunk.document_version`

### Implementation for User Story 3

- [x] T069 [P] [US3] Implement safe archive listing/extract in `services/backend/src/backend/ingestion/archive.py`
- [x] T070 [US3] Extend domain models for Upload/UploadItem in `services/backend/src/backend/domain/models.py` citing [data-model.md](./data-model.md) `Upload.status`, `Upload.target_folder`, `UploadItem.status`, `UploadItem.document_path`, `UploadItem.reason`, `UploadItem.attempts`
- [x] T071 [US3] Alembic migration + SQLAlchemy models for `uploads`/`upload_items` (adapter fields `locked_until`, `next_attempt_at`, `raw_storage_key`) in `services/backend/migrations/` and `adapters/postgres/models.py`
- [x] T072 [US3] Implement `JobQueue` Postgres adapter (`FOR UPDATE SKIP LOCKED`, lease, retries) in `services/backend/src/backend/infrastructure/postgres/job_queue.py`
- [x] T073 [US3] Implement `UploadDocuments` use case (validate→store files→enqueue items→202) in `services/backend/src/backend/application/upload_documents.py`
- [x] T074 [US3] Implement `GetUpload` use case + contracts mapping in `services/backend/src/backend/application/get_upload.py` and backend.application.api.contracts
- [x] T075 [US3] Implement `POST .../documents` and `GET .../uploads/{upload_id}` in `services/backend/src/backend/api/routers/uploads.py` / `documents.py` per openapi.yaml
- [x] T076 [US3] Implement per-item processing pipeline in `services/backend/src/backend/ingestion/process_item.py` (parse/chunk/embed/swap; skipped/not_searchable/failed reasons) citing [data-model.md](./data-model.md) `Document.content_type`, `Document.size_bytes`, `Document.sha256`, `Document.searchable`
- [x] T077 [US3] Implement worker claim loop + graceful shutdown in `services/backend/src/backend/worker/main.py`
- [x] T078 [US3] Switch `scripts/seed_samples.py` to call HTTP upload via CLI/`httpx` with `--wait` (remove sync-only seed path from happy path)

**Checkpoint**: Uploads work end-to-end; seed uses real async path

---

## Phase 6: User Story 4 — Browse and read documents (Priority: P2)

**Goal**: List documents (prefix filter) and download original bytes

**Independent Test**: List `policies/`, GET one file, byte-compare to sample

### Tests for User Story 4

- [x] T079 [P] [US4] Offline API test: list with prefix + 404 on missing path in `services/backend/tests/api/test_documents_list_get.py`

### Implementation for User Story 4

- [x] T080 [US4] Implement `ListDocuments` + `GetDocument` use cases in `services/backend/src/backend/application/list_documents.py` and `get_document.py` citing [data-model.md](./data-model.md) `Document.path`, `Document.content_type`, `Document.size_bytes`
- [x] T081 [US4] Implement `GET .../documents` and `GET .../documents/{document_path}` in `services/backend/src/backend/api/routers/documents.py` returning metadata JSON / raw octets per openapi.yaml

**Checkpoint**: Citations are verifiable by opening the source file via API

---

## Phase 7: User Story 6 — Sessions and follow-ups (Priority: P2)

**Goal**: Optional `session_id` on ask; `condense_question` for follow-ups; list/get sessions with turns

**Independent Test**: Two-turn pronoun follow-up cites same contract; list/resume returns full history

### Tests for User Story 6

- [x] T082 [P] [US6] Offline unit test: condense uses prior turns; evidence still only from retrieval in `services/backend/tests/unit/test_condense_question.py`
- [x] T083 [P] [US6] Offline API test: ask without session creates session; follow-up with session_id continues; wrong engagement → 404 in `services/backend/tests/api/test_sessions.py`

### Implementation for User Story 6

- [x] T084 [US6] Add `condense_question` graph node in `services/backend/src/backend/rag/nodes.py` using `SESSION_CONTEXT_TURNS` (default 5)
- [x] T085 [US6] Implement `ListSessions` + `GetSession` use cases in `services/backend/src/backend/application/list_sessions.py` and `get_session.py`
- [x] T086 [US6] Implement `GET .../sessions` and `GET .../sessions/{session_id}` in `services/backend/src/backend/api/routers/sessions.py` per openapi.yaml
- [x] T087 [US6] Ensure ask always returns `session_id`/`turn_id` and title derived from first question citing [data-model.md](./data-model.md) `Session.title`

**Checkpoint**: Conversational follow-ups work without weakening grounding

---

## Phase 8: User Story 5 — Cloud/local modes, ops, sample reproducibility (Priority: P3)

**Goal**: Config-only provider switch; documented compose/Ollama; readiness names failures; seed via documented commands

**Independent Test**: Local mode with no paid key completes US1/US2; ready probe fails closed when Postgres down

### Tests for User Story 5

- [x] T088 [P] [US5] Offline unit test: Settings validation rejects openai without key in `services/backend/tests/unit/test_settings.py`
- [x] T089 [P] [US5] Offline API test: readiness aggregates dependency failures in `services/backend/tests/api/test_health_ready.py`

### Implementation for User Story 5

- [x] T090 [US5] Add compose `local` profile with `ollama` + one-shot pull service; document host `OLLAMA_BASE_URL` in `deployment/docker-compose/docker-compose.yml` and README
- [x] T091 [US5] Flesh readiness checks (Postgres + model ping) in `services/backend/src/backend/api/routers/health.py`
- [x] T092 [US5] Finalize `just seed` / `scripts/seed_samples.py` against running stack; align with quickstart.md
- [x] T093 [US5] Write root `README.md` sections: problem, architecture, OpenAI mode, Ollama mode (RAM/limits), concurrency/scaling, limitations/next steps (assignment §5–7)

**Checkpoint**: Reviewer can follow quickstart in <15 minutes (excl. model download)

---

## Phase 9: User Story 7 — Interactive terminal client (Priority: P3)

**Goal**: `audit-ai` REPL + non-interactive subcommands over HTTP only

**Independent Test**: Ask via REPL, quit, resume session; upload with `--wait`

### Tests for User Story 7

- [x] T094 [P] [US7] Offline unit test: client maps Problem Details to CLI errors in `cli/tests/unit/test_cli_client.py` (httpx mock)

### Implementation for User Story 7

- [x] T095 [P] [US7] Implement typed HTTP client in `cli/src/cli/client.py` using `backend.application.api.contracts.v1`
- [x] T096 [P] [US7] Implement Rich renderers (answer, citations footnotes, suggestions, errors) in `cli/src/cli/render.py`
- [x] T097 [US7] Implement Typer subcommands (`engagements`, `upload`, `uploads status`, `sessions`) in `cli/src/cli/main.py` per contracts/cli.md
- [x] T098 [US7] Implement prompt_toolkit REPL + slash commands in `cli/src/cli/repl.py` (auto-carry `session_id`)
- [x] T099 [US7] Point `scripts/seed_samples.py` at `audit-ai` subcommands exclusively

**Checkpoint**: Full demo without curl; API proven by a real client

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Quality gate, docs, assignment extras

- [ ] T100 [P] Add OpenAPI export/verify script or FastAPI schema alignment check against `specs/001-audit-assistant-rag/contracts/openapi.yaml`
- [x] T101 [P] Expand `docs/samples/real/README.md` with source/licence template for committed public documents
- [ ] T102 Run full `just check` (ruff, basedpyright, import-linter, offline tests) and fix until green
- [x] T103 [P] Add optional `@pytest.mark.integration` smoke tests in `services/backend/tests/integration/` (skipped by default)
- [ ] T104 Execute [quickstart.md](./quickstart.md) scenarios A–E and record any doc fixes
- [x] T105 [P] Review `deployment/cloud/README.md` for consistency with final ports/adapters
- [x] T106 Final README pass: known limits, next steps (auth/contacts/outreach, Azure AI Search, OCR, chunk tuning)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: start immediately
- **Phase 2 Foundational**: depends on Setup — **BLOCKS all stories**
- **Phase 3–4 (US1, US2)**: after Foundational — MVP
- **Phase 5–7 (US3, US4, US6)**: after MVP; US4 needs documents (from seed sync or US3); US6 builds on ask/session rows from US1
- **Phase 8–9 (US5, US7)**: after core API stable; US7 after US3 upload endpoints for CLI upload command
- **Phase 10 Polish**: after desired stories complete

### User Story Dependencies

```text
Setup → Foundational → US1 → US2 (MVP)
                         ↓
                        US3 → US4
                         ↓
                        US6
                         ↓
                   US5 + US7 → Polish
```

- **US1**: after Foundational; uses sync ingest for samples
- **US2**: after US1 graph exists (extends same ask path)
- **US3**: after Foundational; replaces sync seed path when done
- **US4**: needs Document storage (US1 ingest or US3)
- **US6**: needs US1 ask/session persistence
- **US5**: ops/docs; needs US1–2 working; Ollama adapter from Foundational
- **US7**: needs ask + engagements; upload subcommand needs US3; sessions commands need US6

### Within Each Story

- Tests marked first SHOULD be written and failing before implementation
- Models/contracts before use cases before routers
- Story checkpoint before next priority

### Parallel Opportunities

- Phase 1: T002–T011 marked [P]
- Phase 2: domain files T013–T016, parsers/chunking T035–T036, model adapters T031–T032, tests T042–T043
- Per story: all [P] tests in parallel; independent implementation files in parallel
- After MVP: US3 and US6 can proceed in parallel if staffed (different files); US4 after documents exist

---

## Parallel Example: User Story 1

```bash
# Tests in parallel:
Task: "T045 citation post-filter unit tests in services/backend/tests/unit/test_citations.py"
Task: "T046 ask answered API test in services/backend/tests/api/test_ask_answered.py"
Task: "T047 folder scope API test in services/backend/tests/api/test_ask_folder_scope.py"
Task: "T048 isolation API test in services/backend/tests/api/test_ask_isolation.py"

# Then implementation (citations/prompts parallel, then graph):
Task: "T050 citations.py"
Task: "T051 prompts.py"
Task: "T052 graph nodes"
Task: "T053 AskQuestion use case"
Task: "T055 ask router"
```

---

## Parallel Example: User Story 3

```bash
Task: "T065 archive safety unit test"
Task: "T066 upload accept API test"
Task: "T069 archive.py implementation"
# After models/migration:
Task: "T072 job_queue.py"
Task: "T077 worker main.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1 Setup
2. Phase 2 Foundational
3. Phase 3 US1 — grounded answers
4. Phase 4 US2 — insufficient evidence
5. **STOP and VALIDATE** quickstart scenarios A and C with fakes/`just check`, then one real provider smoke

### Incremental Delivery

1. MVP (US1+US2) → demo Q&A
2. US3 → real uploads + worker → switch seed to HTTP
3. US4 → open cited sources
4. US6 → follow-ups/resume
5. US5 → polish ops/README/Ollama profile
6. US7 → interactive CLI demo
7. Polish → assignment submission readiness

### Suggested MVP Scope

**US1 + US2 only** (both P1). Sync sample ingest is enough to demo; defer async upload, CLI, and sessions list UI until after MVP validation.

---

## Notes

- [P] = different files, no incomplete-task dependencies
- Cite constrained fields via [data-model.md](./data-model.md) entity.field references in implementing tasks (done above for all constrained entities)
- Commit after each task or cohesive group
- `just check` must stay green as stories land
- Do not start US5/US7 polish features while US1–US2 are incomplete (Constitution V)
