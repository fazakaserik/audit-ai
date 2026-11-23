# Research and Decisions: Audit Assistant

Decisions agreed during specification, for use by `/speckit-plan`.

## Language and type safety

- **Decision**: Python 3.13, basedpyright in strict mode as the CI type gate, ruff for lint and format, uv with `uv.lock`.
- **Rationale**: Strict typing is a stated quality goal. basedpyright is stricter and faster than mypy and catches more problems in untyped third-party code.
- **Alternatives**: mypy strict (better pydantic plugin, weaker inference); running both (more friction for little extra signal).

## Monorepo layout

- **Decision**: One uv workspace at the repository root with two members:
  - `services/backend` (import name `backend`): DDD layers `backend.domain`, `backend.application` (ports/use cases/RAG/HTTP API/upload processor), `backend.infrastructure` (Postgres, LLM providers, FS, parsing), plus composition root and Alembic migrations. One Dockerfile; compose runs `api`, `upload-processor` (`audit-worker`), and one-shot `migrate` from that image, plus `load-balancer` (Caddy).
  - `cli/` (import name `cli`): non-interactive Typer client + shared HTTP library (`cli.client`); imports `backend.domain` and `backend.application.api.contracts`.
  - `tui/` (import name `tui`): fullscreen Textual client (`aiditor-tui`); HTTP only via `cli.client`.
- **Rationale**: Auditor tooling does not need independently scaled API/worker packages. A single backend is simpler to run and demo while still allowing an optional second worker process from the same image. One `uv.lock` keeps versions consistent.
- **Import rules (enforced with import-linter)**: `backend.domain` imports nothing from the rest of the project. Application use cases/RAG/ports must not import infrastructure or bootstrap; vendors stay in `backend.infrastructure`. `cli` may import `backend.domain` and `backend.application.api.contracts` only.
- **Internal models vs contracts**: domain entities live as one module per model under `backend.domain` (folders only when models are tightly coupled). HTTP DTOs and mappers live in `backend.application.api.contracts.v1`.

## Domain model (draft for data-model.md)

- **Style**: Every model is a pydantic model with `ConfigDict(frozen=True, strict=True, extra="forbid")`. Value objects are `Annotated` types with validators. Ids are `NewType`s over `uuid.UUID` (UUIDv4), so different id kinds cannot be swapped by accident. Mutable records carry `created_at` and `updated_at`, immutable records only `created_at`. All timestamps are timezone-aware UTC (`AwareDatetime`).
- **Value types**: `EngagementId` (slug `^[a-z0-9][a-z0-9-]{1,62}$`); `FolderPath` and `DocumentPath` (relative POSIX paths that reject `..`, absolute paths, backslashes, control characters and empty segments); `ContentType` (`markdown | text | pdf | docx | xlsx | pptx | html | csv`); `Question` (`text`, `folder_scope`, `auditor_role`, `topic`); `Citation` (`chunk_id`, `document_id`, `document_path`, `page`, `heading_path`, `snippet`, `score`); `SuggestedClientQuestion` (`question`, `rationale`); `Answer = Answered | InsufficientEvidence`, where `InsufficientEvidence.reason` is `no_relevant_chunks | model_judged_insufficient`.
- **Entities**:

| Model        | Fields                                                                                                                             | Timestamps       |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| `Engagement` | `id: EngagementId`, `name`                                                                                                         | created, updated |
| `Upload`     | `id`, `engagement_id`, `target_folder`, `status` (queued, processing, completed, failed), `completed_at`                           | created, updated |
| `UploadItem` | `id`, `upload_id`, `document_path`, `status` (pending, processing, indexed, skipped, not_searchable, failed), `reason`, `attempts` | created, updated |
| `Document`   | `id`, `engagement_id`, `path`, `content_type`, `size_bytes`, `sha256`, `version`, `searchable`                                     | created, updated |
| `Chunk`      | `id`, `document_id`, `document_version`, `ordinal`, `page`, `heading_path`, `text`, `token_count`                                  | created          |
| `Session`    | `id`, `engagement_id`, `title`, `turn_count` (`updated_at` = last activity)                                                        | created, updated |
| `Turn`       | `id`, `session_id`, `ordinal`, `question`, `standalone_question`, `answer`                                                         | created          |

- **Not in the domain**: embeddings and job lease fields (`locked_until`, `next_attempt_at`) belong to the pgvector and job-queue adapters.
- **Contracts (`contracts/v1`)**: `CreateEngagementRequest`, `AskRequest`, `EngagementResponse`, `DocumentResponse`, `UploadAcceptedResponse`, `UploadResponse`, `AskResponse` (the union plus `session_id`, `turn_id`, `request_id`), `SessionSummaryResponse`, `SessionDetailResponse`, `HealthResponse`, `ProblemDetails`, and a generic `Page[T]` (`items`, `total`, `limit`, `offset`).
- **Pagination**: offset-based, `?limit=&offset=` (default limit 50, maximum 200), responses include `total`.

