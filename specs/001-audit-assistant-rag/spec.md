# Feature Specification: Audit Assistant (Document-Grounded Q&A for Auditors)

**Feature Branch**: `001-audit-assistant-rag`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Auditor assistant: the client company uploads its documents in an organized folder structure (single files or a zip archive placed at a chosen folder path), the auditor can list and read the documents, and asks questions that are answered only from the uploaded documents with references to the exact source. When the documents do not contain enough information, the assistant says so and suggests concrete questions the auditor should ask the client, tailored to the auditor's role and topic of interest. Backend service only, no frontend. Must run with a paid cloud model and with a free, fully local model, switchable by configuration."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Ask a grounded question and get a cited answer (Priority: P1)

An auditor working on a client engagement asks a natural-language question (for example "What is the payment term in the Contoso supply agreement?"). The system answers using only the documents of that engagement and lists, for every answer, which documents and which chunks (with page where applicable) the answer is based on.

**Why this priority**: This is the core value: it replaces a round trip of "auditor asks client, client searches, client replies" with an instant, verifiable answer. Without it, nothing else matters.

**Independent Test**: Load the bundled sample engagement, ask a question whose answer is stated in one sample document, and verify that the answer is correct and that the cited source points to that document and chunk.

**Acceptance Scenarios**:

1. **Given** an engagement with indexed documents that contain the answer, **When** the auditor asks a question, **Then** the response has status "answered", contains an answer, and contains at least one citation identifying the document path, the chunk text, and the page (for paginated documents).
2. **Given** an engagement with indexed documents, **When** the auditor restricts the question to a folder (for example "contracts/"), **Then** only documents inside that folder are used and cited.
3. **Given** two engagements with different documents, **When** the auditor asks a question in engagement A, **Then** no document from engagement B is ever used or cited.
4. **Given** a question whose answer would require knowledge not present in the documents (for example general accounting standards), **When** the auditor asks it, **Then** the system does not answer from general knowledge and instead reports insufficient evidence (see User Story 2).

---

### User Story 2 - Insufficient evidence produces suggested client questions (Priority: P1)

When the engagement documents do not contain enough information to answer, the system explicitly says so instead of guessing, and drafts 1 to 3 concrete questions or document requests the auditor can send to the client. The suggestions take into account the auditor's role (for example "IT auditor", "financial auditor") and topic of interest (for example "revenue recognition") when provided, and any partially relevant chunks that were found.

**Why this priority**: Refusing to hallucinate is mandatory for audit work, and turning a refusal into an actionable client request is the differentiating business value of the product. It also defines the required "no relevant result" behavior.

**Independent Test**: Against the sample engagement, ask a question that no sample document covers; verify status "insufficient_evidence", no fabricated answer, and at least one suggested client question related to the asked topic.

**Acceptance Scenarios**:

1. **Given** an engagement where no document is relevant to the question, **When** the auditor asks it, **Then** the response has status "insufficient_evidence", contains no factual answer, contains no citations, and contains 1 to 3 suggested client questions.
2. **Given** partially relevant documents (for example a policy that mentions a topic but not the asked detail), **When** the auditor asks, **Then** the response has status "insufficient_evidence", cites the partially relevant chunks, and the suggested questions ask specifically for the missing detail.
3. **Given** the auditor provides a role and a topic, **When** evidence is insufficient, **Then** the suggested questions are phrased for that role and topic.
4. **Given** an engagement that has no documents at all, **When** the auditor asks a question, **Then** the response has status "insufficient_evidence" and the suggestions ask the client to provide relevant documents.

---

### User Story 3 - Client uploads documents into an organized folder structure (Priority: P2)

A client representative uploads documents for an engagement to a chosen folder path (for example "finance/2025/bank-statements"). They can upload one or more individual files, or a single zip archive whose internal folder structure is preserved under the chosen path. The upload is accepted immediately and processed in the background; the client can check the processing status of the upload at any time. Once processed, the documents become searchable for that engagement.

