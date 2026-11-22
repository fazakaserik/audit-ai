<!--
Sync Impact Report
- Version change: 1.0.0 -> 1.1.0
- Modified principles: none renamed
- Added principles:
  - VI. Virtual Environment Isolation
- Added sections: none
- Removed sections: none
- Follow-up TODOs: none
-->

# Audit Assistant Constitution

## Core Principles

### I. Strict Type Safety

- All Python code MUST pass basedpyright in `strict` mode with zero errors and zero warnings.
- Explicit `Any` (annotations, `cast(Any, ...)`, untyped `**kwargs: Any`) MUST NOT appear outside
  `core.adapters`. Inside adapters, `Any` MUST be confined to the boundary with a vendor
  SDK and converted to project types before leaving the adapter.
- Suppression comments (`# pyright: ignore[...]`, `# type: ignore`) MUST name the specific rule
  and carry a reason on the same line. Blanket suppressions and file-level disables are forbidden.
- Domain models MUST be pydantic models configured with `frozen=True`, `strict=True` and
  `extra="forbid"`. Every identifier kind MUST have its own type (`NewType` over `UUID`, or a
  validated `Annotated` type for slugs and paths); raw `str`/`UUID` MUST NOT be used for ids
  in signatures.
- Every `match` or `if` chain over a union or enum MUST end with `assert_never` so that adding a
  variant is a type error until every branch handles it.
- Public functions and methods MUST have complete parameter and return annotations; unions MUST
  be modelled as discriminated unions where the variants carry different data.

Rationale: type safety is an explicit quality goal of this project. A type checker that
blocks the build is the cheapest reviewer, and it keeps refactors safe across five packages.

### II. Enforced Layering

- Dependency rules MUST be declared as import-linter contracts and MUST pass in CI:
  - `domain` imports nothing from the project; its only third-party dependency is pydantic.
  - `core.application` imports only `domain` (and the standard library).
  - Vendor SDKs (`openai`, `ollama`, `sqlalchemy`, `pgvector`, `asyncpg`, `pypdf`, `tenacity`)
    are imported only in `core.adapters`.
  - `api` and `worker` MAY import `core` and `domain` and MUST NOT
    import each other.
  - `cli` imports only `domain` and communicates with the system over HTTP.
- All models shared between packages MUST be defined once, in `domain`. Public API
  contracts (`contracts/v1`) MUST be separate classes from internal entities, with explicit
  mapping functions.
- External services MUST be reached through ports (`Protocol` classes in
  `core.application`) and wired in a single composition root. Switching providers MUST
  require configuration changes only.

Rationale: the assignment grades separation of concerns and replaceable integrations.
Machine-checked contracts make the architecture provable instead of claimed.

### III. Tested Behaviour, Offline by Default

- Every behaviour change MUST ship with automated tests in the same change. Bug fixes MUST
  include a test that fails without the fix.
- The default test command MUST run offline: no network, no paid services, no Docker. It uses
  in-memory fakes that implement the same ports as the real adapters.
- Tests needing real infrastructure MUST be opt-in via markers: `db` (Postgres with pgvector,
  started by testcontainers) and `integration` (real Ollama or OpenAI).
- Required paths MUST be covered: successful answer with citations, invalid input, no
  relevant passages, model timeout, model provider error, unsafe upload, cross-engagement
  isolation, and every documented error code.
- Fakes MUST live in shared test support code, not be redefined per test file.

Rationale: reviewers must be able to clone and run the tests in seconds without credentials.
Fakes that honour the ports keep the tests honest about the real integration points.

### IV. Consistent Errors and Safe Observability

- Every error response MUST be RFC 9457 Problem Details (`application/problem+json`) with a
  stable machine-readable `code` from a single enumerated list in `domain`, the
  `request_id`, and field-level `errors[]` for validation failures. Error codes MUST NOT be
  renamed or reused once released.
- Domain and application code MUST raise typed exceptions; mapping to HTTP status codes and
  Problem Details MUST happen in exactly one place in `api`.
- Logs MUST be structured JSON (structlog) carrying `request_id`, and `upload_id`/`job_id` for
  background work.
- Logs, error responses and traces MUST NOT contain document content, passage text, prompts,
  model outputs, or secrets. Documents are referenced by id and path only. Secrets MUST be held
  as `SecretStr` and never formatted into strings.
