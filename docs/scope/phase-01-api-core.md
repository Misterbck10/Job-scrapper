# Scope: Job Scraper — Phase 01, API core

Job Scraper is an API-first service that collects, validates, versions, deduplicates, and exposes job listings from public and authorized sources. Phase 01 is the walking skeleton: no scraping yet, just a real FastAPI + PostgreSQL + Valkey/ARQ vertical slice that later source work builds on.

**Build approach:** Tracer Bullet (each feature built end to end through every layer, working, so the skeleton is real rather than mocked).
**Workflow:** Beta (after `/develop`: `/check verify` then `/test`). `/architect` is the recommended first stop for a feature with a real decision, but skippable when you already know the build. Any feature can carry its own tag (e.g. `· GA`) to do more or less.

_These are recommendations to keep your build orderly, not requirements. Skip anything that does not fit: if you already know how to build a feature, use `/develop` and skip `/architect`. You decide when a feature is `done`._

## At a glance

| # | Feature | Phase | Status |
|---|---------|-------|--------|
| 1 | App factory, settings, structured logging | Foundation | done |
| 2 | PostgreSQL async setup + Alembic | Foundation | done |
| 3 | Valkey/Redis client + ARQ worker skeleton | Foundation | done |
| 4 | MinIO client abstraction | Foundation | done |
| 5 | Core domain models | Foundation | done |
| 6 | Searches and runs API | Slice 1 | done |
| 7 | Jobs read API | Slice 1 | done |
| 8 | Test suite (unit + integration) | Slice 1 | done |

## Foundations

### 1. App factory, settings, structured logging
FastAPI application factory driven by Pydantic Settings, with `structlog` request/correlation-ID middleware so every log line carries `request_id`/`trace_id` per AGENTS.md.
**Done when:** the app boots via a factory function, config loads from `.env` through a typed `Settings` object, and every request log includes a correlation ID that also appears in the response (e.g. as a header).
- [x] Design it (spec): `/architect app factory, settings, structured logging`
- [x] Build it: `/develop app factory, settings, structured logging`
   - [x] `Settings` (Pydantic Settings) loading `.env` (AC-1)
   - [x] `structlog` config + correlation-ID middleware (AC-2)
   - [x] `create_app()` application factory wiring both (AC-1, AC-2)
- [x] Verify it: `/check verify app factory, settings, structured logging`
- [x] Test it: `/test app factory, settings, structured logging`
Spec `bootstrap-api-core` · code in `app/core/config.py`, `app/core/logging.py`, `app/main.py`

### 2. PostgreSQL async setup + Alembic
Async SQLAlchemy 2.x engine/session wiring using asyncpg, plus Alembic configured and producing the first migration for the core tables in Feature 5.
**Done when:** an async session can be obtained via a FastAPI dependency, `alembic upgrade head` runs clean against the running `postgres` container, and `alembic downgrade -1` reverses it.
- [x] Design it (spec): `/architect postgresql async setup + alembic`
- [x] Build it: `/develop postgresql async setup + alembic`
   - [x] Alembic init (async `env.py`) (AC-3)
   - [x] `0001_initial_schema` migration for the 7 tables (AC-3)
   - [x] Async engine/session + `get_session()` dependency (AC-4)
- [x] Verify it: `/check verify postgresql async setup + alembic`
- [x] Test it: `/test postgresql async setup + alembic`
Spec `bootstrap-api-core` · code in `alembic/`, `app/db/session.py`

### 3. Valkey/Redis client + ARQ worker skeleton
A shared Valkey/Redis client and an ARQ `WorkerSettings` skeleton (no real jobs yet beyond a trivial health/ping task), matching AGENTS.md's ARQ-owns-application-jobs rule.
**Done when:** the API can enqueue a job through the ARQ pool, a worker process picks it up and completes it against the running `valkey` container, and connection settings come from `Settings`.
- [x] Design it (spec): `/architect valkey/redis client + arq worker skeleton`
- [x] Build it: `/develop valkey/redis client + arq worker skeleton`
   - [x] Redis/ARQ pool client (AC-5)
   - [x] `WorkerSettings` + trivial `complete_crawl_run` task (AC-5)
- [x] Verify it: `/check verify valkey/redis client + arq worker skeleton`
- [x] Test it: `/test valkey/redis client + arq worker skeleton`
Spec `bootstrap-api-core` · code in `app/core/queue.py`, `app/workers/settings.py`

### 4. MinIO client abstraction
A MinIO/S3 client wrapper (via boto3) behind an interface, wired to settings, with no real artefact writes yet — just the abstraction and a connectivity check, since AGENTS.md reserves real artefact storage for source/fetch work not in this phase.
**Done when:** the app can construct a MinIO client from settings and verify bucket connectivity (e.g. a health check), with put/get methods stubbed or minimal but not exercised by real scraping.
- [x] Design it (spec): `/architect minio client abstraction`
- [x] Build it: `/develop minio client abstraction`
   - [x] `ArtifactStore` interface + `MinioArtifactStore` (boto3) implementation (AC-6)
   - [x] Connectivity check method (AC-6)
- [x] Verify it: `/check verify minio client abstraction`
- [x] Test it: `/test minio client abstraction`
Spec `bootstrap-api-core` · code in `app/artifacts/store.py`

### 5. Core domain models
SQLAlchemy models and Alembic migration for `countries`, `sources`, `searches`, `crawl_runs`, `crawl_jobs`, `job_posts`, `artifacts` — the minimum slice of AGENTS.md's full table list needed to support this phase's endpoints.
**Done when:** the models exist with the relationships and constraints the Slice 1 endpoints need, and the Feature 2 migration creates them all in one revision.
- [x] Design it (spec): `/architect core domain models`
- [x] Build it: `/develop core domain models`
   - [x] 7 SQLAlchemy 2.x models with FKs and constraints (AC-3)
