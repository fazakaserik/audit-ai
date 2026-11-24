# Contract: Environment and Compose publish posture

## Host publish (operator-visible)

| Stack                | File(s)                                  | Host binding (required)                  |
| -------------------- | ---------------------------------------- | ---------------------------------------- |
| Default API edge     | `deployment/docker-compose/compose.yaml` | `127.0.0.1:8000:8000` on `load-balancer` |
| Dev Postgres         | `compose.yaml` + `compose.dev.yaml`      | `127.0.0.1:5432:5432`                    |
| Dev Ollama (profile) | `compose.yaml` + `compose.dev.yaml`      | `127.0.0.1:11434:11434`                  |

**Non-goals**: Changing the in-network listen address of `api` (`0.0.0.0:8000` inside the container remains valid for Caddy). There is no LAN publish overlay; operators who need broader host binding must edit Compose themselves.

## Required environment variables

| Variable            | Required at compose up?                     | Notes                                                        |
| ------------------- | ------------------------------------------- | ------------------------------------------------------------ |
| `POSTGRES_PASSWORD` | **Yes** — no Compose `${…:-audit}` fallback | `.env.example` ships `audit` for local demo                  |
| `POSTGRES_USER`     | Yes (example: `audit`)                      | Prefer no silent fallback; example file supplies value       |
| `POSTGRES_DB`       | Yes (example: `audit`)                      | Same                                                         |
| `DATABASE_URL`      | Yes for app/migrate/worker                  | Must match Postgres credentials; example file supplies value |

Unset `POSTGRES_PASSWORD` must cause Compose interpolation failure or an explicit preflight error — not a silent `audit` substitution.

## New / extended application settings (env)

| Env var                     | Purpose  | Example default |
| --------------------------- | -------- | --------------- |
| `UPLOAD_MAX_BYTES`          | Existing | `52428800`      |
| `UPLOAD_MAX_FILE_BYTES`     | Existing | `20971520`      |
| `UPLOAD_MAX_FILES`          | Existing | `200`           |
| `INGEST_MAX_EXPANDED_CHARS` | New      | `2000000`       |
| `INGEST_MAX_PAGES`          | New      | `500`           |
| `INGEST_MAX_CHUNKS`         | New      | `5000`          |
| `SESSION_CONTEXT_TURNS`     | Existing | `5`             |
| `SESSION_MAX_TURNS`         | New      | `100`           |

## Documentation contract

README / `.env.example` MUST state:

1. Default publish is loopback-only.
2. Example DB credentials are local-demo only; do not expose the stack beyond loopback without changing them.
