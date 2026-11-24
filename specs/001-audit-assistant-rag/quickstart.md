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
# Or set LLM_MODEL=openai/gpt-6-luna and LLM_API_KEY=...

just compose-up          # migrate → 2× api + 2× upload-processor + load-balancer + postgres
# just compose-dev-up    # optional: compose.yaml + compose.dev.yaml (DB port, readable logs)
```

Equivalent without just:

```bash
docker compose -f deployment/docker-compose/compose.yaml up -d --build
```

Host traffic hits `load-balancer` on `127.0.0.1:8000` (Caddy → `api`). See [002-harden-local-security/quickstart.md](../002-harden-local-security/quickstart.md) for local security posture checks.

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

Uses `scripts/seed_samples.py` → HTTP create engagements + queue folder uploads (processing continues in the background).
Seeds `northwind-fy2025`, `fabrikam-sox-fy2025`, and `adventureworks-itgc-fy2025` (see [docs/samples/ai-generated/README.md](../../docs/samples/ai-generated/README.md)).

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

More prompts: [docs/samples/ai-generated/README.md](../../docs/samples/ai-generated/README.md).

## 4. Optional: TUI / CLI

```bash
uv run aiditor-tui
# non-interactive: uv run aiditor engagements list
```

### Scenario E — upload via CLI

```bash
uv run aiditor upload docs/samples/ai-generated/northwind-fy2025/finance --engagement northwind-fy2025 --folder finance --wait
```
