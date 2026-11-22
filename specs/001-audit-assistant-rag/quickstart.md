# Quickstart: Validate Audit Assistant end-to-end

Prerequisites: Docker, `uv`, `just`, and either an OpenAI API key **or** Ollama (host install recommended on Windows/macOS).

## 1. Start infrastructure and API

```bash
cp deployment/docker-compose/.env.example deployment/docker-compose/.env
# Edit: set LLM_PROVIDER=openai and OPENAI_API_KEY=...
#    or LLM_PROVIDER=ollama and OLLAMA_BASE_URL=http://host.docker.internal:11434

just up          # api + worker + postgres (and ollama if profile local)
just migrate
```

Underlying commands (also in README):

```bash
docker compose -f deployment/docker-compose/docker-compose.yml up -d
uv run alembic -c packages/core/alembic.ini upgrade head
```

Check:

```bash
curl -s http://localhost:8000/health/live
curl -s http://localhost:8000/health/ready
```

Expected: live `{"status":"ok"}`; ready `status: ready` with postgres (and model) checks `ok: true`.

## 2. Seed sample engagement

Sample docs: `docs/samples/ai-generated/northwind-fy2025/`.

```bash
just seed
```

Underlying: `uv run python scripts/seed_samples.py` which calls:

```bash
uv run audit-ai engagements create --id northwind-fy2025 --name "Northwind FY2025"
uv run audit-ai upload docs/samples/ai-generated/northwind-fy2025 --engagement northwind-fy2025 --folder "" --wait
```

Expected: upload reaches `status: completed`; at least one item `indexed`.

## 3. Scenario A — Cited answer (P1)

```bash
curl -s -X POST http://localhost:8000/api/v1/engagements/northwind-fy2025/ask \
  -H "content-type: application/json" \
  -d "{\"question\":\"What is the payment term in the Contoso supply agreement?\"}"
```

Expected:

- `status: "answered"`
- `answer` contains at least one `[n]` marker
- `citations` non-empty; `document_path` under `contracts/`
- `session_id` and `turn_id` present

## 4. Scenario B — Follow-up in the same session (P2)

Reuse `session_id` from Scenario A:

```bash
curl -s -X POST http://localhost:8000/api/v1/engagements/northwind-fy2025/ask \
  -H "content-type: application/json" \
  -d "{\"question\":\"And what is its termination clause?\",\"session_id\":\"<session_id>\"}"
```

Expected: answered about the same Contoso agreement; citations still from retrieved passages only.

## 5. Scenario C — Insufficient evidence (P1)

```bash
curl -s -X POST http://localhost:8000/api/v1/engagements/northwind-fy2025/ask \
  -H "content-type: application/json" \
  -d "{\"question\":\"What is the client's crypto wallet private key?\",\"auditor_role\":\"financial auditor\",\"topic\":\"treasury\"}"
```

Expected:

- `status: "insufficient_evidence"`
- `suggested_client_questions` length 1–3
- no fabricated factual answer field

## 6. Scenario D — Interactive CLI

```bash
uv run audit-ai
# select northwind-fy2025 → ask a question → /sessions → /quit → audit-ai again → /resume <id>
```

Expected: formatted answer with citation footnotes; resumed session shows earlier turns.

## 7. Scenario E — Offline quality gate

```bash
just check
```

Expected: ruff, basedpyright, import-linter, and offline pytest all green (no network, no paid key, no Docker).

## 8. Optional — local Ollama mode

```bash
# Host Ollama with models pulled: qwen2.5:7b (or :3b) and nomic-embed-text
# In .env: LLM_PROVIDER=ollama EMBEDDING_PROVIDER=ollama OLLAMA_BASE_URL=http://host.docker.internal:11434
just up
just seed   # re-seed after embedding model change
# Repeat scenarios A and C
```

## Contract references

- HTTP: [contracts/openapi.yaml](./contracts/openapi.yaml)
- CLI: [contracts/cli.md](./contracts/cli.md)
- Entities: [data-model.md](./data-model.md)