## Local model hosting

- **Decision**: Two supported ways to run Ollama:
  - The `ollama` service under the `local` compose profile, plus a one-shot model-pull service. Fully containerized and CPU by default, with documented GPU settings for WSL2 and NVIDIA.
  - An Ollama installed on the host, reached by setting `OLLAMA_BASE_URL` (for example `http://host.docker.internal:11434`). It uses the GPU natively and is recommended on Windows and macOS.

## Developer workflow

- **Decision**: A `justfile` at the repository root with recipes such as `just check` (lint, format check, type check, import contracts, tests), `just test`, `just test-integration`, `just migrate`, `just compose-up` / `just compose-dev-up`, and `just seed` (runs `scripts/seed_samples.py`). Compose runs `migrate` (one-shot), `api`, `upload-processor`, and `load-balancer` (Caddy) from `deployment/docker-compose/`.
- **Note**: `just` must be installed (`winget install Casey.Just`, `brew install just`, `cargo install just`). Every recipe is a thin wrapper around `uv run ...` or `docker compose ...`, and the README also lists the underlying commands.

## HTTP API conventions

- **Decision**: Business routes live under `/api/v1/...`. Health checks stay unversioned at `/health/live` and `/health/ready`, so infrastructure probes never change with API versions. Errors use RFC 9457 Problem Details (`application/problem+json`) extended with a stable `code`, the `request_id`, and `errors[]` for field-level validation errors.
- **Decision**: The ask response is a discriminated union on `status` (`answered` | `insufficient_evidence`), so that invalid combinations cannot be represented.
- **Decision**: `POST /api/v1/engagements/{engagement_id}/ask` takes an optional `session_id`. Without it, a new session is created. Both response variants always carry `session_id`, `turn_id` and `request_id`, so any answer can be followed up. The CLI carries the `session_id` forward automatically. Sessions are read-only resources: `GET .../sessions` and `GET .../sessions/{session_id}`.

## Sessions and follow-up questions

- **Decision**: Sessions are a server-side resource persisted in Postgres (`sessions` and `session_turns` tables), stored through a `SessionRepository` port. A turn stores the original question, the rewritten standalone question and the full typed response.
- **Decision**: The ask agent receives a bounded number of recent prior user questions (default 5, configurable) only for reference resolution. Evidence comes exclusively from tool results in the current turn (`search_relevant_chunks`, optional browse tools). Earlier answers are never passed in as evidence.
- **Rationale**: Follow-up questions work without weakening grounding, and the rest of the graph stays unchanged.
- **Alternative considered**: the LangGraph Postgres checkpointer as session storage. Rejected because it stores graph-internal state rather than a typed, queryable transcript, and the API needs to list sessions and return turns as part of its own contract.

## Terminal clients (`cli/` + `tui/`)

- **Decision**: Two uv workspace members share one HTTP library:
  - `cli/` (command `aiditor`): Typer subcommands only; Rich for script-friendly stdout. Agents and seed scripts use this surface. `aiditor` with no args prints help (does not launch a TUI).
  - `tui/` (command `aiditor-tui`): Textual fullscreen app with sticky brand header, status bar (engagement · session · tokens), and a screen stack (Engagements → Sessions → Chat). Slash commands and Esc/Ctrl+E navigation. Depends on `cli.client` only (not `cli.commands` / `cli.main`).
- **Behaviour**: Interactive humans run `aiditor-tui`. Automations run `aiditor engagements|upload|uploads|sessions|documents …`. Both talk to the service only over HTTP (httpx).
- **Rationale**: Keeps the automation CLI lean and predictable while giving humans a Claude Code–like TUI; one typed HTTP client avoids duplicated API logic.

## Sample data and seeding

- **Decision**: AI-generated fictional sample documents live in `docs/samples/ai-generated/<engagement-id>/...`. `docs/samples/real/` is committed and reserved for real documents added by the author, which must be publicly available and non-confidential, with a README listing each document's source and licence. `scripts/seed_samples.py` (run with `uv run`) is the seeding script that creates the engagement(s) and queues every folder upload via the same HTTP path as the CLI (without waiting for indexing). A `just seed` recipe runs it as part of setting up the dev environment.
- **Rationale**: The CLI stays a clean product tool, and seeding goes through the same real path (HTTP, validation, queue, worker, indexing), which makes it a smoke test too.

## Testing strategy

