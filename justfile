set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

compose_dir := "deployment/docker-compose"
compose_file := compose_dir / "compose.yaml"
compose_dev_file := compose_dir / "compose.dev.yaml"
compose := "docker compose -f " + compose_file
compose_dev := compose + " -f " + compose_dev_file

default:
    @just --list

sync:
    uv sync --all-packages

check: lint typecheck imports test

check-backend: lint-backend typecheck-backend imports test-backend
check-cli: lint-cli typecheck-cli imports test-cli
check-tui: lint-tui typecheck-tui imports test-tui

lint:
    uv run ruff check .
    uv run ruff format --check .

lint-backend:
    uv run ruff check services/backend scripts
    uv run ruff format --check services/backend scripts

lint-cli:
    uv run ruff check cli
    uv run ruff format --check cli

lint-tui:
    uv run ruff check tui
    uv run ruff format --check tui

format:
    uv run ruff check --fix .
    uv run ruff format .

typecheck:
    uv run basedpyright

typecheck-backend:
    uv run basedpyright services/backend/src scripts

typecheck-cli:
    uv run basedpyright cli/src

typecheck-tui:
    uv run basedpyright tui/src

imports:
    # Prefer the console script; fall back when the host blocks the .exe (AppLocker).
    uv run python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports(config_filename='importlinter.ini'))"

test:
    uv run python -m pytest

test-backend:
    uv run python -m pytest services/backend/tests

test-cli:
    uv run python -m pytest cli/tests

test-tui:
    uv run python -m pytest tui/tests

test-db:
    uv run python -m pytest -m db

test-integration:
    uv run python -m pytest -m integration

# Generate a new Alembic revision from model changes (applied by the compose migrate service).
# Usage: just migration "add foo column"
migration message:
    uv run alembic -c services/backend/alembic.ini revision --autogenerate -m "{{message}}"

# Two api + two upload-processor replicas by default (demo multi-instance).
# Restart load-balancer after scale so Caddy refreshes Docker DNS upstreams.
compose-up:
    {{compose}} up -d --build --scale api=2 --scale upload-processor=2
    {{compose}} restart load-balancer

compose-down:
    {{compose}} down

compose-restart:
    just compose-down
    just compose-up

compose-clean:
    {{compose}} down -v --remove-orphans

compose-dev-up:
    {{compose_dev}} up -d --build --scale api=2 --scale upload-processor=2
    {{compose_dev}} restart load-balancer

compose-dev-down:
    {{compose_dev}} down

compose-dev-restart:
    just compose-dev-down
    just compose-dev-up

compose-dev-clean:
    {{compose_dev}} down -v --remove-orphans

seed:
    uv run --package cli python scripts/seed_samples.py

cli:
    uv run --package cli aiditor --help

tui:
    uv run --package tui aiditor-tui
