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

migrate:
    uv run alembic -c services/backend/alembic.ini upgrade head

up:
    docker compose -f {{compose_file}} up -d

down:
    docker compose -f {{compose_file}} down

seed:
    uv run python scripts/seed_samples.py