- **Decision**: pytest suites colocated next to packages (`services/backend/tests/unit/domain`, `services/backend/tests`, `cli/tests`), in three groups:
  - `unit` (default, no I/O): domain, ingestion and graph tests with in-memory fakes, and API tests through an in-process httpx client with a fake container.
  - `db`: repository, hybrid search and job-claiming tests against a real Postgres with pgvector, started by testcontainers. Needs Docker but no paid services.
  - `integration`: end-to-end tests against real Ollama or OpenAI. Opt-in only.
- **Rationale**: The default suite stays fast and offline. The SQL-heavy parts (job claiming with `SKIP LOCKED`, hybrid ranking, atomic document swap) are verified against real Postgres behaviour instead of mocks.

## Chunking

- **Decision**: Structure-aware chunking. Split on Markdown headings and PDF page boundaries first, then into token windows of about 500 tokens with about 15% overlap. Each chunk keeps its heading path and page number as citation metadata.
- **Rationale**: Chunks that follow document structure cite cleanly ("contracts/contoso.pdf, page 3, section 4.2 Payment terms") and do not merge unrelated sections.
- **Next step**: Chunk size, overlap and the splitting rules are configuration parameters. They should be tested with different values on a labelled question set and tuned, which is out of scope for this version.

## Ask orchestration

- **Decision**: Ask flow is a LangGraph `StateGraph` under `backend.application.agents.research_agent` (`agent` ⇄ `tools` → `grade_evidence` → `generate` → `finalize`), with tool turns via `complete_tool_turn` / shared `backend.application.tools` and a structured `AnswerGenerationResult` + citation filter. Entry: `agents.research_agent.graph.run_graph`. Retrieval is `backend.application.rag.retrieve_relevant_chunks`; ingestion is `backend.application.rag.worker`. The `search_relevant_chunks` tool calls retrieve.
- **Rationale**: Keeps the ask agent separate from RAG (ingest + retrieve). LangGraph owns control flow; project-owned `ChatModel` ports stay free of LangChain model wrappers.

## Grounding and citations

- **Decision**: Retrieved chunks are shown to the model numbered `[1]..[n]`. The model must return the answer text with inline markers after each claim, together with the list of marker numbers it used. A post-processing step removes markers that do not match a retrieved chunk, renumbers the rest so they run consecutively, and builds `citations` in marker order. An answer with no valid marker left becomes `InsufficientEvidence(reason="model_judged_insufficient")`. The CLI renders the markers as footnotes.
- **Rationale**: Every claim can be traced to a chunk, and checking the markers is deterministic, with no extra model call.

## Resilience

- **Decision**: tenacity inside the model and embedding adapters. Exponential backoff with jitter, at most 3 attempts, retrying only typed transient errors (timeouts, rate limits, 5xx errors), and always bounded by the overall per-request time limit. The openai SDK's own retries are disabled (`max_retries=0`) so retry behaviour lives in one place. An `asyncio.Semaphore` caps concurrent model calls per process.

## Configuration

- **Decision**: pydantic-settings with flat environment variable names for providers, models, DB/storage, RAG/ask knobs (`MODEL_TIMEOUT_SECONDS`, `RETRIEVAL_TOP_K`, `RELEVANCE_THRESHOLD`, `MAX_CONCURRENT_MODEL_CALLS`, `AGENT_MAX_TOOL_ROUNDS`, `AGENT_READ_MAX_CHARS`), upload limits, API bind/docs, and logging. Ask always includes the full session history (no turn window); history compression is a documented next step when prompts exceed the provider context. Schema upgrades and upload processing are separate compose services (`migrate`, `upload-processor`), not Settings toggles. Settings stay typed (enums and `SecretStr`) and are validated at startup; for example, `LLM_PROVIDER=openai` without `OPENAI_API_KEY` fails fast. A secret-free `.env.example` documents every variable.

## Model and embedding integration

- **Decision**: Use the official `openai` SDK for cloud mode and the official `ollama` SDK for local mode, as two separate adapters behind project-owned ports (`ChatModel`, `Embedder`). LangChain packages are used only as far as LangGraph requires.
- **Rationale**: Both SDKs are fully typed. Two real adapters show that providers can be swapped, and no vendor types leak into the application or the graph.
- **Alternatives**: one `openai` adapter pointed at Ollama's OpenAI-compatible endpoint (fewer dependencies, but swapping providers becomes just a URL change); LangChain model wrappers (only partially typed).

## Metadata and vector storage

