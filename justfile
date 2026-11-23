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

lint:
    uv run ruff check .
    uv run ruff format --check .

format:
    uv run ruff check --fix .
    uv run ruff format .

typecheck:
    uv run basedpyright

imports:
    # Prefer the console script; fall back when the host blocks the .exe (AppLocker).
    uv run python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports(config_filename='importlinter.ini'))"

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
    {{compose}} up -d --build

compose-down:
    {{compose}} down

compose-restart:
    just compose-down
    just compose-up

compose-clean:
    {{compose}} down -v --remove-orphans

compose-dev-up:
    {{compose_dev}} up -d --build

compose-dev-down:
    {{compose_dev}} down

compose-dev-restart:
    just compose-dev-down
    just compose-dev-up

compose-dev-clean:
    {{compose_dev}} down -v --remove-orphans

seed:
    uv run python scripts/seed_samples.py

cli:
    uv run audit-ai
