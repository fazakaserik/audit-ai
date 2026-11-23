# Data Model: Audit Assistant

Source of truth for domain types in `backend.domain` (one module per model, e.g. `backend.domain.engagement`, `backend.domain.upload`) and the Postgres schema owned by `backend.infrastructure.postgres`. HTTP DTOs live in `backend.application.api.contracts.v1`, not in domain.

## Conventions

- All domain models: pydantic `ConfigDict(frozen=True, strict=True, extra="forbid")`.
- Ids: `NewType` over `uuid.UUID` (UUIDv4), except `EngagementId` (validated slug).
- Timestamps: timezone-aware UTC (`AwareDatetime`). Mutable records have `created_at` + `updated_at`; immutable records have `created_at` only.
- Embeddings, `locked_until`, and `next_attempt_at` are **adapter storage fields**, not domain attributes.

## Value types

| Type                                                                                    | Definition                               | Validation                                                                                                                                                                     |
| --------------------------------------------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `EngagementId`                                                                          | `Annotated[str, ...]`                    | `^[a-z0-9][a-z0-9-]{1,62}$`                                                                                                                                                    |
| `FolderPath`                                                                            | relative POSIX path                      | no `..`, absolute, backslash, control chars, empty segments; may be `""` (root)                                                                                                |
| `DocumentPath`                                                                          | relative POSIX path ending in a filename | same as FolderPath; must have a non-empty final segment with an allowed extension                                                                                              |
| `UploadId`, `UploadItemId`, `DocumentId`, `ChunkId`, `SessionId`, `TurnId`, `RequestId` | `NewType("…", UUID)`                     | UUIDv4                                                                                                                                                                         |
| `ContentType`                                                                           | enum                                     | `markdown`, `text`, `pdf`, `docx`, `xlsx`, `pptx`, `html`, `csv`                                                                                                              |
| `Question`                                                                              | model                                    | `text` 1–2000 chars after strip; optional `folder_scope`, `auditor_role`, `topic` (each ≤ 200 chars)                                                                           |
| `Citation`                                                                              | model                                    | `chunk_id`, `document_id`, `document_path`, `page: int \| None` (≥1), `heading_path: tuple[str, ...]`, `snippet` (≤ 500 chars), `score: float` in `[0, 1]`, `marker: int` (≥1) |
| `SuggestedClientQuestion`                                                               | model                                    | `question` 1–500 chars, `rationale` 1–500 chars                                                                                                                                |
| `Answer`                                                                                | discriminated union on `status`          | see below                                                                                                                                                                      |

### Answer union

```text
Answered
  status: Literal["answered"]
  text: str                    # contains inline [n] markers
  citations: list[Citation]    # ordered by marker; len >= 1

InsufficientEvidence
  status: Literal["insufficient_evidence"]
  reason: Literal["no_relevant_chunks", "model_judged_insufficient"]
  partial_citations: list[Citation]          # may be empty
  suggested_client_questions: list[SuggestedClientQuestion]  # 1..3
```

## Entities

### Engagement

| Field                       | Type            | Notes       |
| --------------------------- | --------------- | ----------- |
| `id`                        | `EngagementId`  | primary key |
| `name`                      | `str`           | 1–200 chars |
| `created_at` / `updated_at` | `AwareDatetime` |             |

**Relationships**: owns Uploads, Documents, Sessions.

**Validation**: creating a duplicate `id` → `conflict`.

### Upload

| Field                       | Type                    | Notes                                             |
| --------------------------- | ----------------------- | ------------------------------------------------- |
| `id`                        | `UploadId`              |                                                   |
| `engagement_id`             | `EngagementId`          | FK                                                |
| `target_folder`             | `FolderPath`            |                                                   |
| `status`                    | enum                    | `queued` → `processing` → `completed` \| `failed` |
| `completed_at`              | `AwareDatetime \| None` | set on terminal status                            |
| `created_at` / `updated_at` |                         |                                                   |

