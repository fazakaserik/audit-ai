# Research: Harden Local Security Posture

## 1. Loopback-default Compose publish

**Decision**: Change host port mappings to `127.0.0.1:<host>:<container>` in `compose.yaml` (API/Caddy `8000`) and `compose.dev.yaml` (Postgres `5432`, Ollama `11434`). Do **not** ship a LAN publish overlay. Do **not** change in-container `uvicorn --host 0.0.0.0` (required for Caddy→api on the Docker network).

**Rationale**: Spec FR-001–003 care about _host_ reachability. Docker’s default `8000:8000` publishes on all host interfaces; `127.0.0.1:8000:8000` matches “local only” without adding auth. Operators who need broader binds edit Compose themselves.

**Alternatives considered**:

- Bind `API_HOST=127.0.0.1` inside the API container — breaks Caddy reverse-proxy on the compose network.
- Host firewall docs only — not enforceable from the repository; weaker than changing defaults.
- Ship `compose.lan.yaml` LAN overlay — declined; keeps the default stack simpler.
- Always require auth before any publish — out of scope (FR-013).

## 2. Upload limits before expansion

**Decision**: Enforce limits in two stages: (1) raw multipart: stream/read each part with a running byte counter capped by `upload_max_file_bytes` (and reject early); accumulate total against `upload_max_bytes` and file count against `upload_max_files`. (2) zip: before `ZipFile.read`, check `ZipInfo.file_size` against `upload_max_file_bytes` and running uncompressed total against `upload_max_bytes`; refuse to read members that would exceed. After successful reads, keep existing `_enforce_limits` as a defense-in-depth assertion. Preserve path/symlink checks.

**Rationale**: Current path buffers full `upload.read()` then expands then limits — matches audit fingerprint `upload.limits.post_expansion_enforcement`. Metadata `file_size` is not cryptographically trusted alone, so post-read length checks remain; the metadata gate prevents the common zip-bomb path.

**Alternatives considered**:

- Rely only on reverse-proxy `client_max_body_size` — Caddyfile has no such limit today; still need app-level zip member control.
- Stream zip to disk — more complex; in-memory with pre-checks is enough at demo scale.
- Trust only post-expansion limits — fails the spec.

## 3. Ingest representation ceilings (fail closed)

**Decision**: Add Settings: `ingest_max_expanded_chars`, `ingest_max_pages`, `ingest_max_chunks` with conservative defaults (research picks: 2_000_000 chars, 500 pages, 5_000 chunks — tunable via env). Enforce in parse/chunk/index path: PDF page loop aborts with domain error when pages exceed; MarkItDown/text output length checked; chunk list length checked before embed. Worker marks item failed via existing failure path with a clear reason string; no partial successful index for that item (delete any partial writes if already started, or check limits before upsert).

**Rationale**: Spec FR-007 fail-closed default. Byte caps do not bound page/section fan-out.

**Alternatives considered**:

- Silent truncation — rejected by spec default.
- Only limit embed batch size — leaves parse memory unbounded.
- Per-format separate policies — unnecessary complexity for v1; three global ceilings suffice.

## 4. Session history budget

**Decision**: Add `session_max_turns` (default e.g. 100, ≥ `session_context_turns`). When loading turns for ask: if stored turns exceed the budget, only the newest `session_max_turns` are considered for `prepare_session_context` (older rows remain in DB for audit trail / session GET unless product later adds pruning). Summarization therefore never sees more than `session_max_turns - session_context_turns` older turns, each still subject to existing answer length caps.

**Rationale**: Spec FR-008 / edge case “at maximum”: drop oldest from _context preparation_, do not reject the ask (better UX for local demo). Session detail API can still return full history or also cap — prefer consistent newest-N for GET list_turns used by ask; document that ask uses newest-N.

**Alternatives considered**:

- Reject ask when over budget — harsher UX.
- Persist a rolling summary row — larger schema change; defer.
- Cap only summarization prompt chars — still allows unbounded turn loops calling the model.

## 5. Job lease holder checks

**Decision**: Change `PostgresJobQueue.complete` and `fail_for_retry` to require `worker_id` and update only when `locked_by == worker_id` and status is `PROCESSING` (and optionally `locked_until` still in the future, or allow complete after expiry only by current locked_by until reclaim). Return/raise a typed “stale lease” / not-updated outcome so the worker does not treat success incorrectly. No Alembic migration if columns already exist. Wire `worker_id` from `run_worker_loop` into complete/fail calls.

**Rationale**: Audit fingerprint `backend.job-queue.unauthenticated-lifecycle-mutations`. Application-layer fix; DB credential holders remain trusted (same as today) when Postgres is loopback-only.

**Alternatives considered**:

- SKIP LOCKED only without complete guards — insufficient after lease expiry reclaim.
- DB triggers — heavier than SQLAlchemy WHERE.
- Worker HMAC secrets — overkill for local-only; out of simplicity principle.

## 6. Explicit database password (no silent `:-audit`)

**Decision**: In Compose, require `${POSTGRES_PASSWORD}` without `:-audit` default (and same for interpolated `DATABASE_URL`). Keep `POSTGRES_PASSWORD=audit` in `.env.example` so `cp .env.example .env` still works. Remove or narrow `Settings.database_url` default that embeds `audit:audit` — prefer requiring `DATABASE_URL` from env when running outside compose, or keep a localhost default only for unit tests via test fixtures overriding settings (tests already inject settings). Document local-demo credentials and loopback requirement in README + `.env.example` comments.

**Rationale**: FR-011/012 — example file may show demo value; unset must fail fast.

**Alternatives considered**:

- Generate random password on first boot — surprising for demo; needs persistence story.
- Keep `:-audit` but only when not publishing ports — Compose cannot express that condition cleanly.

## 7. Error codes

**Decision**: Reuse `payload_too_large` for upload pre-expansion rejections. Add `representation_limit_exceeded` (or map ingest failures to existing `validation_error` / worker failure reason without new HTTP code if ingest is async-only). For stale lease: no HTTP surface — worker logs + skip; if needed for tests, raise domain error `StaleJobLeaseError` without new public API. Prefer minimal new `ErrorCode` values: at most one for representation limits if sync paths can surface them (e.g. markdown download later deferred).

**Rationale**: Constitution IV — stable codes; avoid renaming. Async ingest already stores `reason` on upload items.

**Alternatives considered**: Many fine-grained codes — deferred until clients need them.
