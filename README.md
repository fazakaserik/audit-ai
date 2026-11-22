# Audit Assistant

Document-grounded Q&A for auditors. Upload engagement documents, ask questions, and get
cited answers — or suggested client questions when evidence is missing.

See [specs/001-audit-assistant-rag/](specs/001-audit-assistant-rag/) for the full specification.

## Workspace

| Path               | Package   | Role                                                                                  |
| ------------------ | --------- | ------------------------------------------------------------------------------------- |
| `packages/domain`  | `domain`  | Domain models; tests in `packages/domain/tests/`                                      |
| `services/backend` | `backend` | HTTP API, use cases, adapters, worker, migrations; tests in `services/backend/tests/` |
| `cli`              | `cli`     | `audit-ai` terminal client; tests in `cli/tests/`                                     |

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
audit-ai     # interactive REPL
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

- **domain** — frozen pydantic feature models
- **backend** — FastAPI, ports/adapters (Postgres/pgvector, OpenAI, Ollama), RAG ask graph, async upload worker
- **cli** — HTTP-only client using `backend.api.contracts.v1`

## Limitations / next steps

- No authentication or user management
- Ask graph is an explicit node runner (LangGraph `StateGraph` optional where native wheels allow)
- Chunk sizes not corpus-tuned; OCR out of scope
- Cloud mapping: `deployment/cloud/README.md`