**Why this priority**: Required for real use, but the core Q&A can be demonstrated with the bundled sample data loaded by a command, so this is second.

**Independent Test**: Create an empty engagement, upload a zip with nested folders to a target path, poll the upload status until it is finished, then list the engagement's documents and ask a question answered by one of the uploaded files.

**Acceptance Scenarios**:

1. **Given** an existing engagement, **When** the client uploads two supported files to "contracts/2025", **Then** the upload is acknowledged immediately with an upload identifier and status "queued", before any document is processed.
2. **Given** an accepted upload, **When** the client checks its status, **Then** the status is one of "queued", "processing", "completed" or "failed"; once "completed", it reports each document with its final path and outcome.
3. **Given** an existing engagement, **When** the client uploads a zip containing "q1/invoice.pdf" and "q2/invoice.pdf" to "finance" and processing completes, **Then** documents "finance/q1/invoice.pdf" and "finance/q2/invoice.pdf" exist and are searchable.
4. **Given** a document already exists at a path, **When** a new file uploaded to the same path finishes processing, **Then** the new version replaces the old one and the old content is no longer used for answers; until then, the old version keeps answering.
5. **Given** an upload containing unsupported file types, **When** it is processed, **Then** supported files are indexed, unsupported files are reported as skipped with a reason, and nothing is silently dropped.
6. **Given** a zip archive whose entries try to escape the target folder (for example "../../secret.txt"), or an upload exceeding the limits, **When** it is submitted, **Then** it is rejected immediately with a clear error, no upload is queued, and nothing is stored.
7. **Given** processing of one file fails (for example the model provider is unavailable while preparing it for search), **When** the upload finishes, **Then** that file is reported as failed with a reason, the other files are unaffected, and the upload ends with status "completed" (with failures) rather than hanging.
8. **Given** the service restarts while an upload is queued or processing, **When** it comes back, **Then** the upload resumes and eventually reaches a final status.

---

### User Story 4 - Auditor browses and reads the documents (Priority: P2)

The auditor lists the folder structure and documents of an engagement, optionally narrowed to a folder, and retrieves the original content of any document, including any document referenced in a citation.

**Why this priority**: Citations are only trustworthy if the auditor can open the cited source. Listing also lets the auditor see what the client has and has not provided.

**Independent Test**: With the sample engagement loaded, list documents under "policies/", then fetch one listed document and compare it byte-for-byte with the original sample file.

**Acceptance Scenarios**:

1. **Given** an engagement with documents, **When** the auditor lists documents, **Then** every document is returned with its path, type, size and upload time.
2. **Given** a folder filter, **When** the auditor lists documents, **Then** only documents under that folder are returned.
3. **Given** a citation in an answer, **When** the auditor requests the cited document path, **Then** the original document is returned unchanged.
4. **Given** a path that does not exist in the engagement, **When** the auditor requests it, **Then** a "not found" error is returned.

---

### User Story 5 - Operator runs the service in cloud mode or fully local free mode (Priority: P3)

An operator (or the interview reviewer) starts the service with a single documented command, loads the sample data with a single documented command, and chooses by configuration only whether answers and search use a paid cloud model provider or a free model running locally without any paid key. A health check tells whether the service and its dependencies are ready.

**Why this priority**: Required by the assignment and essential for reproducibility, but it is an operational concern on top of the user-facing stories.

**Independent Test**: Start the service in local mode with no paid key configured, load the sample data, and complete User Story 1 and 2 scenarios end-to-end.

**Acceptance Scenarios**:

1. **Given** local mode is configured and no paid key is present, **When** the operator starts the service and loads sample data, **Then** questions are answered end-to-end, including document search.
2. **Given** cloud mode is configured with a valid key, **When** the operator switches only configuration values and reloads data, **Then** the same requests work with no code change.
3. **Given** a dependency (search store or model provider) is unavailable, **When** the operator calls the readiness check, **Then** it reports "not ready" and names the failing dependency; the liveness check still reports alive.

---

### User Story 6 - Auditor continues a conversation in a session and resumes it later (Priority: P2)

