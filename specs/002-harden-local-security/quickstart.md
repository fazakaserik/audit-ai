# Quickstart validation: Harden Local Security Posture

Prove the feature after implementation. Prefer offline tests for logic; use Compose checks for publish posture.

## Prerequisites

- Repo root with `.venv` via `uv sync`
- Docker (for Compose bind checks only)
- Copied `deployment/docker-compose/.env` from `.env.example` (must include explicit `POSTGRES_PASSWORD`)

## 1. Offline quality gate

```bash
just check
```

Expected: pass, including new offline tests for upload pre-expansion limits, representation fail-closed fixtures, session history ceiling, and lease-holder transitions (see FR-015).

## 2. Upload limit-before-expansion (automated)

```bash
uv run python -m pytest services/backend/tests -k "upload and (limit or zip or oversized)" -q
```

Expected: oversize / zip-bomb style fixtures rejected with `payload_too_large` (or equivalent assertion) without treating expanded oversized payloads as accepted planned uploads. Safe under-limit zip still accepted.

## 3. Representation limits + session budget (automated)

```bash
uv run python -m pytest services/backend/tests -k "representation or ingest_max or session_max_turns or history" -q
```

Expected: ingest fixtures over page/char/chunk ceilings fail closed with a clear reason; ask with long session only feeds newest `session_max_turns` into history preparation (fake ChatModel).

## 4. Lease holder (automated)

```bash
uv run python -m pytest services/backend/tests -k "lease or job_queue or stale" -q
```

Expected: stale `complete` / `fail_for_retry` after reclaim does not change terminal state; current holder succeeds. Use `db` marker tests if the suite places the race under testcontainers.

## 5. Compose loopback publish (operator / local Docker)

```bash
# From deployment/docker-compose with valid .env
docker compose -f compose.yaml config
```

Expected: `load-balancer` ports show `127.0.0.1:8000:8000` (or equivalent published address `127.0.0.1`).

```bash
docker compose -f compose.yaml -f compose.dev.yaml config
```

Expected: Postgres/Ollama host ports bound to `127.0.0.1`.

Unset password check:

```bash
# With POSTGRES_PASSWORD removed from env / .env — compose up should fail fast
```

Expected: no silent `audit` substitution.

## 6. Docs checklist

Confirm README and `.env.example` state:

- [ ] Loopback-default publish
- [ ] Example credentials are local-demo only

## References

- [env-and-compose.md](./contracts/env-and-compose.md)
- [error-codes.md](./contracts/error-codes.md)
- [data-model.md](./data-model.md)
- [spec.md](./spec.md)