- [x] Verify it: `/check verify core domain models`
- [x] Test it: `/test core domain models`
Spec `bootstrap-api-core` · code in `app/domain/models.py`

## Slice 1: Searches, runs, jobs

### 6. Searches and runs API
`POST /v1/searches` to create a search, and `POST /v1/searches/{search_id}/runs` to start a crawl run, returning `202 Accepted` + `crawl_run_id` per AGENTS.md's async-run rule. Run creation supports `Idempotency-Key` so a retried request does not create a duplicate run, and `GET /v1/runs/{crawl_run_id}` reads run status.
**Done when:** creating a search persists it; creating a run returns `202` with a `crawl_run_id` without doing real crawl work; replaying the same `Idempotency-Key` on run creation returns the original run instead of a new one; `GET /v1/runs/{crawl_run_id}` returns the persisted status.
- [x] Design it (spec): `/architect searches and runs api`
- [x] Build it: `/develop searches and runs api`
   - [x] `POST /v1/searches` (AC-7)
   - [x] `POST /v1/searches/{search_id}/runs` + Idempotency-Key handling (AC-8, AC-9)
   - [x] `GET /v1/runs/{crawl_run_id}` (AC-10)
- [x] Verify it: `/check verify searches and runs api`
- [x] Test it: `/test searches and runs api`
Spec `bootstrap-api-core` · code in `app/api/v1/searches.py`, `app/api/v1/runs.py`

### 7. Jobs read API
`GET /v1/jobs` returning job posts with a cursor-pagination skeleton (no real job data yet, since discovery/parsing is out of this phase; the endpoint and pagination contract are real).
**Done when:** the endpoint returns an empty or seeded list with a working cursor (a page token that advances and terminates correctly), and matches the `/v1/jobs` shape AGENTS.md expects source filters to extend later.
- [x] Design it (spec): `/architect jobs read api`
- [x] Build it: `/develop jobs read api`
   - [x] Keyset cursor encode/decode `(created_at, id)` (AC-11)
   - [x] `GET /v1/jobs` endpoint (AC-11)
- [x] Verify it: `/check verify jobs read api`
- [x] Test it: `/test jobs read api`
Spec `bootstrap-api-core` · code in `app/api/v1/jobs.py`, `app/api/v1/cursor.py`

### 8. Test suite (unit + integration)
Unit tests for settings/logging/models and integration tests (via testcontainers) for the Postgres/Valkey-backed endpoints and the idempotency behavior.
**Done when:** unit tests cover settings loading and model constraints; integration tests cover run creation + idempotency replay, run status read, and the jobs cursor pagination, all runnable via `uv run pytest`.
- [x] Design it (spec): `/architect test suite (unit + integration)`
- [x] Build it: `/develop test suite (unit + integration)`
   - [x] Unit tests: settings, models, cursor encode/decode
   - [x] Integration tests (testcontainers): happy path, idempotency replay, pagination (AC-12)
- [x] Verify it: `/check verify test suite (unit + integration)`
- [x] Test it: `/test test suite (unit + integration)`
Spec `bootstrap-api-core` · code in `tests/unit/`, `tests/integration/`

## Deferred
Out of scope for this phase, kept so the plan stays honest.
- **Live source scraping (any source adapter)**: needs a decision · deferred until a source is researched and approved per AGENTS.md's source rules
- **Crawlee Python integration**: needs a decision
- **Firecrawl fallback calls**: needs a decision
- **Playwright remote browser calls**: needs a decision
- **Zyte / Bright Data / Oxylabs provider adapters**: needs a decision · GA (cost/PII sensitive)
- **Customer dashboard or public UI**: explicitly excluded by AGENTS.md's product scope
- **Authentication/payment owned by the parent product**: explicitly excluded by AGENTS.md's product scope
- **CV parsing, CV/job matching, recommendations**: explicitly excluded by AGENTS.md's product scope

## Legend

**The decision box.** Every feature carries exactly one, the sub-task whose label ends with `(spec)`. Its wording varies, so skills locate it by that `(spec)` suffix, never by an exact label. Every other box is an execution box and `/architect` never ticks one.

**Feature lifecycle**: the scope updates as a feature moves; each row is what it shows and who sets it:

| State | Set by | The feature shows |
|---|---|---|
| `planned` · needs a decision | `/scope` | one box: `Design it (spec): /architect <feature>` |
| `in-progress` (designed) | **`/architect` at spec capture** | `Design it` ticked; spec linked; `Build it: /develop <feature>` + **2 to 5 milestones**; `Verify it: /check verify <feature>`; `Test it: /test <feature>` (Beta tier) |
| `in-progress` (building) | `/develop` | milestone sub-boxes tick one by one; code pointer filled |
| `in-progress` (verified) | `/check verify` | `Build it` + milestones ticked; `Verify it` ticked |
| `done` | **you, when you decide it is** (any skill sets it when you say so); `/sync` reconciles | boxes you ran ticked, skipped ones marked skipped; Beta tier's last stage (after `/test`) is the suggested point to call it done; `/sync` captures conventions |

- **Next step** = the first unticked box (always a command or a tracked milestone).
- **needs a decision** = run `/architect` first; otherwise straight to `/develop`.
- **Atomic build tasks live in the spec's `## Build plan`, not here**: the scope carries only the milestone rollup.
- **Status** `planned` → `in-progress` → `done`, plus `existing` (pre-workflow) and `dropped` (de-scoped, kept for history).
- **Workflow** (header line) is the project default: **Beta** = `/check verify` then `/test`. A feature built on an unratified decision (an `Assumed` spec) stays flagged, but that never blocks `done`.