The auditor asks questions within a session tied to one engagement. Follow-up questions can refer to earlier turns ("And what is its termination clause?" after asking about the Contoso supply agreement), and the system understands what "its" refers to. Sessions are saved, so the auditor can list earlier sessions of an engagement and resume one with its full history, from any client.

**Why this priority**: Real audit questioning is a dialogue; forcing the auditor to restate context in every question wastes time. Resuming a session lets work continue across days.

**Independent Test**: Start a session on the sample engagement, ask a question about a specific contract, then ask a follow-up that uses a pronoun; verify the follow-up is answered about the same contract with citations. Then list sessions, resume the session and verify the earlier turns are returned.

**Acceptance Scenarios**:

1. **Given** an engagement, **When** the auditor asks a question without referring to a session, **Then** a new session is created for that engagement with a title derived from the question, and the response contains the session identifier so the next question can follow up in it.
2. **Given** a session with an earlier turn about a specific document, **When** the auditor asks a follow-up that refers to it implicitly, **Then** the follow-up is answered about that document, with citations, and still only from documents.
3. **Given** earlier turns in a session, **When** a follow-up is answered, **Then** facts stated in earlier answers are not reused as evidence; every factual claim is backed by a citation retrieved for the current turn.
4. **Given** several sessions on an engagement, **When** the auditor lists sessions, **Then** they are returned newest first with title, turn count, and last activity time.
5. **Given** an existing session, **When** the auditor resumes it, **Then** all turns (questions and full answers including citations and suggested client questions) are returned in order, and new questions continue the same session.
6. **Given** a session of engagement A, **When** it is used with engagement B, **Then** the request is rejected as "not found".

---

### User Story 7 - Auditor works in an interactive terminal client (Priority: P3)

The auditor uses an interactive terminal application, similar in feel to modern AI coding assistants, to pick an engagement, start or resume a session, ask questions, and read answers with clearly presented citations and suggested client questions. The same tool offers non-interactive commands to manage engagements and upload documents. It talks to the service only through its public interface.

**Why this priority**: It is not required by the assignment, but it makes the product demonstrable without an HTTP tool, and it proves the public interface is complete and usable by a real client. It builds on all other stories, so it comes last.

**Independent Test**: With the service running and sample data loaded, start the terminal client, choose the sample engagement, ask a question, see a formatted answer with citations, exit, restart the client, resume the previous session, and see the earlier turns.

**Acceptance Scenarios**:

1. **Given** the service is running, **When** the auditor starts the client without arguments, **Then** it shows an interactive prompt that lets them choose an engagement and either start a new session or resume a recent one.
2. **Given** an active session, **When** the auditor asks a question, **Then** a progress indicator is shown while waiting, and the answer is rendered with formatted text, a list of citations (document path, page, snippet), and, when evidence is insufficient, the suggested client questions.
3. **Given** the interactive prompt, **When** the auditor types a command (for example to switch engagement, start a new session, list sessions, open a cited document, or quit), **Then** it is executed without leaving the client; available commands are discoverable through completion and a help command.
4. **Given** the service is unreachable or returns an error, **When** the auditor asks a question, **Then** the client shows a readable error message (including the error code and request identifier) and stays usable.
5. **Given** the non-interactive commands, **When** an operator creates an engagement or uploads a folder or zip and asks to wait for completion, **Then** the command reports the per-file outcomes and exits with a non-zero status if any file failed.

---

### Edge Cases

