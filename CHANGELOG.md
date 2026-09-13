# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- **bootstrap-api-core**: first real vertical slice of the Job Scraper API (Phase 01).
  - FastAPI application factory (`app/main.py`) with Pydantic Settings (`app/core/config.py`) and
    `structlog`-based structured logging with a correlation-ID middleware (`X-Request-ID`).
  - Async PostgreSQL setup (SQLAlchemy 2.x + asyncpg) with the initial Alembic migration
    (`0001_initial_schema`) creating `countries`, `sources`, `searches`, `crawl_runs`,
    `crawl_jobs`, `job_posts`, `artifacts`, seeded with `AT`/`DE` in `countries`.
  - Valkey/Redis client + ARQ worker skeleton (`app/workers/settings.py`) with a trivial
    `complete_crawl_run` task proven end to end against a real worker process.
  - `ArtifactStore` abstraction with a `MinioArtifactStore` (boto3) implementation and a
    connectivity check, wired into `/readyz`.
  - `POST /v1/searches`, `POST /v1/searches/{search_id}/runs` (with `Idempotency-Key` support),
    `GET /v1/runs/{crawl_run_id}`, `GET /v1/jobs` (keyset cursor pagination).
  - Unit tests (settings, models, cursor) and testcontainers-backed integration tests (happy
    path, idempotency replay/conflict, jobs pagination).
- `docker-compose.yml`: published `postgres`/`valkey` ports to `127.0.0.1` for local, non-Docker
  development against the compose containers.