**State transitions**

```text
queued --(worker picks first item)--> processing --(all items terminal)--> completed
                                   \--(unrecoverable upload-level error)--> failed
```

`completed` is used even when some items failed (per-item outcomes carry the detail). `failed` is reserved for upload-level failure (for example storage write failure after accept should not happen; mainly defensive).

### UploadItem

| Field                       | Type           | Notes                                                                             |
| --------------------------- | -------------- | --------------------------------------------------------------------------------- |
| `id`                        | `UploadItemId` | also the job id                                                                   |
| `upload_id`                 | `UploadId`     |                                                                                   |
| `document_path`             | `DocumentPath` | final path under the engagement                                                   |
| `status`                    | enum           | `pending` → `processing` → `indexed` \| `skipped` \| `not_searchable` \| `failed` |
| `reason`                    | `str \| None`  | required for skipped / not_searchable / failed                                    |
| `attempts`                  | `int`          | 0..max (default max 3)                                                            |
| `processing_started_at`     | `AwareDatetime \| None` | set when a worker claims the item                                        |
| `processing_finished_at`    | `AwareDatetime \| None` | set when the item reaches a terminal status                              |
| `embedding_prompt_tokens`   | `int \| None`  | provider-reported embedding prompt tokens (indexed items)                         |
| `embedding_total_tokens`    | `int \| None`  | provider-reported embedding total tokens (indexed items)                          |
| `chunk_count`               | `int \| None`  | chunks written for indexed items                                                  |
| `chunk_token_sum`           | `int \| None`  | sum of chunker `token_count` for indexed items                                    |
| `created_at` / `updated_at` |                |                                                                                   |

API responses also expose derived `processing_duration_ms` when both timestamps are set.

**Adapter-only job fields** (Postgres `upload_items` / jobs): `locked_until`, `locked_by`, `next_attempt_at`, `raw_storage_key`.

### Document

| Field                       | Type           | Notes                              |
| --------------------------- | -------------- | ---------------------------------- |
| `id`                        | `DocumentId`   |                                    |
| `engagement_id`             | `EngagementId` |                                    |
| `path`                      | `DocumentPath` | unique per engagement              |
| `content_type`              | `ContentType`  |                                    |
| `size_bytes`                | `int`          | ≥ 0                                |
| `sha256`                    | `str`          | 64 hex chars                       |
| `version`                   | `int`          | starts at 1; increments on replace |
| `searchable`                | `bool`         | false when stored but not indexed  |
| `created_at` / `updated_at` |                |                                    |

**Replace semantics**: on re-upload to the same path, `version` increments; old chunks for prior versions are deleted in the same transaction as the new chunks are inserted (atomic swap). Retrieval always filters `chunk.document_version = document.version`.

### Chunk

| Field              | Type              | Notes                                               |
| ------------------ | ----------------- | --------------------------------------------------- |
| `id`               | `ChunkId`         |                                                     |
| `document_id`      | `DocumentId`      |                                                     |
| `document_version` | `int`             |                                                     |
| `ordinal`          | `int`             | 0-based order within the document version           |
| `page`             | `int \| None`     | PDF page (≥1); None for md/txt unless derived       |
| `heading_path`     | `tuple[str, ...]` | from Markdown headings / PDF outline when available |
| `text`             | `str`             | non-empty                                           |
| `token_count`      | `int`             | ≥ 1                                                 |
| `created_at`       |                   |                                                     |

**Adapter-only**: `embedding vector`, `embedding_model text`, `search_vector tsvector` (generated/stored).

### Session

| Field                       | Type           | Notes                                   |
| --------------------------- | -------------- | --------------------------------------- |
| `id`                        | `SessionId`    |                                         |
| `engagement_id`             | `EngagementId` |                                         |
| `title`                     | `str`          | derived from first question (truncated) |
| `turn_count`                | `int`          | ≥ 0                                     |
| `created_at` / `updated_at` |                | `updated_at` = last activity            |

