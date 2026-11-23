# Quickstart: Validate AIditor end-to-end

Prerequisites: Docker, `uv`, `just`, and **host Ollama** (GPU recommended; CPU works but slow) or an OpenAI API key. See the root [README.md](../../README.md) for hardware notes.

## 0. Pull local models

```bash
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
```

## 1. Start infrastructure and API

```bash
cp deployment/docker-compose/.env.example deployment/docker-compose/.env
# Defaults already point at host Ollama + qwen3.5:4b
# Or set LLM_PROVIDER=openai and OPENAI_API_KEY=...

just compose-up          # production-like: compose.yaml only (schema upgrades on API startup)
# just compose-dev-up    # optional: compose.yaml + compose.dev.yaml (DB port, /docs, readable logs)
```

Equivalent without just:

```bash
docker compose -f deployment/docker-compose/compose.yaml up -d --build
```

Check:

```bash
curl -s http://localhost:8000/health/live
curl -s http://localhost:8000/health/ready
```

Expected: live `{"status":"ok"}`; ready includes `postgres` and `embeddings` checks.

Interactive OpenAPI (default `ENABLE_API_DOCS=true`): http://localhost:8000/docs

## 2. Seed sample engagement

```bash
just seed
```

Uses `scripts/seed_samples.py` → HTTP create engagement + upload folders with wait.
Engagement id: `northwind-fy2025`.

## 3. Ask over HTTP (primary demo path)

Grounded answer:

```bash
curl -s -X POST http://localhost:8000/api/v1/engagements/northwind-fy2025/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What are Contoso payment terms?\"}"
```

Expect `kind: "answered"` with a citation to `contracts/contoso-msa.md`.

Folder-scoped ask:

```bash
curl -s -X POST http://localhost:8000/api/v1/engagements/northwind-fy2025/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What is the domestic meal limit?\", \"folder_prefix\": \"policies\"}"
```

Insufficient evidence:

```bash
curl -s -X POST http://localhost:8000/api/v1/engagements/northwind-fy2025/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What is the SOC 2 Type II opinion date for Contoso?\"}"
```

Expect `kind: "insufficient_evidence"` plus suggested client questions.

Follow-up in a session: pass `session_id` from the previous response into the next ask body.

More prompts: [docs/samples/ai-generated/northwind-fy2025/README.md](../../docs/samples/ai-generated/northwind-fy2025/README.md).

## 4. Optional: TUI / CLI

```bash
uv run aiditor-tui
# non-interactive: uv run aiditor engagements list
```

### Scenario E — upload via CLI

```bash
uv run aiditor upload docs/samples/ai-generated/northwind-fy2025/finance --engagement northwind-fy2025 --folder finance --wait
```
