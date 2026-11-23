# AIditor

Document-grounded Q&A for auditors. Upload engagement documents, ask questions, and get
cited answers — or suggested client questions when evidence is missing.

**Core deliverable:** a FastAPI + LangGraph RAG HTTP backend (citations, health, validation,
OpenAI or free local Ollama). The CLI and TUI are optional clients over the same API; they are
not required to evaluate the backend.

See [specs/001-audit-assistant-rag/](specs/001-audit-assistant-rag/) for the full specification.

## Workspace

| Path               | Package   | Role                                                                                |
| ------------------ | --------- | ----------------------------------------------------------------------------------- |
| `services/backend` | `backend` | Domain, application, infrastructure layers; HTTP API + worker; tests under `tests/` |
| `cli`              | `cli`     | `aiditor` non-interactive CLI + shared HTTP client; tests in `cli/tests/`           |
| `tui`              | `tui`     | `aiditor-tui` fullscreen Textual client; tests in `tui/tests/`                      |

Compose runs a single `backend` container (HTTP API + in-process upload worker).

### Docker Compose recipes

| Recipe                                                                                   | Files                                    | Use when                                                                                                                     |
| ---------------------------------------------------------------------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `just compose-up` / `compose-down` / `compose-restart` / `compose-clean`                 | `deployment/docker-compose/compose.yaml` | Default / production-like local deploy (API on `:8000` only)                                                                 |
| `just compose-dev-up` / `compose-dev-down` / `compose-dev-restart` / `compose-dev-clean` | `compose.yaml` + `compose.dev.yaml`      | Local development overrides (publishes Postgres `:5432`, forces `/docs`, human-readable logs; optional Ollama profile ports) |

`compose-clean` / `compose-dev-clean` also remove volumes (indexed data is wiped).

## Prerequisites

- Docker
- [uv](https://docs.astral.sh/uv/) and [just](https://github.com/casey/just)
- Python 3.13 (for host `uv sync` / CLI / seed)
- Either **host Ollama** (default) or an OpenAI API key

## Local models (Ollama) — default

On the host:

```bash
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
```

Defaults (`deployment/docker-compose/.env.example`):

- `LLM_PROVIDER=ollama` / `LLM_MODEL=qwen3.5:4b`
- `EMBEDDING_PROVIDER=ollama` / `EMBEDDING_MODEL=nomic-embed-text`
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`

Containers reach host Ollama via `host.docker.internal`.

### Hardware and limits

| Setup                        | What to expect                                                                                                                                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **NVIDIA GPU (recommended)** | `qwen3.5:4b` + `nomic-embed-text`; roughly **6–8 GB VRAM** free for comfortable use. Answers in seconds to tens of seconds.                                                                                         |
| **CPU-only**                 | Same models work; expect **minutes** per ask and high RAM use (plan on **16 GB+** system RAM). Prefer a smaller chat model if the machine struggles (e.g. `qwen2.5:3b`) and keep `nomic-embed-text` for embeddings. |
| **Quality**                  | Local mode is slower and less consistent than cloud; still exercises the full RAG path with no paid API key.                                                                                                        |
| **Timeouts**                 | Default `MODEL_TIMEOUT_SECONDS=120`. Raise it on CPU-only hosts if asks time out.                                                                                                                                   |

Optional in-compose Ollama (GPU via NVIDIA Container Toolkit):  
`docker compose -f deployment/docker-compose/compose.yaml --profile local up -d` — prefer host Ollama for day-to-day GPU use.

## OpenAI mode

In `deployment/docker-compose/.env`:

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-...
```

## Run (HTTP-first)

```bash
cp deployment/docker-compose/.env.example deployment/docker-compose/.env
uv sync
just compose-up   # postgres + backend via compose.yaml; schema migrates on API startup
just seed         # creates engagement northwind-fy2025 and indexes sample docs
```

For day-to-day coding against published DB ports and readable logs, use `just compose-dev-up` instead.

API base URL: `http://localhost:8000`  
Interactive docs (enabled by default): [http://localhost:8000/docs](http://localhost:8000/docs)

### Health

```bash
curl -s http://localhost:8000/health/live
curl -s http://localhost:8000/health/ready
```

Live returns `{"status":"ok"}`. Ready includes `postgres` and `embeddings` checks.

### Ask (after `just seed`)

```bash
curl -s -X POST http://localhost:8000/api/v1/engagements/northwind-fy2025/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What are Contoso payment terms?\"}"
```

Expect `kind: "answered"` with numbered `citations` (e.g. `contracts/contoso-msa.md`).

Insufficient-evidence example:

```bash
curl -s -X POST http://localhost:8000/api/v1/engagements/northwind-fy2025/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What is the SOC 2 Type II opinion date for Contoso?\"}"
```

More sample prompts: [docs/samples/ai-generated/northwind-fy2025/README.md](docs/samples/ai-generated/northwind-fy2025/README.md).  
End-to-end scenarios: [specs/001-audit-assistant-rag/quickstart.md](specs/001-audit-assistant-rag/quickstart.md).

### Optional clients

```bash
aiditor-tui                # fullscreen interactive UI
aiditor engagements list   # non-interactive CLI
```

To author a new DB migration after changing SQLAlchemy models: `just migration "describe change"`.

## Quality gate

```bash
just check   # ruff + basedpyright + import-linter + offline pytest (no paid APIs)
```

Integration smoke against a live Ollama (optional): `just test-integration` with `RUN_INTEGRATION=1`.

## Architecture

```text
upload / seed  →  job queue + worker  →  parse → chunk → embed → pgvector
                                              ↓
ask HTTP  →  LangGraph (tools / retrieve → grade → generate → finalize)  →  cited answer
```

- **`backend.domain`** — frozen pydantic feature models
- **`backend.application`** — Protocols (`llm`, `parsing`, `repositories`, `storage`), services, RAG, HTTP API (controllers), worker entrypoints
- **`backend.infrastructure`** — Postgres/pgvector, OpenAI, Ollama, local FS, parsing
- **`cli` / `tui`** — HTTP clients only (same contracts as `/docs`)

Provider adapters are selected with `LLM_PROVIDER` / `EMBEDDING_PROVIDER`; application logic does not change.

## Limitations / next steps

- No authentication or user management
- Ask flow is a LangGraph `StateGraph` (tool loop → grade → generate → finalize); a minimal retrieve→generate graph would also satisfy the brief
- Chunk sizes not corpus-tuned; OCR out of scope
- Default compose runs API + upload worker in one process (`RUN_WORKER_IN_API=true`)
- Cloud mapping: [deployment/cloud/README.md](deployment/cloud/README.md)
