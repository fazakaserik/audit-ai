# Tasks: Harden Local Security Posture

**Input**: Design documents from `/specs/002-harden-local-security/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — spec **FR-015** requires offline automated tests for upload pre-expansion limits, representation fail-closed ingest, session history ceiling, and lease-holder transitions.

**Organization**: Phases follow user stories US1–US5 from spec.md (P1 → P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 for story phases only
- Paths are repository-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align local env/docs pointers for this hardening feature (no new packages).

- [X] T001 Confirm feature docs present under `specs/002-harden-local-security/` (`plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`) and note working branch for implementation
- [X] T002 [P] Add a short “Local security posture” pointer section in `README.md` linking to `specs/002-harden-local-security/quickstart.md` (details filled in later polish)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared Settings / error-code groundwork before story work.

**⚠️ CRITICAL**: No user story implementation until this phase completes.

- [X] T003 Extend `Settings` in `services/backend/src/backend/config.py` with representation and session budget fields citing `data-model.md` `RepresentationLimitPolicy.ingest_max_expanded_chars`, `RepresentationLimitPolicy.ingest_max_pages`, `RepresentationLimitPolicy.ingest_max_chunks`, and `SessionHistoryBudget.session_max_turns` (keep existing `UploadLimitPolicy.upload_max_*` and `SessionHistoryBudget.session_context_turns`; validate `session_max_turns >= session_context_turns`)
- [X] T004 [P] Update `services/backend/tests/unit/test_settings.py` for new Settings fields and validation failures
- [X] T005 [P] Add optional `representation_limit_exceeded` to `ErrorCode` in `services/backend/src/backend/domain/errors.py` per `contracts/error-codes.md` (wire Problem Details mapper only if a sync path needs it; otherwise document worker `reason` usage)
- [X] T006 [P] Document new env vars in `deployment/docker-compose/.env.example` for `INGEST_MAX_*` and `SESSION_MAX_TURNS` (values only; credential/password wording is US5)

**Checkpoint**: Foundation ready — user stories can proceed

---

## Phase 3: User Story 1 — Local stack stays on this machine by default (Priority: P1) 🎯 MVP

**Goal**: Default and dev Compose publish bindings are loopback-only (`PublishBindingPosture` in `data-model.md`). No LAN overlay ships.

**Independent Test**: `docker compose … config` shows `127.0.0.1` on default/dev publishes (`contracts/env-and-compose.md`, `quickstart.md` §5).

### Tests for User Story 1

- [X] T007 [P] [US1] Add a small offline check script or pytest that parses compose YAML / `docker compose config` output asserting loopback host binds for default and dev overlays in `services/backend/tests/unit/test_compose_publish_binds.py` (skip if Docker unavailable; still assert static file contents for `127.0.0.1:`)

### Implementation for User Story 1

- [X] T008 [P] [US1] Change `load-balancer` ports in `deployment/docker-compose/compose.yaml` to `127.0.0.1:8000:8000` per `data-model.md` `PublishBindingPosture` local default and `contracts/env-and-compose.md`
- [X] T009 [P] [US1] Change Postgres/Ollama host ports in `deployment/docker-compose/compose.dev.yaml` to `127.0.0.1:5432:5432` and `127.0.0.1:11434:11434`
- [X] T010 [US1] ~~Add `compose.lan.yaml`~~ Declined — keep loopback-only defaults; no LAN overlay
- [X] T011 [US1] Document default loopback publish in `README.md` and `specs/002-harden-local-security/quickstart.md` (operator steps only; no auth claims)

**Checkpoint**: US1 independently verifiable via compose config / static bind assertions

---

## Phase 4: User Story 2 — Uploads cannot blow past stated size promises (Priority: P1)

**Goal**: Enforce `UploadLimitPolicy` before full buffering and zip member materialization.

**Independent Test**: Offline API/unit tests reject oversize/zip-bomb fixtures with `payload_too_large` without accepting planned oversized payloads (`quickstart.md` §2, FR-015).

### Tests for User Story 2

- [X] T012 [P] [US2] Extend `services/backend/tests/api/test_upload_accept.py` with cases: raw part over `upload_max_file_bytes`, count over `upload_max_files`, zip whose `ZipInfo.file_size` exceeds limits before read (cite `data-model.md` `UploadLimitPolicy.upload_max_file_bytes`, `UploadLimitPolicy.upload_max_files`, `UploadLimitPolicy.upload_max_bytes`)
- [X] T013 [P] [US2] Extend `services/backend/tests/unit/test_archive_safety.py` for pre-read size refusal and preserved path/symlink rejection

### Implementation for User Story 2

- [X] T014 [US2] Bound multipart reads in `services/backend/src/backend/application/api/controllers/documents.py` using Settings `upload_max_file_bytes` / running total vs `upload_max_bytes` / count vs `upload_max_files` (`data-model.md` `UploadLimitPolicy.*`)
- [X] T015 [US2] Extend `ArchiveExtractor` Protocol in `services/backend/src/backend/application/parsing/archive_extractor.py` and implement size-aware extraction in `services/backend/src/backend/infrastructure/parsing/archive.py` (check `ZipInfo.file_size` before `read`; re-check `len(payload)`; raise `PayloadTooLargeError`)
- [X] T016 [US2] Pass limit context into `_expand_incoming` / `DocumentService.upload_documents` in `services/backend/src/backend/application/services/documents.py`; keep post-expand `_enforce_limits` as defense-in-depth; preserve unsafe-path behaviour
- [X] T017 [US2] Update fakes implementing `ArchiveExtractor` under `services/backend/tests/support/` so new Protocol methods compile and tests pass

**Checkpoint**: US2 upload limits match stated policy before expansion

---

## Phase 5: User Story 3 — Ingest and ask work stay within operator-visible budgets (Priority: P2)

**Goal**: Fail-closed `RepresentationLimitPolicy` during ingest; ask uses newest `SessionHistoryBudget.session_max_turns`.

**Independent Test**: Offline fixtures over page/char/chunk ceilings fail closed; long-session ask only feeds newest-N into history prep (`quickstart.md` §3).

### Tests for User Story 3

- [X] T018 [P] [US3] Add unit/API tests in `services/backend/tests/unit/test_ingest_representation_limits.py` (and/or worker-focused unit) for over-page / over-char / over-chunk fail-closed citing `data-model.md` `RepresentationLimitPolicy.ingest_max_pages`, `RepresentationLimitPolicy.ingest_max_expanded_chars`, `RepresentationLimitPolicy.ingest_max_chunks`
- [X] T019 [P] [US3] Add tests in `services/backend/tests/unit/test_session_history_budget.py` (or extend ask tests) proving summarization/context uses at most `session_max_turns` newest turns citing `data-model.md` `SessionHistoryBudget.session_max_turns` and `SessionHistoryBudget.session_context_turns`

### Implementation for User Story 3

- [X] T020 [P] [US3] Enforce page/char ceilings in `services/backend/src/backend/infrastructure/parsing/parsers/pdf.py` and post-convert checks in `markitdown_convert.py` / `default.py` using Settings representation fields
- [X] T021 [US3] Enforce `ingest_max_chunks` before embed in `services/backend/src/backend/application/rag/index_document.py` and/or `services/backend/src/backend/infrastructure/parsing/chunking.py`; fail closed from `process_item.py` with clear `reason` (no successful partial index)
- [X] T022 [US3] Limit turns loaded for ask context in `services/backend/src/backend/application/services/ask.py` to newest `session_max_turns`; ensure `prepare_session_context` in `services/backend/src/backend/application/agents/research_agent/history.py` only sees that window
- [X] T023 [US3] Thread new Settings into bootstrap/worker container wiring in `services/backend/src/backend/bootstrap.py` if parsers/index need explicit limit args

**Checkpoint**: US3 budgets independently testable offline

---

## Phase 6: User Story 4 — Background ingest jobs respect their lease (Priority: P2)

**Goal**: `complete` / `fail_for_retry` only succeed for current `UploadItem.locked_by` holder.

**Independent Test**: Stale complete after reclaim does not change terminal state; current holder succeeds (`quickstart.md` §4, `data-model.md` lease transitions).

### Tests for User Story 4

- [X] T024 [P] [US4] Add offline unit tests with a fake/in-memory job queue or SQLAlchemy-backed unit double in `services/backend/tests/unit/test_job_queue_lease.py` covering stale complete/fail vs holder success (cite `data-model.md` `UploadItem.locked_by`, lease transition rules)
- [X] T025 [P] [US4] Optional `db`-marked race test in `services/backend/tests/db/test_job_queue_lease_race.py` if SKIP LOCKED reclaim needs Postgres (keep default suite offline)

### Implementation for User Story 4

- [X] T026 [US4] Update `JobQueue` Protocol in `services/backend/src/backend/application/` (repositories/ports) so `complete` / `fail_for_retry` require `worker_id`
- [X] T027 [US4] Implement lease-matched UPDATEs in `services/backend/src/backend/infrastructure/postgres/job_queue.py` (`id` + `locked_by` + `PROCESSING`); zero rows → stale lease error/false
- [X] T028 [US4] Pass `worker_id` from `services/backend/src/backend/application/rag/worker/main.py` into complete/fail; treat stale as non-success without corrupting state
- [X] T029 [US4] Update test fakes for `JobQueue` under `services/backend/tests/support/` for the new signatures

**Checkpoint**: US4 lease integrity independently testable

---

## Phase 7: User Story 5 — Bootstrap credentials match local-only expectations (Priority: P3)

**Goal**: No silent Compose/Settings password fallback; example file keeps local-demo values with warnings (`contracts/env-and-compose.md`).

**Independent Test**: Unset `POSTGRES_PASSWORD` fails compose/start; `cp .env.example .env` still works with documented `audit` demo password; docs warn about non-loopback use.

### Tests for User Story 5

- [X] T030 [P] [US5] Add unit test ensuring application Settings no longer silently embeds a required production-like default password path inconsistently — assert documented test fixtures still construct Settings; document compose fallback removal via static assert that `compose.yaml` has no `${POSTGRES_PASSWORD:-audit}` in `services/backend/tests/unit/test_compose_credentials.py`

### Implementation for User Story 5

- [X] T031 [US5] Remove `${POSTGRES_PASSWORD:-audit}` (and related user/db silent defaults if required by contract) from `deployment/docker-compose/compose.yaml`; require explicit env from `.env`
- [X] T032 [US5] Keep `POSTGRES_PASSWORD=audit` in `deployment/docker-compose/.env.example` with local-demo + loopback warnings; align `DATABASE_URL` comments
- [X] T033 [US5] Adjust `Settings.database_url` default in `services/backend/src/backend/config.py` so non-test runtime does not silently imply a hidden compose fallback story (tests/fixtures supply URLs explicitly as needed)
- [X] T034 [US5] Update operator docs in `README.md` for explicit password requirement and local-demo credential warning (FR-012)

**Checkpoint**: US5 bootstrap behaviour matches contract

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Gate, docs consistency, deferred items stay out of scope.

- [X] T035 [P] Cross-link security notes in `specs/001-audit-assistant-rag/quickstart.md` if it still implies all-interface publish
- [X] T036 Run `just check` and fix ruff / basedpyright / import-linter / offline test failures
- [X] T037 Execute `specs/002-harden-local-security/quickstart.md` validation checklist (compose config + targeted pytest -k filters)
- [X] T038 Confirm out-of-scope items not implemented: application auth (FR-013), folder-prefix tool ceiling (FR-014)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup** → none
- **Phase 2 Foundational** → Setup; **blocks all stories**
- **US1 (Phase 3)** and **US2 (Phase 4)** → Foundational; both P1; can proceed in parallel after T003–T006
- **US3 (Phase 5)** → Foundational (needs T003 Settings fields); independent of US1/US2 logically
- **US4 (Phase 6)** → Foundational; independent of US1–US3
- **US5 (Phase 7)** → Foundational; pairs naturally with US1 docs but independently testable
- **Polish** → desired stories complete

### User Story Dependencies

| Story                        | Depends on     | Notes                 |
| ---------------------------- | -------------- | --------------------- |
| US1 Publish binds            | Phase 2        | MVP network posture   |
| US2 Upload limits            | Phase 2        | MVP memory safety     |
| US3 Representation + session | Phase 2 (T003) | P2                    |
| US4 Job leases               | Phase 2        | P2; Protocol + worker |
| US5 Credentials              | Phase 2        | P3; compose + docs    |

### Parallel Opportunities

- After Phase 2: US1 + US2 + US4 can run in parallel (different files)
- US3 can start once T003 lands (even before US1/US2 finish)
- Within stories: `[P]` test tasks and independent file edits in parallel

---

## Parallel Example: User Story 1

```bash
# After Phase 2:
Task: T007 compose publish bind tests
Task: T008 compose.yaml loopback 8000
Task: T009 compose.dev.yaml loopback 5432/11434
# Then:
Task: T010 skipped (no LAN overlay)
Task: T011 README / quickstart docs
```

## Parallel Example: User Story 2

```bash
Task: T012 api upload accept tests
Task: T013 archive safety unit tests
# Then sequential Protocol → archive → documents → fakes:
Task: T014 → T015 → T016 → T017
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1–2
2. US1 loopback publish
3. US2 upload pre-expansion limits
4. **STOP** — validate with compose config + upload tests
5. Then US3 → US4 → US5 → polish / `just check`

### Incremental Delivery

1. Foundation → Settings ready
2. US1 → safer default network
3. US2 → safer uploads
4. US3 → ingest/ask budgets
5. US4 → lease integrity
6. US5 → credential honesty
7. Polish → `just check` + quickstart.md

---

## Notes

- Cite `data-model.md` fields in implementing tasks rather than re-copying numeric defaults
- Do not add application authentication
- Prefer no Alembic migration for lease WHERE-clause hardening
- Commit after each story checkpoint when possible