- Empty, whitespace-only, or overly long question (over 2,000 characters): rejected with a validation error that names the offending field.
- Unknown engagement identifier on any operation: "not found" error, never an empty success.
- Malformed engagement identifier or folder path (absolute path, "..", backslashes, control characters, empty segments): rejected with a validation error.
- Model provider times out: a distinct "model timeout" error is returned within the configured time limit plus a small margin; no partial answer is returned.
- Model provider fails (unreachable, rate limited, invalid key, malformed output): a distinct "model unavailable" error; details of credentials are never exposed.
- Search store unavailable: a distinct "dependency unavailable" error.
- Model output cites a source that was not among the retrieved chunks: that citation is discarded; if no valid citation remains, the result is treated as insufficient evidence.
- Upload exceeds size or file-count limits, or the zip is corrupted: rejected as a whole at submission with a specific error.
- Document with no extractable text (for example a scanned image-only PDF): stored and listable, but reported in the upload status as "not searchable" with a reason.
- Status requested for an unknown upload identifier, or for an upload that belongs to another engagement: "not found".
- Two uploads to the same document path processed close together: the one submitted last wins, and the final state is never a mix of both.
- A question asked about a document whose upload is still queued: the document is not yet used; the answer may report insufficient evidence.
- Concurrent questions from several auditors on different engagements: answers never mix data between requests or engagements.
- Question asked while an upload to the same engagement is in progress: the answer uses either the old or the new version of each document consistently, never a broken mix of one document.

## Requirements _(mandatory)_

### Functional Requirements

**Engagements**

- **FR-001**: System MUST let an operator create an engagement with a human-readable identifier (for example "northwind-fy2025") and display name, and MUST reject duplicate identifiers.
- **FR-002**: System MUST let a caller list engagements and retrieve a single engagement with its document count.
- **FR-003**: Every document, search, and answer MUST be scoped to exactly one engagement; data MUST NOT be retrievable across engagements.

**Documents**

- **FR-004**: System MUST accept upload of one or more individual files to a target folder path within an engagement.
- **FR-005**: System MUST accept upload of a single zip archive to a target folder path and preserve the archive's internal folder structure beneath that path.
- **FR-006**: System MUST support at least plain text, Markdown, PDF, DOCX, XLSX, PPTX, HTML, and CSV documents; other types MUST be reported as skipped with a reason.
- **FR-007**: System MUST reject the entire upload at submission time, storing and queuing nothing, if any archive entry would resolve outside the target folder, the archive is corrupted, or configured limits (total size, file count, single file size) are exceeded.
- **FR-008**: Uploading to an existing document path MUST replace that document and its searchable content once processing completes; the replacement MUST be atomic, so answers use either the complete old version or the complete new version.
- **FR-009**: System MUST acknowledge a valid upload immediately with an upload identifier and process it in the background.
- **FR-009a**: System MUST expose the status of an upload ("queued", "processing", "completed", "failed") and, per file, the final document path and an outcome: indexed, skipped (with reason), not searchable (with reason), or failed (with reason).
- **FR-009b**: Background processing MUST survive a service restart: queued or interrupted uploads MUST be picked up again and reach a final status. Failures of individual files MUST be retried a bounded number of times and then reported, without blocking other files or uploads.
- **FR-009c**: Background processing MUST be able to run in multiple parallel workers without processing the same upload twice.
- **FR-010**: System MUST list documents of an engagement, optionally filtered by folder prefix, returning path, type, size, and upload time.
- **FR-011**: System MUST return the original, unmodified content of a document by its path.
- **FR-012**: The repository MUST include fictional sample documents and a seeding script that creates the sample engagement(s) and uploads them through the terminal client's non-interactive commands, so the service is usable without any user-supplied documents.

**Question answering**