- Unexpected exceptions MUST return a generic `internal_error` problem without stack traces or
  internal details.

Rationale: audit documents are confidential client data. Predictable error contracts let
clients such as the CLI handle failures precisely.

### V. Simplicity Over Breadth

- A small, fully working, reproducible solution takes priority over additional features. A
  feature MUST NOT be started while a previously started P1 or P2 story is not working end to end.
- New dependencies, services or abstractions MUST be justified in the feature's `research.md`,
  stating why the simpler alternative is insufficient. Deviations from a principle go in the
  plan's Complexity Tracking table.
- No speculative extension points: a port exists only when there are at least two
  implementations (real adapter plus fake, or two providers).
- Out-of-scope ideas (authentication, user management, frontend, OCR, streaming) MUST be
  documented as next steps rather than partially implemented.

Rationale: the assignment explicitly rewards a smaller, end-to-end working solution over a
feature-rich system that is hard to run.

### VI. Virtual Environment Isolation

- All Python tooling for this repository MUST run inside the project virtual environment at
  `.venv`. Agents and developers MUST create or refresh it with `uv sync` (or an equivalent
  `uv`-managed venv rooted at `.venv`) before installing or running project packages.
- Dependencies MUST be installed only into `.venv` (via `uv sync`, `uv add`, or `uv run`).
  Installing packages into the global/system Python, a user site-packages tree outside
  `.venv`, or any other interpreter is forbidden.
- Commands that execute project code, tests, linters, type checkers, or scripts MUST go through
  `uv run ...` or an activated `.venv`, never via a bare global `python`/`pip`/`pytest` that
  targets the system interpreter.
- Documentation and `just` recipes MUST NOT instruct readers to `pip install` or otherwise
  mutate the global Python environment.

Rationale: a single locked workspace keeps every machine and agent on the same interpreter and
dependency set. Global installs pollute the host and break reproducibility.

## Product and Security Constraints

- Answers MUST be derived only from passages retrieved from the engagement's own documents.
  The model's general knowledge MUST NOT supply facts, and every claim MUST be traceable to a
  citation of a retrieved passage.
- Every read, search and answer MUST be scoped to exactly one engagement. Engagement scoping MUST
  be enforced in the data access layer, not only in request handling, and covered by tests.
- Untrusted input (uploaded archives, paths, questions) MUST be validated at the boundary: path
  traversal rejected, size and count limits enforced, and only allowed file types processed.
- The full system MUST run without any paid credential (local model mode), and switching between
  cloud and local mode MUST NOT require code changes.
- Configuration MUST be validated at startup and fail fast with a clear message. The repository
  MUST contain only secret-free configuration examples.
- Stack baseline: Python 3.13, a uv workspace with a single committed `uv.lock`, FastAPI,
  LangGraph, PostgreSQL with pgvector, Docker and docker compose. Changing the baseline is a
  constitution amendment.

## Development Workflow and Quality Gates

- `just check` is the single quality gate and MUST pass before any change is considered done. It
  runs ruff (lint and format check), basedpyright strict, import-linter, and the offline test
  suite. CI MUST run the same gate.
- Every `just` recipe MUST be a thin wrapper around `uv run ...` or `docker compose ...`, and the
  README MUST document the underlying commands. Recipes that need Python MUST assume `.venv`
  exists (created by `uv sync`) and MUST NOT fall back to global Python.
- Database schema changes MUST go through Alembic migrations; schemas MUST NOT be created at
  application startup.
- Code MUST match the surrounding style. Comments explain constraints the code cannot express,
  never what the next line does.
- Each feature follows the Spec Kit flow (specify, plan, tasks, implement). The plan MUST pass
  the Constitution Check before implementation starts.

## Governance

- This constitution supersedes conflicting conventions, plans and tasks. A plan or task that
  violates a principle MUST either be changed or record the justified exception in the plan's
  Complexity Tracking table.
- Amendments are made through `/speckit-constitution`, with a Sync Impact Report, and are
  versioned semantically: MAJOR for removing or redefining a principle, MINOR for adding a
  principle or materially expanding guidance, PATCH for clarifications.
- Compliance is checked at three points: the Constitution Check in every plan, `just check` on
  every change, and a final review against the principles before submission.
- Runtime development guidance lives in the root `README.md` and the feature's `research.md`.

**Version**: 1.1.0 | **Ratified**: 2026-11-22 | **Last Amended**: 2026-11-22
