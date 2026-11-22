# Quickstart: Validate Audit Assistant end-to-end

Prerequisites: Docker, `uv`, `just`, and **host Ollama with GPU** (recommended) or an OpenAI API key.

## 0. Pull local models (GPU)

```bash
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
```

## 1. Start infrastructure and API

```bash
cp deployment/docker-compose/.env.example deployment/docker-compose/.env
# Defaults already point at host Ollama + qwen3.5:4b
# Or set LLM_PROVIDER=openai and OPENAI_API_KEY=...

just up          # backend + postgres (schema upgrades on API startup)
```

```bash
docker compose -f deployment/docker-compose/docker-compose.yml up -d
```

Check:

```bash
curl -s http://localhost:8000/health/live
curl -s http://localhost:8000/health/ready
```

Expected: live `{"status":"ok"}`; ready includes `postgres` and `embeddings` checks.

## 2. Seed sample engagement

```bash
just seed
```

Uses `scripts/seed_samples.py` → HTTP create engagement + upload folders with wait.

## 3. Ask via CLI

```bash
uv run audit-ai
# or: uv run audit-ai engagements list
```

### Scenario A — grounded answer

Ask: _What are Contoso payment terms?_  
Expect `answered` with citation to `contracts/contoso-msa.md`.

### Scenario B — folder scope

Ask with folder `policies`: _What is the domestic meal limit?_

### Scenario C — insufficient evidence

Ask: _What is the SOC 2 Type II opinion date for Contoso?_  
Expect `insufficient_evidence` + suggestions.

### Scenario D — follow-up session

Ask a question, then a pronoun follow-up in the same REPL session.

### Scenario E — upload

```bash
uv run audit-ai upload docs/samples/ai-generated/northwind-fy2025/finance --engagement northwind-fy2025 --folder finance --wait
```
