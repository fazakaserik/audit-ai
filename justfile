set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

compose_file := "deployment/docker-compose/docker-compose.yml"

default:
    @just --list

sync:
    uv sync --all-packages

check: lint typecheck imports test

lint:
    uv run ruff check .
    uv run ruff format --check .

format:
    uv run ruff check --fix .
    uv run ruff format .

typecheck:
    uv run basedpyright

imports:
    uv run lint-imports

test:
    uv run python -m pytest

test-db:
    uv run python -m pytest -m db

test-integration:
    uv run python -m pytest -m integration

# Generate a new Alembic revision from model changes (DB auto-upgrades on API startup).
# Usage: just migration "add foo column"
migration message:
    uv run alembic -c services/backend/alembic.ini revision --autogenerate -m "{{message}}"

compose-up:
    docker compose -f {{compose_file}} up -d

compose-down:
    docker compose -f {{compose_file}} down

compose-clean:
    docker compose -f {{compose_file}} down -v --remove-orphans

seed:
    uv run python scripts/seed_samples.py
