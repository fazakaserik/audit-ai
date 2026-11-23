# TUI Contract: `aiditor-tui`

Package: `tui/` (import name `tui`). Fullscreen Textual client. Speaks only HTTP via `cli.client.AuditApiClient` using `backend.application.api.contracts.v1` models. Same env vars as the CLI (`AUDIT_API_BASE_URL`, `AUDIT_API_TIMEOUT_SECONDS`).

## Entry points

| Invocation       | Behaviour                          |
| ---------------- | ---------------------------------- |
| `aiditor-tui`    | Launch the fullscreen interactive UI |
| `python -m tui`  | Same                               |

## Screen stack

Sticky **BrandHeader** (full wordmark on pickers; compact title on chat) and **StatusBar** (engagement · session · token counts) on every screen.

1. **Connecting** — retry `/health/live` with backoff; on failure show error and allow quit.
2. **Engagements** — `OptionList` of engagements; Enter selects.
3. **Sessions** — Start new session, or resume a recent session.
4. **Chat** — `RichLog` transcript + input; streamed ask; slash commands.

### Navigation

| Action | Behaviour |
| ------ | --------- |
| Esc / `/sessions` from Chat | Back to Sessions (list refreshes) |
| Esc / Ctrl+E / `/engagement` from Sessions or Chat | Engagements (clears current session) |
| Enter on session / “Start new” | Chat (resume replays turns into the log) |
| q / `/quit` | Exit |

### Slash commands (Chat)

| Command | Action |
| ------- | ------ |
| `/engagement` | Switch engagement (clears session) |
| `/new` | Drop `session_id` so the next question starts a new session |
| `/sessions` | Return to the session list |
| `/resume [id]` | Resume by id, or return to session list if omitted |
| `/documents [folder]` | Modal document browser |
| `/uploads [id]` | Modal upload list or one upload’s details |
| `/upload <path> <folder>` | Upload to the active engagement under `<folder>` |
| `/open <n>` | Show citation `[n]` from the last answer |
| `/help` | List commands |
| `/quit` | Exit |

### Rendering

- Progress stages, tool calls, and thinking stream into the chat log.
- Answer body as Markdown (Rich via `RichLog`).
- Citations as a numbered footnote panel matching `[n]` markers.
- Insufficient evidence: decline line plus numbered client questions.
- Errors: Problem Details fields; the TUI stays open.