- **FR-013**: System MUST accept a question for an engagement with optional folder scope, auditor role, and topic of interest.
- **FR-014**: System MUST answer only from chunks retrieved from the engagement's documents and MUST NOT use the model's general knowledge to supply facts.
- **FR-014a**: Chunk retrieval MUST match both by meaning and by exact terms, so that questions containing identifiers such as invoice numbers, contract ids, amounts or names find the chunks that contain those exact terms.
- **FR-015**: Every response MUST carry an explicit outcome: "answered" or "insufficient_evidence".
- **FR-016**: An "answered" response that relies on engagement documents MUST include at least one citation; each citation MUST identify the document path, the chunk text, the page number when the document is paginated, and a relevance score. Answers that make no document claims (greetings, meta chat, or non-document tool facts such as the current time) MAY omit citations.
- **FR-016a**: When document citations are required, the answer text MUST mark each claim with a numbered reference (for example "[1]") that corresponds to an entry in the citation list; references that point to no citation MUST be removed, and an answer left with no valid reference MUST be treated as insufficient evidence.
- **FR-017**: Citations MUST only reference chunks that were actually retrieved for that request.
- **FR-018**: An "insufficient_evidence" response MUST include 1 to 3 suggested client questions or document requests, MAY include citations of partially relevant chunks, and MUST NOT include a factual answer.
- **FR-019**: Suggested client questions MUST reflect the provided role and topic when given.
- **FR-020**: After the agent drafts an answer, the system MUST check whether statements that need engagement data are supported by retrieved evidence (and cited). If they are not, the system MAY send the agent back to gather more evidence or revise, up to a configured restart limit, and MUST return "insufficient_evidence" when the limit is exhausted or the draft remains ungrounded. Non-document replies (for example greetings) that make no engagement claims MAY be answered without citations.

**Sessions**

- **FR-031**: System MUST let a caller list the sessions of an engagement (newest activity first) and retrieve a session with all its turns.
- **FR-032**: Every question MUST be stored as a turn of a session, together with its complete response. A question MAY name an existing session; if it does not, a new session MUST be created. Every response (both outcomes) MUST contain the session identifier and the turn identifier.
- **FR-033**: When a question is asked within a session, the system MUST use a bounded number of recent turns (configurable, default 5) only to interpret the question (resolving references such as "it" or "that contract"); evidence for the answer MUST still come only from chunks retrieved for the current turn.
- **FR-034**: A session MUST belong to exactly one engagement and MUST NOT be usable with another engagement.
- **FR-035**: A session title MUST be derived automatically from its first question.

**Terminal client**

- **FR-036**: The project MUST include an interactive terminal client that uses only the public HTTP interface and supports: choosing an engagement, starting and resuming sessions, asking questions, rendering answers with citations and suggested client questions, and opening a cited document.
- **FR-037**: The terminal client MUST offer non-interactive commands to list and create engagements, upload files, folders or zip archives (optionally waiting for completion), check upload status, and list sessions. It MUST NOT contain test-only or sample-specific commands.

**Errors, validation, observability**

- **FR-021**: All errors MUST use one consistent response shape containing a stable machine-readable error code, a human-readable message, and the request identifier.
- **FR-022**: System MUST distinguish at least these error categories: validation error, not found, conflict (duplicate), payload too large, unsupported or unsafe upload, model timeout, model unavailable, dependency unavailable, internal error.
- **FR-023**: Every request MUST receive a request identifier (generated, or accepted from the caller), returned in the response and included in every related log entry.
- **FR-024**: System MUST log request outcome, duration, retrieval hit count, and model call duration in a structured format; logs MUST NOT contain document content or credentials.
- **FR-025**: System MUST expose a liveness check (process is up) and a readiness check (search store and model provider reachable), the latter naming any failing dependency.
- **FR-026**: System MUST provide self-describing, browsable API documentation including example requests for every operation.

**Operation modes**

- **FR-027**: System MUST support a cloud mode using a paid model provider and a local mode using a free model running on the operator's machine, for both answer generation and search embeddings.
- **FR-028**: Switching modes MUST require only configuration changes, never code changes.
- **FR-029**: Model call time limit, number of retrieved chunks, relevance threshold, maximum concurrent model calls, and upload limits MUST be configurable, with documented defaults.
- **FR-030**: Switching the embedding model MUST NOT corrupt or mix existing search data; the system MUST keep data for different embedding models separate and document that re-loading is required.

### Key Entities

