# Job Scraper

API-first service that collects, validates, versions, deduplicates, and exposes job listings
from public and authorized sources. See [AGENTS.md](AGENTS.md) for the full product scope,
architecture, and engineering rules.

## Status

Phase 01 (`docs/scope/phase-01-api-core.md`): walking skeleton, no live scraping yet.
FastAPI + PostgreSQL + Valkey/ARQ + MinIO vertical slice with searches, runs, and jobs endpoints.

## Stack

Python 3.12+, `uv`, FastAPI, SQLAlchemy 2.x + Alembic (async, asyncpg), Valkey/Redis + ARQ,
MinIO (boto3), `structlog`. Full stack list in [AGENTS.md](AGENTS.md#core-stack).

## Getting started

```bash
cp .env.example .env   # fill in real values
docker compose up -d   # postgres + valkey
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
uv run arq app.workers.settings.WorkerSettings   # separate terminal
```

## Checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

## Docs

- [AGENTS.md](AGENTS.md): stack, boundaries, and workflow
- [docs/scope/](docs/scope/): product slices and delivery order
- [docs/specs/](docs/specs/): accepted technical decisions
- [CHANGELOG.md](CHANGELOG.md): completed change history