- **Decision**: PostgreSQL with the pgvector extension stores engagement and document metadata, chunks and embeddings. It runs as a container in docker compose.
- **Rationale**: One datastore. Replacing a document (deleting old chunks and inserting new ones) is a single transaction, so an answer never sees half of a re-uploaded document. Filtering by engagement and folder is plain SQL. Postgres full-text search allows hybrid search later. pgvector with an HNSW index comfortably handles the expected scale (thousands of engagements with up to about 100k chunks each).
- **Alternatives**: Qdrant next to Postgres (two stores that can drift out of sync); Chroma (prototype-grade); Pinecone (SaaS, would send client data to a third party).
- **Embedding dimensions**: Different embedding models produce vectors of different lengths (for example 1536 for `text-embedding-3-small`, 768 for `nomic-embed-text`). Chunks store `embedding_model` and an untyped `vector` column. Retrieval filters on the configured model. One partial HNSW index is created per supported model, casting to that model's dimension (`CREATE INDEX ... ON chunks USING hnsw ((embedding::vector(1536))) WHERE embedding_model = 'text-embedding-3-small'`). Switching embedding models never mixes dimensions; re-seeding is required after a switch.
- **Cloud target**: Azure AI Search replaces pgvector for search in a cloud deployment (managed hybrid and semantic ranking), as a new `VectorIndex` adapter with no application change. See `deployment/cloud/README.md`.

## Database access

- **Decision**: SQLAlchemy 2.0 async (`Mapped[...]` typed models) with the asyncpg driver, Alembic migrations, and `pgvector-python` for the vector column type. ORM models stay inside the repository adapters and are mapped to the frozen pydantic domain models at the boundary.
- **Rationale**: Mature, well typed under strict checking, first-class pgvector support. Mapping at the boundary keeps the ORM out of the domain and application layers.
- **Alternatives**: psycopg 3 with handwritten SQL (most explicit, much more boilerplate); SQLModel (one class doubles as table and API schema, which blurs the layers).

## Retrieval

- **Decision**: Hybrid search in version 1. A pgvector cosine-similarity query (HNSW index) and a Postgres full-text query (`tsvector` with a GIN index, `websearch_to_tsquery`) run filtered by engagement, folder prefix and active document version. The two ranked lists are merged with reciprocal rank fusion inside the pgvector `VectorIndex` adapter.
- **Rationale**: Audit questions often contain exact identifiers (invoice numbers, contract ids, amounts) that vector search alone ranks poorly. Doing the fusion inside the adapter keeps the port simple (`search(query, scope) -> list[ScoredChunk]`) and lets Azure AI Search replace it with its native hybrid search.
- **Relevance threshold**: Applied to vector cosine similarity **before** reciprocal rank fusion. Chunks with cosine similarity below `RELEVANCE_THRESHOLD` (default `0.30`) are discarded from the vector candidate set. If the vector candidate set is empty after the threshold, the graph returns `insufficient_evidence` with `reason=no_relevant_chunks` without calling the LLM, even if full-text search returned hits. Full-text hits participate in fusion only among the chunks that also survived the vector threshold (or were in the top-k vector set before thresholding but still above threshold). Rationale: fused RRF ranks are ordinal and not comparable across queries; vector similarity is.

## Ingestion

- **Decision**: Asynchronous upload processing. The API validates the upload (size limits, a path-traversal-safe archive listing), stores the raw files, creates an `upload` row plus one job per file in Postgres, and returns `202 Accepted` with the upload id. A separate worker process claims jobs with `SELECT ... FOR UPDATE SKIP LOCKED`, then parses, chunks, embeds and atomically swaps the document's chunks. Each job has a bounded retry count and a lease timeout, so jobs from a crashed worker are picked up again. Clients poll `GET .../uploads/{upload_id}`.
- **Rationale**: Embedding calls are slow and rate limited and must not hold HTTP requests open. A Postgres job table needs no extra infrastructure, survives restarts, and allows several workers. In the cloud target it is replaced by Azure Service Bus.
- **Alternatives**: synchronous indexing (simpler, blocks requests); Celery or RQ with Redis (one more service, weaker typing); in-process background tasks (lost on restart, wrong with multiple instances).

## Logging and observability

- **Decision**: structlog with JSON output to stdout. The request id and upload or job id are bound through context variables, so every log line can be correlated.
- **Rationale**: Structured, typed and simple to configure, and context variables work across async tasks.
- **Cloud target**: logs, traces and metrics are exported to Azure Application Insights through OpenTelemetry, so incidents can be investigated end-to-end (request id to model call to worker job) with KQL queries. See `deployment/cloud/README.md`.

## Users and access control

- **Decision**: No user concept in this version.
- **Rationale**: The assignment does not value authentication or user management. Leaving them out keeps the scope small and the service runnable.
- **Next step**: User and contact management, enabling outreach suggestions addressed to a specific client contact, plus engagement-level access control (Entra ID in the cloud target).
