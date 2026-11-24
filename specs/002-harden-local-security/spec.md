# Feature Specification: Harden Local Security Posture

**Feature Branch**: `002-harden-local-security`

**Created**: 2026-03-24

**Status**: Draft

**Input**: User description: "I want to resolve these security issues" (security-audit run-1 needs-validation leads; missing authentication remains intentionally out of scope for the local-only phase)

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Local stack stays on this machine by default (Priority: P1)

As an operator running AIditor on my workstation, I start the documented local stack and expect the product HTTP surface (and any optional development ports) to be reachable only from this machine unless I deliberately choose otherwise.

**Why this priority**: Accidental LAN exposure of a full-power, unauthenticated API (and optionally the database or local model) is the largest mismatch with the stated “local only” intent.

**Independent Test**: Start the default local stack and the documented development overlay; verify published services listen on loopback only; verify a documented opt-in path exists if LAN access is ever required.

**Acceptance Scenarios**:

1. **Given** a fresh checkout following the quickstart, **When** the operator starts the default local stack, **Then** the product HTTP port is bound so that only local clients on that machine can reach it.
2. **Given** the operator starts the documented development overlay that publishes database or local-model ports, **When** those ports are published, **Then** they are bound to loopback by default (not all network interfaces).
3. **Given** the operator needs access from another host, **When** they follow the documented opt-in procedure, **Then** they can publish beyond loopback with an explicit, documented choice (not the silent default).

---

### User Story 2 - Uploads cannot blow past stated size promises (Priority: P1)

As an operator (or any client that can reach the API), when I upload files or zip archives, the system rejects oversize or over-count uploads before spending unbounded memory on buffering or decompressing them. Stated upload limits must match what the process actually does.

**Why this priority**: Documented size/count limits that apply only after full decompression allow a single request to exhaust machine memory before rejection.

**Independent Test**: Submit a zip whose compressed size is small but whose uncompressed members exceed configured per-file or total limits; confirm rejection occurs without fully materializing oversized payloads into memory as the primary path; confirm normal under-limit uploads still succeed.

**Acceptance Scenarios**:

1. **Given** configured maximum total upload size, per-file size, and file count, **When** a client sends a multipart upload that would exceed those limits before or during archive expansion, **Then** the system rejects the upload and does not accept the engagement content from that request.
2. **Given** a well-formed zip under all configured limits, **When** the client uploads it to a valid engagement folder, **Then** the upload is accepted and queued for ingest as today.
3. **Given** an archive with unsafe paths or symlink members, **When** uploaded, **Then** it continues to be rejected (existing safety behavior is preserved).

---

### User Story 3 - Ingest and ask work stay within operator-visible budgets (Priority: P2)

As an operator, after a document is accepted under upload size limits, parsing, chunking, and indexing must still respect additional representation budgets so a single capped file cannot create unbounded pages, text, or chunks. Separately, long ask sessions must not grow summarization cost without a clear ceiling.

**Why this priority**: Byte caps alone do not bound parse/index fan-out or per-ask history summarization spend on a shared local machine.

**Independent Test**: Process a fixture document at the upload size ceiling that maximizes pages or sections; confirm ingest fails closed or truncates within configured representation limits. Drive a long session past the recent-context window; confirm summarization input and session length stay within configured ceilings.

**Acceptance Scenarios**:

1. **Given** configured maxima for expanded text, page count, and/or chunk count, **When** ingest would exceed them for an accepted upload, **Then** the item fails closed with a clear failure reason (or is truncated only if the product explicitly documents truncation—default is fail closed).
2. **Given** a session with many prior turns, **When** the user asks another question, **Then** history preparation stays within a configured maximum turn budget and does not send unbounded prior answers into summarization.
3. **Given** normal short sessions and ordinary documents, **When** users upload and ask, **Then** behaviour remains successful without hitting the new ceilings.

---

### User Story 4 - Background ingest jobs respect their lease (Priority: P2)

As an operator running one or more ingest workers, when a job is claimed under a lease, only the current lease holder may mark that job complete or failed for retry. Stale or overlapping workers must not silently overwrite terminal state.

**Why this priority**: Lease reclaim without holder checks can corrupt upload status and derived indexes under concurrent workers or delayed finish.

**Independent Test**: Simulate lease expiry and reclaim by a second worker, then attempt completion from the first; only the current holder’s outcome sticks.

**Acceptance Scenarios**:

1. **Given** a processing item locked by worker A, **When** worker A completes successfully within the lease, **Then** the item reaches the successful terminal state.
2. **Given** the lease expired and worker B reclaimed the item, **When** worker A later attempts to complete or fail the same item, **Then** that stale mutation is rejected or ignored and worker B remains authoritative.
3. **Given** worker B holds the lease, **When** worker B fails the item for retry under policy, **Then** retry/failure state updates only for that holder.

---

### User Story 5 - Bootstrap credentials match local-only expectations (Priority: P3)

As an operator setting up the stack from documentation, example credentials remain suitable for a single-machine demo, but the product must not silently fall back to a well-known password when the operator forgets to configure one in a way that contradicts published guidance. Documentation must state the local-demo nature of example secrets.

**Why this priority**: Well-known passwords are acceptable only when paired with loopback-only access and clear docs; silent fallbacks increase surprise when overlays publish ports.

**Independent Test**: Follow quickstart with the example env file; confirm documented credentials work locally; confirm docs warn that example passwords are for local demo only; confirm compose does not invent a hidden default password when the operator leaves the password unset in a published-port scenario (operator must set an explicit value).

**Acceptance Scenarios**:

