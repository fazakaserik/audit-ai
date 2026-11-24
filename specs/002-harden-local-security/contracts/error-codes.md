# Contract: Error codes and failure surfaces

Aligned with `backend.domain.errors.ErrorCode` and RFC 9457 Problem Details.

## HTTP (upload / sync)

| Situation                                                                        | HTTP | `code`              | Notes                                          |
| -------------------------------------------------------------------------------- | ---- | ------------------- | ---------------------------------------------- |
| Multipart part or zip member exceeds size/count limits (including pre-expansion) | 413  | `payload_too_large` | Same code as today; enforcement timing changes |
| Unsafe zip path / symlink                                                        | 400  | `unsafe_upload`     | Unchanged                                      |
| Corrupt zip                                                                      | 400  | `validation_error`  | Unchanged                                      |

No new OpenAPI routes. OpenAPI descriptions for upload MAY note that limits apply before decompression.

## Async ingest (upload item `reason`)

| Situation                                   | Item status                       | `reason` (human-readable, no document body)                               |
| ------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------- |
| Expanded text / pages / chunks over ceiling | `FAILED` (or retry then `FAILED`) | e.g. `representation_limit_exceeded: pages` / `chunks` / `expanded_chars` |
| Stale lease on complete/fail                | No status change                  | Worker logs stale lease; item remains with current holder                 |

Optional: add `ErrorCode.REPRESENTATION_LIMIT_EXCEEDED = "representation_limit_exceeded"` if any synchronous path returns Problem Details for the same condition; otherwise keep as worker `reason` only to minimize API surface.

## Ask / session

Exceeding `session_max_turns` does **not** return an error; ask uses newest-N turns (see data-model). No new error code.

## Worker / job queue (internal)

| Situation                                                     | Behaviour                                                                                      |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `complete` / `fail_for_retry` with wrong or stale `worker_id` | Update affects 0 rows; raise domain error or return false — caller must not mark local success |

Not exposed on the public OpenAPI surface.