- **Engagement**: One audit of one client for one period. Human-readable identifier, display name, creation and last-update time. Owns uploads, documents and sessions.
- **Upload**: One submission of files or an archive to a target folder. Engagement, target folder, status, submission and completion time, per-file outcomes. Processed in the background.
- **Document**: An uploaded file within an engagement. Engagement, folder path (unique within engagement), file name, type, size, content fingerprint, upload time, searchability status.
- **Chunk**: A searchable piece of a document's text. Document, position, page (if paginated), text.
- **Question**: An auditor's query. Engagement, text, optional folder scope, optional role, optional topic.
- **Answer**: Outcome (answered / insufficient evidence), answer text (if answered), citations, suggested client questions, session identifier, turn identifier, request identifier.
- **Citation**: Reference from an answer to a chunk. Document path, page, chunk text, relevance score.
- **Suggested Client Question**: A draft question or document request for the client, optionally linked to the topic it addresses.
- **Session**: A saved conversation of one auditor about one engagement. Identifier, engagement, title, creation time, last activity time. Owns turns.
- **Turn**: One question and its complete response within a session, in order. Question (with scope, role, topic), the interpreted standalone question, the response, timestamp.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A reviewer with only the repository and a container runtime can start the service, load sample data, and receive a cited answer in under 15 minutes in cloud mode (excluding download time in local mode).
- **SC-002**: In local mode with no paid credentials, 100% of the documented example requests complete successfully.
- **SC-003**: For a documented set of at least 6 sample questions whose answers exist in the sample documents, every answer includes a citation pointing to the document that actually contains the answer.
- **SC-004**: For a documented set of at least 3 sample questions not covered by the sample documents, 100% return "insufficient_evidence" with at least one suggested client question and no fabricated answer.
- **SC-005**: 0 occurrences of a citation or chunk from another engagement in automated isolation tests.
- **SC-006**: Every documented error category is covered by an automated test that asserts the consistent error shape, and the automated test suite runs with no network access and no paid credentials.
- **SC-007**: In cloud mode, 90% of questions on the sample engagement are answered in under 10 seconds.
- **SC-008**: Switching between cloud and local mode requires changing only configuration values (verified by the documented procedure).
- **SC-009**: For a documented set of at least 3 two-turn conversations where the second question refers to the first only implicitly, the second answer cites the same document as the first.
- **SC-010**: A session resumed after restarting both the service and the terminal client shows 100% of its earlier turns with their citations.

## Assumptions

- Target users are external auditors (asking) and client representatives (uploading), but the system has no concept of users: no accounts, no authentication, no role enforcement, and any caller can perform any operation. This limitation is documented.
- The auditor role and topic of interest are optional free-text attributes of a single question, not properties of a stored user.
- Documented next step (not built): user management for both sides (auditor team members and client contacts with their responsibilities). This would let the system turn insufficient evidence into a suggested outreach addressed to the right client contact (for example "ask the Head of Treasury for the Q4 bank confirmations"), and enforce engagement-level access control.
- No graphical or web user interface is built; interaction happens through the HTTP interface, its built-in documentation, and the interactive terminal client.
- Sessions are not tied to users (there are none); anyone with the session identifier can resume it. Session deletion and renaming are out of scope.
- Real sample documents are committed to the public repository only if publicly available; their sources and licences are recorded next to them.
- Engagements are created explicitly before documents can be uploaded; folders are implicit (they exist when a document is stored under them).
- Uploads are processed in the background and sized for small document sets (default limits: 50 MB per upload, 200 files per archive, 20 MB per file). The client checks progress by polling the upload status; push notifications (webhooks) are out of scope.
- AI-generated fictional sample documents live in a dedicated samples folder; a separate folder is reserved for real documents added by the author, which must be publicly available, non-confidential documents. The seeding script uploads them through the same background processing path (queue only; indexing continues asynchronously).
- Scanned image-only documents are not made searchable (no OCR) in this version.
- Answers are returned complete, not streamed token by token.
- Document deletion and version history are out of scope; replacing a document by uploading to the same path is supported.
- Sample data is fictional and contains no confidential information.
- The local mode requires a machine with roughly 8 GB of free memory for the default local model, with a smaller documented fallback model; initial model download needs internet access.
- The assignment's evaluation emphasizes clean structure, testability and reliability over answer quality; no answer-quality evaluation suite is built.
