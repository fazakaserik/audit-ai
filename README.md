# AIditor

Document-grounded Q&A for auditors. Upload engagement documents, ask questions, and get
cited answers — or suggested client questions when evidence is missing.

See [specs/001-audit-assistant-rag/](specs/001-audit-assistant-rag/) for the full specification.

## Workspace

| Path               | Package   | Role                                                                                         |
| ------------------ | --------- | -------------------------------------------------------------------------------------------- |
| `services/backend` | `backend` | Domain, application, infrastructure layers; HTTP API + worker; tests under `tests/`          |
| `cli`              | `cli`     | `aiditor` non-interactive CLI + shared HTTP client; tests in `cli/tests/`                    |
| `tui`              | `tui`     | `aiditor-tui` fullscreen Textual client; tests in `tui/tests/`                               |

Compose runs a single `backend` container (HTTP API + in-process upload worker).

## Local GPU (Qwen3.5 4B via Ollama) — recommended

On the host (NVIDIA GPU):

```bash
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
```

Defaults (`deployment/docker-compose/.env.example`):

- `LLM_PROVIDER=ollama` / `LLM_MODEL=qwen3.5:4b`
- `EMBEDDING_MODEL=nomic-embed-text`
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`

Ollama uses the GPU when available. Containers reach host Ollama via `host.docker.internal`.

```bash
cp deployment/docker-compose/.env.example deployment/docker-compose/.env
uv sync
just up
just seed    # HTTP upload of northwind samples (API + worker must be up)
aiditor-tui  # fullscreen interactive UI
aiditor engagements list   # non-interactive / agents
```

Schema migrations apply automatically when the API starts. To author a new
migration after changing SQLAlchemy models: `just migration "describe change"`.

Optional in-compose Ollama (GPU via NVIDIA Container Toolkit):  
`docker compose --profile local up` — prefer host Ollama for day-to-day GPU use.

## OpenAI mode

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-...
```

## Quality gate

```bash
just check   # ruff + basedpyright + import-linter + offline pytest
```

Requires Python 3.13, [uv](https://docs.astral.sh/uv/), [just](https://github.com/casey/just).

## Architecture

- **`backend.domain`** — frozen pydantic feature models
- **`backend.application`** — Protocols (`llm`, `parsing`, `repositories`, `storage`), services, RAG, HTTP API (controllers), worker entrypoints
- **`backend.infrastructure`** — Postgres/pgvector, OpenAI, Ollama, local FS, parsing
- **`cli`** — HTTP-only Typer client + shared `cli.client` using `backend.domain` + `backend.application.api.contracts.v1`
- **`tui`** — Textual fullscreen UI over the same HTTP client

## Limitations / next steps

- No authentication or user management
- Ask flow is a LangGraph `StateGraph` (tool loop → grade → generate → finalize).
- Chunk sizes not corpus-tuned; OCR out of scope
- Cloud mapping: `deployment/cloud/README.md`
