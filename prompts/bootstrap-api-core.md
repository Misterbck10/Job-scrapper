# Prompt: bootstrap-api-core

Implementation prompt for `docs/specs/bootstrap-api-core.md` (Phase 01, `docs/scope/phase-01-api-core.md`, features 1-8). Use this to drive `/develop` once implementation is approved. Do not start building from this file alone without reading the full spec first — this is a compact restatement, not a replacement.

## Objective

Build the first real vertical slice of the Job Scraper API: FastAPI app factory + Pydantic Settings + structured logging with correlation ID, async PostgreSQL (SQLAlchemy 2.x + asyncpg) with one Alembic migration, a Valkey/Redis client + ARQ worker skeleton that completes one real job end to end, a MinIO client abstraction (no real artefact writes yet), and four HTTP routes (`POST /v1/searches`, `POST /v1/searches/{search_id}/runs`, `GET /v1/runs/{crawl_run_id}`, `GET /v1/jobs`). No live scraping, no Crawlee, no Firecrawl, no Playwright, no Zyte/Bright Data/Oxylabs, no dashboard, no auth/payment, no CV matching.

## Build order

1. `app/core/config.py` — `Settings(BaseSettings)` reading `.env`: `database_url`, `redis_url`, `s3_endpoint_url`, `s3_access_key`, `s3_secret_key`, `s3_bucket`, `s3_region`, `api_prefix`, `log_level`. Fail fast on a missing required var.
2. `app/core/logging.py` — `structlog` configuration (JSON renderer in production, console in dev per `APP_ENV`); a middleware (or dependency) that reads/generates `X-Request-ID`, binds it to the structlog context, and sets it on the response header.
3. `app/main.py` — `create_app() -> FastAPI` factory; registers the request-ID middleware, mounts `app/api/v1` routers under `settings.api_prefix`, exposes `/healthz` and `/readyz` (readyz checks DB + Redis connectivity).
4. `app/domain/models.py` — SQLAlchemy 2.x declarative models: `Country`, `Source`, `Search`, `CrawlRun`, `CrawlJob`, `JobPost`, `Artifact`. Match the Data model sketch in the spec exactly (PKs, FKs, the `UNIQUE (search_id, idempotency_key)` partial constraint, the `queued`/`completed` enums).
5. `alembic/` — init with an async-capable `env.py` (uses the app's async engine/metadata); generate migration `0001_initial_schema` creating all 7 tables, FKs, and constraints. Verify both `alembic upgrade head` and `alembic downgrade -1` against the running `postgres` container from `docker-compose.yml`.
6. `app/db/session.py` — async engine (`create_async_engine` with the asyncpg URL) + `async_sessionmaker`; a FastAPI dependency `get_session()` yielding an `AsyncSession`, closed in a `finally`.
7. `app/core/queue.py` — a Redis connection pool (`redis.asyncio`) and an ARQ pool factory (`arq.create_pool`) built from `settings.redis_url`.
8. `app/workers/settings.py` — ARQ `WorkerSettings` with one function `complete_crawl_run(ctx, crawl_run_id: str)` that opens a DB session, sets the `CrawlRun.status` to `completed` and `completed_at` to now, and updates the sibling `CrawlJob` the same way.
9. `app/artifacts/store.py` — `ArtifactStore` protocol/ABC with `put(key, data) -> str` and `check_connectivity() -> bool`; `MinioArtifactStore` implementing it via `boto3` `s3` client pointed at `settings.s3_endpoint_url`. No route calls `put` in this phase; only `check_connectivity` is exercised (e.g. from `/readyz` or a startup check).
10. `app/api/v1/searches.py` — `POST /v1/searches`: validate body (`name: str`, `query: dict`, `country_code: str | None`), insert a `Search` row, return `201` with the created object.
11. `app/api/v1/runs.py` —
    - `POST /v1/searches/{search_id}/runs`: read optional `Idempotency-Key` header. If present and a `CrawlRun` already exists for `(search_id, idempotency_key)`, return `202` with that run's `crawl_run_id` (no new row, no new enqueue). If the same key exists for a *different* `search_id`, return `409`. Otherwise: 404 if `search_id` doesn't exist; else create `CrawlRun` (`status="queued"`) + a sibling `CrawlJob` (`status="queued"`), enqueue `complete_crawl_run` via the ARQ pool, return `202` with `{"crawl_run_id": ...}`.
    - `GET /v1/runs/{crawl_run_id}`: 404 if missing, else return `id`, `search_id`, `status`, `created_at`, `completed_at`.
12. `app/api/v1/jobs.py` — `GET /v1/jobs?cursor=&limit=20`: decode the base64 cursor into `(created_at, id)` (or start from the beginning if absent); query `JobPost` ordered by `(created_at, id)` with a `WHERE (created_at, id) > (cursor_created_at, cursor_id)` keyset predicate, `LIMIT limit + 1` to detect a next page; encode the last item's `(created_at, id)` as `next_cursor` when a next page exists, else omit it. Invalid cursor → `422`.
13. `tests/unit/` — `test_config.py` (Settings loads / fails fast), `test_models.py` (constraints, e.g. the idempotency unique constraint), `test_cursor.py` (encode/decode round-trip, ordering, malformed cursor rejected).
14. `tests/integration/` — testcontainers-backed Postgres + Redis; `test_searches_and_runs.py` covering the happy path (create search → create run → worker completes it → `GET /runs/{id}` shows `completed`) and the idempotency replay + cross-search-id conflict; `test_jobs_pagination.py` seeding N `JobPost` rows and paginating to exhaustion with no duplicates/gaps.

## Constraints (do not violate)

- No live source scraping, no Crawlee, no Firecrawl, no Playwright, no Zyte/Bright Data/Oxylabs client code anywhere in this slice.
- No customer dashboard, no auth/payment logic, no CV parsing/matching/recommendations.
- `Idempotency-Key` applies only to `POST /v1/searches/{search_id}/runs`, not to `POST /v1/searches`.
- `crawl_run.status` / `crawl_job.status` are restricted to `queued`/`completed` in this phase — do not add `running`/`failed`/etc. yet (tracked as follow-up in the spec).
- `ArtifactStore.put` exists but is never called by a route in this phase.
- PostgreSQL is the source of truth; Redis/Valkey is only for the ARQ queue in this slice — no business state stored there.
- All new endpoints live under `/v1` and use `async def` handlers with the async session dependency.

## Acceptance criteria (verify against these, from the spec)

AC-1 through AC-12 in `docs/specs/bootstrap-api-core.md` — `/check verify` and `/test` check against this list. Do not mark a build task done without its AC passing.

## Manual verification after building

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload &
uv run arq app.workers.settings.WorkerSettings &

curl -s -X POST localhost:8000/v1/searches -H 'content-type: application/json' \
  -d '{"name": "test", "query": {}, "country_code": "AT"}'

curl -s -X POST localhost:8000/v1/searches/<search_id>/runs \
  -H 'Idempotency-Key: test-key-1'
# repeat the same call with the same Idempotency-Key: same crawl_run_id back

curl -s localhost:8000/v1/runs/<crawl_run_id>
curl -s localhost:8000/v1/jobs

uv run pytest
uv run ruff check .
uv run pyright
```
