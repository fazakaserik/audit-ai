# Data Model: Harden Local Security Posture

This feature mostly extends **configuration policies** and **job lease transition rules**. No new user-facing entities. Schema migration is not required if `upload_items.locked_by` / `locked_until` already exist (they do in `001`).

## Configuration entities (Settings / env)

### UploadLimitPolicy

| Field                   | Meaning                                                       | Default (plan) | Validation |
| ----------------------- | ------------------------------------------------------------- | -------------- | ---------- |
| `upload_max_bytes`      | Max total accepted upload bytes (sum of member/file payloads) | 50 MiB         | ≥ 1        |
| `upload_max_file_bytes` | Max single file / zip member bytes                            | 20 MiB         | ≥ 1        |
| `upload_max_files`      | Max files after expansion                                     | 200            | ≥ 1        |

**Rules**:

- Applied to raw multipart parts before accepting unbounded buffers.
- Applied to zip members using `ZipInfo.file_size` before `read`, and again on actual `len(payload)` after read.
- Violations → reject upload (HTTP `413` / `payload_too_large`); nothing queued.

### RepresentationLimitPolicy

| Field                       | Meaning                                           | Default (plan) | Validation |
| --------------------------- | ------------------------------------------------- | -------------- | ---------- |
| `ingest_max_expanded_chars` | Max characters of parsed text across the document | 2_000_000      | ≥ 1_000    |
| `ingest_max_pages`          | Max pages for paged formats (PDF)                 | 500            | ≥ 1        |
| `ingest_max_chunks`         | Max chunks before embed/upsert                    | 5_000          | ≥ 1        |

**Rules**:

- Checked during ingest worker processing after upload acceptance.
- Exceeding any ceiling → fail closed: item terminal `FAILED` (or retry policy exhausted path) with clear `reason`; no successful partial index for that item.

### SessionHistoryBudget

| Field                   | Meaning                                         | Default (plan) | Validation                            |
| ----------------------- | ----------------------------------------------- | -------------- | ------------------------------------- |
| `session_context_turns` | Recent turns kept verbatim (existing)           | 5              | 1–50                                  |
| `session_max_turns`     | Max turns considered for ask context prep (new) | 100            | ≥ `session_context_turns`, ≤ e.g. 500 |

**Rules**:

- Ask path loads newest `session_max_turns` only for `prepare_session_context`.
- If `len(turns) > session_context_turns`, summarization input is the older slice within that newest window only.
- Stored turns beyond the window may remain in the database; they are out of ask context until product adds pruning (out of scope).

### PublishBindingPosture

Not a DB entity — deployment configuration:

| Mode          | Host publish                                             | How selected                        |
| ------------- | -------------------------------------------------------- | ----------------------------------- |
| Local default | `127.0.0.1` on product HTTP (and on dev DB/Ollama ports) | `compose.yaml` / `compose.dev.yaml` |

Broader host publish is out of product defaults; operators edit Compose themselves if needed.

## Ingest job lease

### UploadItem (existing)

Relevant fields: `id`, `upload_id`, `status`, `locked_by`, `locked_until`, `attempts`, `reason`, …

### State transitions (hardened)

```text
PENDING  --claim(worker_id)--> PROCESSING (locked_by=worker_id, locked_until=now+lease)
PROCESSING --complete(worker_id)--> INDEXED|FAILED terminal  [only if locked_by matches]
PROCESSING --fail_for_retry(worker_id)--> PENDING|FAILED     [only if locked_by matches]
PROCESSING --lease expired--> reclaimable by claim_next
```

**Rules**:

- `complete(item_id, worker_id, …)` updates only rows where `id = item_id AND locked_by = worker_id AND status = PROCESSING`.
- `fail_for_retry(item_id, worker_id, …)` same predicate.
- Zero rows updated → stale lease; worker must not treat as success.
- `claim_next` behaviour (SKIP LOCKED + expired lease reclaim) unchanged in intent; reclaim assigns new `locked_by`.

## Relationships

```text
UploadLimitPolicy --enforces--> Upload acceptance
RepresentationLimitPolicy --enforces--> process_upload_item / parse / chunk / index
SessionHistoryBudget --enforces--> AskService + prepare_session_context
Ingest job lease --binds--> upload_items row ↔ worker_id
PublishBindingPosture --controls--> host network exposure of API/DB/Ollama
```

## Validation summary

| Requirement    | Entity / rule                                                   |
| -------------- | --------------------------------------------------------------- |
| FR-004, FR-005 | UploadLimitPolicy pre-expand + zip metadata                     |
| FR-007         | RepresentationLimitPolicy fail-closed                           |
| FR-008         | SessionHistoryBudget `session_max_turns`                        |
| FR-009, FR-010 | Lease-matched complete/fail                                     |
| FR-001–003     | PublishBindingPosture                                           |
| FR-011         | Env must supply `POSTGRES_PASSWORD` / `DATABASE_URL` explicitly |