### Turn

| Field                 | Type        | Notes                                                                   |
| --------------------- | ----------- | ----------------------------------------------------------------------- |
| `id`                  | `TurnId`    |                                                                         |
| `session_id`          | `SessionId` |                                                                         |
| `ordinal`             | `int`       | 0-based within session                                                  |
| `question`            | `Question`  | as asked (relational columns on `session_turns`)                        |
| `standalone_question` | `str`       | search/agent wording (equals `question.text` when unchanged)            |
| `answer`              | `Answer`    | status/text on `session_turns`; citations & suggestions in child tables |
| `created_at`          |             |                                                                         |

## Error codes (`ErrorCode` enum)

Stable machine-readable codes for Problem Details `code` field. Never rename or reuse.

| Code                     | Typical HTTP | When                                                 |
| ------------------------ | ------------ | ---------------------------------------------------- |
| `validation_error`       | 422          | invalid body/path/query                              |
| `not_found`              | 404          | unknown engagement, path, upload, session            |
| `conflict`               | 409          | duplicate engagement id                              |
| `payload_too_large`      | 413          | size/count limits                                    |
| `unsafe_upload`          | 400          | path traversal, corrupt zip                          |
| `model_timeout`          | 504          | model call exceeded budget                           |
| `model_unavailable`      | 502          | provider error / bad structured output after retries |
| `dependency_unavailable` | 503          | Postgres (or model for readiness) unreachable        |
| `internal_error`         | 500          | unexpected                                           |

## SQL sketch (Postgres + pgvector)

```text
engagements(id PK, name, created_at, updated_at)
uploads(id PK, engagement_id FK, target_folder, status, completed_at, created_at, updated_at)
upload_items(id PK, upload_id FK, document_path, status, reason, attempts,
             locked_until, locked_by, next_attempt_at, raw_storage_key, created_at, updated_at)
documents(id PK, engagement_id FK, path, content_type, size_bytes, sha256, version,
          searchable, created_at, updated_at, UNIQUE(engagement_id, path))
chunks(id PK, document_id FK, document_version, ordinal, page, heading_path text[],
         text, token_count, embedding vector, embedding_model, search_vector tsvector,
         created_at)
sessions(id PK, engagement_id FK, title, turn_count, created_at, updated_at)
session_turns(id PK, session_id FK, ordinal,
              question_text, question_folder_scope, question_auditor_role, question_topic,
              standalone_question, answer_status, answer_text, insufficient_reason,
              thinking_text, thinking_seconds,
              usage_prompt_tokens, usage_completion_tokens, usage_total_tokens,
              created_at, UNIQUE(session_id, ordinal))
turn_citations(id PK, turn_id FK, kind, marker, chunk_id, document_id, document_path,
               page, heading_path text[], snippet, score, UNIQUE(turn_id, kind, marker))
turn_suggested_questions(id PK, turn_id FK, ordinal, question, rationale,
                         UNIQUE(turn_id, ordinal))
```

**Indexes**

- `documents (engagement_id, path)` unique
- `chunks` partial HNSW per embedding model on `embedding::vector(N)`
- `chunks` GIN on `search_vector`
- `chunks (document_id, document_version)`
- `upload_items (status, next_attempt_at)` for job claiming
- `sessions (engagement_id, updated_at DESC)`

**Engagement isolation**: every repository query that returns documents, chunks, uploads, or sessions MUST include `engagement_id = :engagement_id` (or join through a parent that does). Vector and FTS queries filter `engagement_id` and optional `path LIKE :folder_prefix || '%'`.

## Mapping to API contracts

Internal entities ↔ `backend.application.api.contracts.v1` response models via explicit functions in `backend/api/contracts/v1/mapping.py`. Contract models never subclass entity models.
