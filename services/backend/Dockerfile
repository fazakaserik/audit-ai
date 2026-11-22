FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY packages/domain packages/domain
COPY services/backend services/backend

RUN uv sync --frozen --package backend --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uv", "run", "--package", "backend", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