1. **Given** the operator copies the example environment file unchanged for local demo, **When** they start the loopback-bound stack, **Then** the stack starts successfully with the documented demo database credentials.
2. **Given** the operator removes or blanks the database password in environment configuration, **When** they attempt to start the stack, **Then** startup fails with a clear configuration error rather than silently substituting a built-in password.
3. **Given** the quickstart and security notes, **When** the operator reads them, **Then** they are told example credentials are for local demo only and must be changed before any non-loopback exposure.

---

### Edge Cases

- What happens when a zip declares a huge uncompressed size in metadata but members are actually small—does the system trust metadata, stream with running counters, or both?
- What happens when Content-Length is missing or lies about multipart body size?
- What happens when ingest hits a representation limit midway through a multi-page document—partial index cleanup vs fail the item?
- What happens when session turn count is at the maximum and the user asks again—reject, drop oldest, or summarize more aggressively within the cap?
- What happens when a single worker process restarts and reuses a new worker identity against rows it previously locked?
- What happens if the operator already has a customized compose override that republishes on all interfaces—docs must not claim absolute network safety beyond repository defaults.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Default documented local deployment MUST publish the product HTTP port on loopback only.
- **FR-002**: Documented development overlays that publish database or local-model ports MUST bind those host ports to loopback by default.
- **FR-003**: The product MUST provide a documented, explicit opt-in for publishing beyond loopback; that path MUST NOT be the default quickstart.
- **FR-004**: Upload acceptance MUST enforce configured maximum total size, per-file size, and file count before accepting oversized decompressed or buffered content as successfully planned uploads.
- **FR-005**: Archive expansion MUST NOT fully materialize member payloads that exceed configured per-file or total limits as the normal acceptance path.
- **FR-006**: Existing archive path-safety and symlink rejection behaviour MUST be preserved.
- **FR-007**: Ingest MUST enforce configured representation ceilings (at least: maximum expanded text size, maximum page count for paged formats, and maximum chunk count per document). Exceeding a ceiling MUST fail the ingest item with a clear reason unless truncation is explicitly product-documented (default: fail closed).
- **FR-008**: Ask session history preparation MUST enforce a configured maximum number of stored turns considered for context/summarization so summarization input cannot grow without bound.
- **FR-009**: Background ingest job completion and retry-failure transitions MUST succeed only for the worker that currently holds the active lease on that job.
- **FR-010**: Stale completion or failure attempts after lease reclaim MUST NOT overwrite the current holder’s authority for that job.
- **FR-011**: Stack startup MUST require an explicitly configured database password in environment configuration (example file may still show a local-demo value); silent built-in password substitution when the variable is unset MUST NOT occur.
- **FR-012**: Operator documentation MUST state that example database credentials are for local demo only and that non-loopback exposure requires changing them and accepting the risk.
- **FR-013**: Adding application-level authentication or multi-user authorization is OUT OF SCOPE for this feature (local-only phase remains intentionally unauthenticated).
- **FR-014**: Soft ask folder scoping consistency for agent tools (rejected audit leads) is OUT OF SCOPE unless later prioritized as a separate UX hardening feature.
- **FR-015**: Offline automated tests MUST cover upload limit-before-expansion behaviour, representation-limit fail-closed ingest fixtures, session history ceiling behaviour, and lease-holder job transitions, without requiring paid external APIs.

### Key Entities

- **Upload limit policy**: Operator-configured ceilings for file count, total bytes, and per-file bytes applied at acceptance time.
- **Representation limit policy**: Operator-configured ceilings for expanded text, pages, and chunks applied during ingest.
- **Session history budget**: Operator-configured maximum turns retained/considered for ask context and summarization.
- **Ingest job lease**: Binding between a processing upload item and the worker currently authorized to finish it.
- **Publish binding posture**: Whether a published port is loopback-only (default) or explicitly opened beyond the machine.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: With default quickstart settings, a second machine on the same LAN cannot complete a successful product HTTP request to the published port without an explicit opt-in publish change (verified by operator or automated bind-address check in CI/docs tests).
- **SC-002**: 100% of offline upload tests that exceed configured size/count limits are rejected without treating the oversized expanded payload as an accepted planned upload.
- **SC-003**: 100% of offline ingest fixtures that exceed representation ceilings fail closed with a recorded failure reason (no silent partial success).
- **SC-004**: Ask flows with sessions longer than the configured history budget never send more than that budget’s worth of prior turns into summarization preparation (verified by offline tests with a fake model).
- **SC-005**: In a two-worker lease race fixture, stale completion after reclaim fails 100% of the time; only the current lease holder’s terminal transition applies.
- **SC-006**: Starting the stack with the database password environment variable unset fails in 100% of documented start paths (no silent default password).
- **SC-007**: Quickstart and deployment docs mention loopback-default publish and local-demo credentials in the primary setup path (reviewable checklist).

## Assumptions

- The product remains intentionally unauthenticated for this local-only phase; network reachability is the primary control.
- Operators primarily use the repository’s Docker Compose quickstart (and optional development overlay), not an unimplemented cloud path.
- Example credentials such as a shared local demo password remain acceptable **only** when paired with loopback-bound ports and clear documentation.
- Fail-closed is preferred over silent truncation when ingest representation limits are exceeded.
- Existing engagement isolation, zip path safety, agent tool allowlisting, and API-key secret handling are already adequate and are not rewritten by this feature except where required to enforce the new limits and lease rules.
- Audit leads about folder-prefix tool soft-scoping and SQL LIKE wildcards inside an engagement are not treated as security defects for this feature.
- Source of truth for the defect list is the security-audit run-1 needs-validation set under the operator’s “no auth is fine for now” constraint.
