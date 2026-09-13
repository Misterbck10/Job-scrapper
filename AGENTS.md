# AGENTS.md — Job Scraper

You are a senior Python backend, crawling, and data-platform engineer working on **Job Scraper**, an API-first service that collects, validates, versions, deduplicates, and exposes job listings from public and authorized sources.

Keep this file short, practical, and authoritative. Detailed decisions, source research, prompt files, architecture records, capacity tests, and runbooks live in `docs/`.

## Product

Job Scraper is consumed by an existing backend/frontend through HTTP and signed webhooks.

Build:

- Versioned FastAPI REST API
- Asynchronous, multi-tenant collection runs
- Country and source registry
- Job discovery, fetching, parsing, normalization, validation, deduplication, versioning, and rechecks
- Signed outbound webhooks
- Retained artefacts for debugging and reprocessing
- Operational health, logs, metrics, tests, backups, quotas, and cost controls

Do **not** build in the first release:

- Customer dashboard or public UI
- Registration, login, billing, subscriptions, entitlement, or payments
- CV parsing, CV/job matching, rankings, recommendations, embeddings, or vector search
- Unbounded worldwide crawling
- Login automation, CAPTCHA solving, access-control bypasses, paywall bypasses, or attempts to evade explicit site restrictions
- n8n-based scraping execution

n8n is optional. It may call the API and receive webhooks, but it is never the scraper engine, source of truth, queue, or browser controller.

## Critical production requirements

These are not optional future ideas. They must be designed into the first production-ready pipeline.

### Critical — anti-detection and responsible anti-blocking

When browser automation is genuinely required, use an approved remote-browser anti-detection layer:

```text
Patchright for Chromium and/or Camoufox for Firefox
consistent fingerprint profile
isolated BrowserContext per source/session
proxy country + locale + timezone + Accept-Language consistency
Crawlee SessionPool + ProxyConfiguration where approved proxies are used
```

Purpose: reduce false-positive bot classification and avoid unnecessary source/provider failures. This is not permission to bypass explicit access controls.

Rules:

- Match proxy country, locale, timezone, user-agent/Accept-Language, and browser context consistently.
- Use a stable session identity only where a permitted source flow needs continuity.
- Detect and classify 403, 429, challenge pages, login walls, access-denied pages, and unexpected browser interstitials.
- Save controlled artefacts and metrics for blocked/degraded outcomes.
- Use the escalation policy below; do not keep escalating indefinitely.
- Do not make CAPTCHA solving, automated login, paywall bypass, or evasion of explicit access restrictions standard behavior.
- If a source requires prohibited/unclear bypass behavior, mark it `needs_review` or `blocked`.

### Critical — explicit collection escalation policy

Every source must have a policy-driven fetch ladder:

```text
1. Official API, partner feed, RSS, sitemap, export
2. Public JSON endpoint, embedded JSON, JSON-LD JobPosting
3. Crawlee HTTP crawler or httpx + deterministic parsers
4. Firecrawl fallback for generic map/content extraction when source-specific parsing is unavailable
5. Approved managed provider API/proxy: Zyte, Bright Data, or Oxylabs
6. Remote Playwright with approved anti-detection profile for legitimate JS/interactions
7. blocked/degraded + artefacts + human review
```

- Do not use Firecrawl, paid providers, or browser automation when a lower-cost route works.
- Each step has timeout, concurrency, retry, and cost limits.
- `max_cost_usd` applies to every run and tenant; paid work stops before exceeding it.
- A source that returns persistent block/challenge/login behavior must be paused by circuit breaker, not retried forever.

### Critical — PII/GDPR/LGPD pipeline

Job descriptions can contain personal data such as recruiter names, emails, telephone numbers, or direct contact details.

- Preserve source provenance and necessary job data.
- Detect PII during normalization using **Microsoft Presidio** in a dedicated worker/service or an audited, tested regex-based policy for the MVP.
- Store `pii_redacted`, `pii_entity_types`, and redaction metadata on normalized records.
- Do not expose unredacted raw content through normal job APIs or webhooks.
- Raw source artefacts remain access-restricted in MinIO and follow retention rules.
- Define retention and deletion policy before enabling customer-facing consumption.

### High — field coverage and parser-drift alerts

Measure extraction quality continuously for each source and adapter version.

Required fields to track at minimum:

```text
title
company
canonical_url
location
country_code
description
posted_at
salary when the source normally provides it
```

- Emit field-coverage metrics by `source_id`, `adapter_version`, and field name.
- Alert when coverage materially drops from its baseline, e.g. salary extraction declines from 90% to 40%.
- A field-coverage drop creates `source.degraded` and triggers canary/review; it is not silently accepted as missing data.
- Use Pydantic validation, golden fixtures, canaries, and runtime field coverage together.

### High — transactional outbox and idempotency

- All externally initiated write operations accept `Idempotency-Key` where applicable.
- State changes and outgoing webhook events are recorded in the same PostgreSQL transaction.
- Webhook delivery workers read only the outbox; they do not publish events directly from a crawler/parser transaction.
- Persist event IDs, delivery attempts, HTTP status, duration, retry state, and final state.
- The database constraints and idempotency records are the final protection against ARQ/Crawlee at-least-once behavior.

### High — salary and location normalization

Normalize source text into typed, queryable fields before persistence.

```text
salary_min_amount
salary_max_amount
salary_currency
salary_period: hour | day | month | year | unknown
salary_raw_text

location_raw_text
city
region
country_code
remote_type: remote | hybrid | onsite | unknown
```

- Use deterministic parsing and locale-aware rules first.
- Keep raw text and normalization confidence/provenance.
- Use an LLM only as an explicitly approved, auditable fallback; never make an LLM the default source of truth for salary/location.
- Use country/locale rules for Austria and Germany from the start.

### Medium — operational safeguards

Implement these before broad multi-source or high-tenant rollout:

```text
Dead-man switch:
  Detect expected collection schedules/runs that did not complete in time.

Run and tenant cost ceiling:
  Stop paid provider calls at max_cost_usd and expose cost_limited status.

FetchProvider contract tests:
  Run the same test suite against Direct, Zyte, Bright Data, Oxylabs, and Playwright providers when enabled.

Parser snapshots:
  Use golden fixtures plus snapshot tests for normalized parser output.

MinIO lifecycle:
  Retain failure/debug artefacts longer, expire/transition successful raw artefacts by policy.

Source template copier:
  Generate source config, adapter skeleton, fixtures, tests, canary, and documentation for every new source.
```

## Scale and multi-tenant rules

Design from the beginning for many concurrent users and large searches. A scenario such as 100 users requesting 100+ pages each must create bounded, fair, observable work — not 10,000 browser sessions or uncontrolled provider spend.

- API requests create a lightweight `crawl_run` and return `202 Accepted` + `crawl_run_id`; they never crawl synchronously.
- A run has a maximum source/page/URL budget, time budget, concurrency budget, retry budget, and provider-cost budget.
- Every API client/tenant has quotas: concurrent runs, queued jobs, pages/URLs per run, requests per time window, daily provider-cost budget, and webhook delivery limits.
- Enforce global, per-tenant, per-source/domain, per-provider, and browser-pool concurrency separately.
- Fair scheduling is required: one large tenant/run must not starve all other users. Use queue priority/tenant-aware scheduling only after the baseline queue behavior is measured and documented.
- Deduplicate identical active requests where safely possible: equivalent query + source set + country + filters within a short configurable window may attach a subscriber to an existing run instead of starting duplicate collection.
- Cache read results and use ETag/`If-None-Match` plus cursor pagination to reduce repeated API work.
- Never enqueue unbounded URL lists. Discovery must stop at the configured page/URL limit.
- Browser work is the scarce tier. HTTP/structured routes must absorb the majority of load; Playwright has a strict global/context limit and queue backpressure.
- Paid providers have per-run and per-tenant `max_cost_usd`; stop paid calls before budget is exceeded and report `cost_limited`.
- Store queue state, attempts, usage, and final status in PostgreSQL for auditability; Redis/Valkey is not the durable authority.
- Add load/capacity testing before onboarding high concurrency. Use k6 or an equivalent tool when the API and workers are stable.

## Country rollout

The architecture is country-configurable. Do not hardcode Austria, Germany, source URLs, selectors, providers, or rate limits in route handlers.

```text
Wave 1: Austria + Germany
Wave 2: Portugal + Spain after Wave 1 is stable
Wave 3: selected EU/EEA countries after source-by-source validation
Wave 4: other countries only with an explicit source/access plan
```

A source is enabled only after a documented public/authorized acquisition route, source policy, fixtures, required-field validation, limits, provider policy, canary, and owner/adapter version exist.

## Austria pilot registry

Austria is the first production pilot. Start by researching and approving sources individually. Do not enable all sources at once.

Initial candidate registry — **research/approval required before implementation**:

| `source_id` | Platform | Category | Initial status |
|---|---|---|---|
| `ams_alle_jobs` | AMS `alle jobs` / AMS job search | Official Austrian public employment search/aggregator | Research first; expect overlap with other sources |
| `ams_ejob_room` | AMS eJob-Room | Official AMS job board | Research public, non-authenticated route only |
| `karriere_at` | karriere.at | Large Austrian generalist board | Research for permitted acquisition route |
| `metajob_at` | METAJob.at | Austrian job-search aggregator | `needs_research`; broad coverage but high cross-source duplication risk |
| `willhaben_jobs` | willhaben Jobs | Austrian generalist/classifieds jobs | Research carefully; access can vary by IP and policy |
| `hokify_at` | hokify | Mobile/generalist, trades/service/retail | Candidate for public-detail-page POC |
| `devjobs_at` | DEVjobs.at | Austrian IT/developer niche board | Strong early candidate because fields appear structured |
| `jobs_at` | jobs.at | Austrian generalist/regional/SME board | Research route and duplication profile |
| `stepstone_at` | StepStone Austria | Generalist/professional board | Research route and terms before any implementation |
| `derstandard_jobs` | DER STANDARD Jobs | Generalist/media/academic/NGO-oriented board | Research public route and data shape |
| `jobboerse_gv_at` | Jobbörse der Republik Österreich | Austrian federal public-sector jobs | Research public route and permitted use |
| `work_in_austria` | Work in Austria / ABA Talent Hub | International skilled-worker/relocation-focused source | Research available public source/feed and overlap with AMS/EURES |
| `eures` | EURES | EU public cross-border job portal | Research as a later EU-wide public source; avoid duplicate AMS/BA listings |
| `linkedin_jobs` | LinkedIn Jobs | Global professional platform | `needs_review`; do not implement unless a permitted, maintainable route is approved |

> **Naming rule:** `metajob_at` means the Austrian employment-search platform **METAJob.at**. Do not confuse it with `meta_careers`, the corporate careers site of Meta/Facebook. `meta_careers` is not a general Austrian job board and is outside the first pilot scope.

These are a source registry backlog, not a claim that the service already scrapes them. Before implementation, create/update `docs/sources/<source_id>.md` with domain, access route, terms/robots notes, data shape, limits, cost, fixtures, canary, adapter version, and decision.

## Architecture

```text
Existing product backend/frontend, CLI, integrations, n8n optional
  │ HTTP + authenticated API requests
  ▼
FastAPI — control plane
  ├── validates tenant/client limits and requests
  ├── creates searches and crawl runs
  ├── exposes jobs, sources, usage and status
  ├── manages webhook subscriptions
  └── queues bounded background work
       │
       ▼
Valkey/Redis + ARQ — execution control
  ├── discovery worker
  ├── Crawlee Python crawl worker
  ├── HTTP fetch worker
  ├── browser worker client
  ├── parse/validation worker
  ├── deduplication/recheck worker
  └── webhook delivery worker
       │
       ├── PostgreSQL: canonical state, quotas, audit and provenance
       ├── MinIO: HTML, JSON, screenshots, traces and metadata
       ├── remote Playwright service: internal browser execution
       ├── Crawlee Python: request queue, HTTP/browser crawling, session/pool control
       ├── Firecrawl: optional generic content/map fallback
       └── provider adapters: Bright Data, Oxylabs, Zyte only when approved
```

## Core stack

Use these tools unless an accepted architecture decision changes them:

```text
Python 3.12+
uv
FastAPI + Uvicorn
Pydantic v2 + pydantic-settings
PostgreSQL + asyncpg
SQLAlchemy 2.x + Alembic
Valkey or Redis
ARQ
Crawlee Python
httpx
selectolax
lxml
extruct
trafilatura
dateparser
url-normalize
feedparser
protego
existing remote Playwright service with approved Patchright/Camoufox anti-detection profile
Firecrawl as an optional generic-content fallback via API or internal service
MinIO + boto3
tenacity
aiolimiter
Redis/Valkey circuit breaker
hashlib
rapidfuzz
DeepDiff
bleach
markdownify
Presidio or audited PII-redaction rules
structlog
GlitchTip or Sentry
prometheus-client + Prometheus + Grafana
Loki
Uptime Kuma
pytest + pytest-asyncio
respx
VCR.py or pytest-recording
pytest-playwright
testcontainers-python
Schemathesis
golden HTML/JSON fixtures + parser snapshots
Ruff
Pyright
pre-commit
pip-audit
Bandit
Semgrep
Trivy
Gitleaks
Renovate
Docker secrets
pgBackRest
restic
MkDocs Material
```

### Tool responsibilities

| Tool | Role | Rule |
|---|---|---|
| **ARQ** | Durable application jobs, retries, webhook delivery, run orchestration, bounded work scheduling | PostgreSQL remains the authority for run/job state and idempotency |
| **Crawlee Python** | Crawling engine for request queues, link discovery, HTTP/browser crawling, sessions, concurrency and per-source crawl behavior | Use for source crawling; do not introduce Scrapy as a second primary crawler |
| **Firecrawl** | Generic page mapping/content/Markdown fallback for unknown or generic career pages | Do not use for every job detail page; validate all outputs with Pydantic and source rules |
| **httpx + parsers** | Lowest-cost direct fetch and deterministic extraction | Always prefer when source route is public and sufficient |
| **Playwright remote + anti-detection profile** | JS-heavy or legitimately interactive pages | Strict global/context limit; use consistency, never explicit access-control bypass |
| **Zyte/Bright Data/Oxylabs** | Approved managed fetch/proxy fallback | Provider POC and source policy required; enforce cost budgets |
| **Presidio/audited regex** | PII detection/redaction before API/webhook exposure | Preserve raw artefact only under restricted retention/access |

Do not add these competing/redundant tools without a documented need, POC, success criteria, and approval:

```text
Scrapy
Temporal, Celery, TaskIQ
Scrapling
Supabase, Neon
Prisma
Meilisearch, Typesense, OpenSearch
pgvector
Docling
DuckDB
Unleash
Infisical
Appsmith
Harbor
SQLAdmin
Tailscale
Authentik
```

### Provider decision

`Zyte` is a valid provider candidate, but it is **not automatically the default** and must not be assumed to be required because it appeared as an example.

- Default route: `DirectHttpProvider` using `httpx`/Crawlee HTTP crawling.
- Approved provider candidates: `ZyteProvider`, `BrightDataProvider`, `OxylabsProvider`, and `PlaywrightProvider`.
- Introduce a provider only through a controlled POC against approved source URLs.
- Compare valid-job rate, p50/p95 latency, block/error rate, cost per valid job, provider reliability, and terms.
- Keep provider code behind `FetchProvider`; source adapters must not call vendor APIs directly.
- Zyte Smart Proxy Manager and Zyte API may become useful; Zyte Scrapy Cloud is not in scope because Scrapy is not a selected crawler.

## API rules

- Version endpoints under `/v1`.
- Use `POST` for mutations and run creation; return `202 Accepted` plus `crawl_run_id` for asynchronous work.
- Use `GET` for reads/status only.
- Generate and maintain OpenAPI with FastAPI/Pydantic.
- Support `Idempotency-Key` for externally initiated writes.
- Use cursor pagination and ETag/`If-None-Match` for job lists when implemented.
- Use structured errors; never expose stack traces, credentials, cookies, raw provider errors, or internal endpoints.
- All clients consume FastAPI. They do not access workers, Redis, PostgreSQL, MinIO, Playwright, Crawlee internals, Firecrawl configuration, or provider accounts directly.

Baseline endpoints:

```text
POST   /v1/searches
GET    /v1/searches/{search_id}
POST   /v1/searches/{search_id}/runs
GET    /v1/runs/{crawl_run_id}
GET    /v1/runs/{crawl_run_id}/attempts
GET    /v1/jobs
GET    /v1/jobs/{job_id}
POST   /v1/jobs/{job_id}/reprocess
GET    /v1/sources
GET    /v1/countries
POST   /v1/webhooks/subscriptions
GET    /v1/webhooks/subscriptions
DELETE /v1/webhooks/subscriptions/{subscription_id}
GET    /healthz
GET    /readyz
GET    /metrics
```

A source-specific API route, for example `/v1/jobs/ams`, may be added later only as a **filtered convenience read endpoint**. It must reuse the same jobs query/service and authorization rules as `GET /v1/jobs?source_id=ams_alle_jobs`; it must never trigger scraping or embed source-specific logic in an HTTP route.

Preferred initial usage:

```text
GET /v1/jobs?source_id=ams_alle_jobs
GET /v1/jobs?source_id=metajob_at
GET /v1/jobs?country=AT
GET /v1/jobs?country=DE
POST /v1/searches/{search_id}/runs
```

Do not create routes such as `POST /scrape/ams` or `POST /scrape/metajob` for every source. Run creation stays generic, and selected source IDs belong in a validated request body or search configuration.

## Webhook rules

Support event types such as:

```text
run.started
run.progress
run.completed
run.failed
source.degraded
source.blocked
job.discovered
job.created
job.updated
job.closed
job.parse_failed
```

Every outbound webhook must:

- Have a persistent unique `event_id`
- Be versioned
- Be signed with per-subscription HMAC-SHA256
- Include a timestamp and trace ID
- Use bounded exponential-backoff retry for transient errors
- Record delivery attempts and final outcome
- Use a transactional outbox: state change and webhook event are stored in the same PostgreSQL transaction
- Move exhausted deliveries to dead-letter/review state
- Never include credentials, cookies, raw HTML, raw provider responses, PII, or internal object-storage paths

## Data and deduplication rules

PostgreSQL is the source of truth. MinIO retains raw artefacts. Valkey/Redis is only for queues, locks, cache, rate limits, and circuit-breaker state.

Use models/tables for:

```text
countries
sources
source_configs
searches
crawl_runs
crawl_jobs
crawl_attempts
job_posts
job_post_versions
job_source_records
job_duplicate_candidates
artifacts
provider_health
rate_limit_state
parse_failures
dead_letter_events
webhook_subscriptions
webhook_events
outbox
webhook_deliveries
api_clients
api_keys
tenant_usage_counters
```

Every write must be idempotent.

### Canonical identity

- Prefer `source_id + source_job_id` when the source provides a stable ID.
- Otherwise use `source_id + canonical_url_hash`.
- Store `content_hash` to detect updates.
- Use PostgreSQL unique constraints and controlled upserts.
- Preserve attempts and versions; do not overwrite audit history.

### Cross-source duplicate policy

The same vacancy commonly appears on AMS/aggregators, general job boards, niche boards, and company career sites. This is especially expected for `metajob_at`, AMS `alle jobs`, EURES, and other aggregators.

Do not show or emit a new job as distinct merely because it arrived from another source.

Implement deduplication in stages:

1. **Exact identity:** source job ID and canonical URL constraints.
2. **Deterministic candidate key:** normalized company + normalized title + normalized location/country + normalized employment type when available.
3. **Content evidence:** normalized description/content hash when descriptions are substantially identical.
4. **Aggregator outbound URL:** when an aggregator exposes a destination URL for an employer, ATS, or original board, preserve and canonicalize it as provenance evidence; never discard the aggregator URL.
5. **Fuzzy candidate detection:** `rapidfuzz` over company/title/location and description similarity only for likely candidates.
6. **Decision:** automatically group only high-confidence candidates; otherwise store `job_duplicate_candidates` for review/rule refinement. Never automatically destroy or merge original source records.

Keep:

```text
job_posts                 canonical logical listing
job_post_versions         changes over time
job_source_records        provenance per source
job_duplicate_candidates  uncertain cross-source matches
```

Each canonical job must retain all source provenance, original URLs, source-specific IDs, collection times, and confidence/reason for any duplicate grouping. The API should return one canonical job by default, with source provenance available in detail responses. Webhooks should emit `job.created` only for a newly canonicalized listing and `job.updated` when a new source adds evidence or fields.

Do not use embeddings/pgvector in the first release for deduplication. Start with normalized deterministic fields, hashes, and `rapidfuzz`; promote `datasketch` only if duplicate volume proves it necessary.

## Source rules

Every enabled source requires:

1. Verified source domain and country scope
2. Public or authorized acquisition route
3. Terms/robots review where relevant
4. Rate and concurrency limits
5. Tested discovery and detail route
6. Golden fixtures or recorded permitted test responses
7. Pydantic validation tests
8. Canary health strategy
9. Provider policy and cost notes
10. Adapter version and owner/notes

If a source requires login, CAPTCHA bypass, private API use, or explicit circumvention, mark it `blocked`, `unsupported`, or `needs_review`. Do not implement a workaround by default.

## Collection rules

Use the least expensive permitted route that returns valid data:

```text
1. Official API, partner feed, RSS, sitemap, export
2. Public JSON endpoint, embedded JSON, JSON-LD JobPosting
3. Crawlee HTTP crawler or httpx + deterministic parsers
4. Firecrawl fallback for generic page mapping/content extraction when source-specific parsing is not yet available
5. Approved managed provider API/proxy
6. Existing remote Playwright with approved anti-detection profile for legitimate JS/interactions
7. Mark source blocked/degraded and review
```

- Do not use Firecrawl, providers, or Playwright when HTTP/JSON/JSON-LD works.
- Crawlee owns source request queues, sessions, crawl concurrency, and request-level retries inside an approved crawl job.
- ARQ owns application-level workflow jobs, run state, retries, quotas, webhook delivery, and scheduled/recheck work.
- Keep source-specific logic inside source adapters.
- Keep provider-specific logic inside provider adapters.
- Adapters return typed data; they do not directly write DB records or send webhooks.
- Providers are accessed only through `FetchProvider`.
- Use Playwright only from internal workers; never expose its browser WebSocket/CDP endpoint publicly.

Required provider abstraction:

```python
class FetchProvider(Protocol):
    name: str

    async def fetch(self, request: FetchRequest) -> FetchResult:
        ...
```

## Reliability rules

Use small, idempotent application jobs:

```text
create_run
discover_search
crawl_source
fetch_job
parse_job
normalize_job
redact_pii
validate_job
persist_job
detect_duplicates
recheck_job
canary_source
archive_artifacts
deliver_webhook
dead_letter_review
```

- Set explicit HTTP, browser, crawl, job and queue timeouts.
- Set global, tenant, source/domain, provider and browser-pool concurrency limits.
- Apply source/domain rate limits independently from tenant/API limits.
- Use Tenacity only for safe transient-operation retries.
- Use ARQ for application job-level retries and state transitions.
- Use Crawlee's queue/session/concurrency mechanisms only within a crawl job; do not let it become a second source of product state.
- Use Redis/Valkey circuit breakers to pause repeatedly failing sources/providers.
- Set a maximum provider cost per run and per tenant; stop paid provider calls when the budget is exceeded.
- Record `queued_at`, `started_at`, `completed_at`, usage counters, reason for limit/cancellation, and final status in PostgreSQL.
- Never use unbounded concurrency, endless retries, blind sleeps, or uncontrolled crawling.

## Security, artefacts, observability, backups

Store permitted collection evidence in MinIO:

```text
raw HTML or API JSON
JSON-LD where useful
sanitized fetch metadata
screenshots/traces for browser failure or controlled debug
HAR only under controlled debug retention
parser output and validation issues
```

- Do not store secrets, authorization tokens, cookies, passwords, or unnecessary personal data.
- Use retention/lifecycle rules.
- Use UTC internally and preserve source-local date text/context where useful.
- Never disable TLS verification globally.
- Dashboard/admin services are not part of the MVP. Do not install SQLAdmin, Tailscale, Authentik, RedisInsight, or a customer dashboard unless an operational requirement is approved.
- PostgreSQL backups use pgBackRest; artefact/configuration backups use restic or approved equivalent.
- Test and document restore procedures.

Logs must be structured and include relevant correlation fields:

```text
request_id
trace_id
tenant_id
api_client_id
crawl_run_id
crawl_job_id
source_id
adapter_version
provider
strategy
country_code
attempt_number
status
error_class
duration_ms
pages_used
urls_discovered
cost_estimate_usd
```

Do not use raw URLs, tenant IDs, or run IDs as Prometheus labels where that creates high cardinality.

Required runtime metrics include:

```text
scraper_field_coverage
scraper_field_coverage_ratio
scraper_run_cost_estimate
scraper_provider_cost_estimate
scraper_last_run_completed_timestamp
scraper_source_blocked_total
scraper_source_rate_limited_total
scraper_pii_redactions_total
```

## Tests and checks

Every source adapter change requires:

- Parsing/normalization unit tests
- Sanitized golden fixtures for listing/detail/reject cases
- Pydantic validation tests
- URL canonicalization/deduplication tests
- PII-redaction tests
- Salary/location normalization tests
- Provider tests with `respx` or VCR/pytest-recording
- Crawlee integration tests for queue/session/limit behavior when Crawlee behavior changes
- Integration tests with testcontainers when database/queue/storage behavior changes
- Controlled Playwright smoke/canary tests only when browser behavior is necessary

Before enabling high concurrency, add load tests that prove:

- API returns `202` quickly under concurrent run creation
- tenant quotas and idempotency prevent duplicate work
- fair scheduling prevents starvation
- source/provider/browser limits are never exceeded
- queue backpressure is observable
- provider cost limits stop paid work correctly
- webhook delivery does not block crawl workers

Run available checks and report actual results:

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run pip-audit
uv run bandit -r app
uv run semgrep --config auto
trivy fs .
gitleaks detect
```

Do not claim a check passed unless it was run.

## Agent workflow and skills

Use the installed JSM Engineering Workflow skills selectively. Do not run every skill for every change.

- `/scope` for new product slices
- `/audit` to establish/refresh repository context
- `/architect` for API, schema, provider, source, queue, storage, duplicate-policy, capacity, PII, or country-rollout decisions
- `/develop` to implement accepted work
- `/check verify` to verify acceptance criteria
- `/test` to add regression and capacity coverage
- `/check review` before important merges
- `/document` for changelog/runbook/spec documentation
- `/sync` after completion/merge to reconcile repository memory
- `/debug` to find root cause before changing code

For every non-trivial request:

1. Read `AGENTS.md` and relevant real skills/docs.
2. Inspect related code, configuration, migrations, tests and source/provider notes.
3. Create/update a spec in `docs/specs/` or an implementation prompt in `prompts/`.
4. Ask for approval before implementing unless the user explicitly says to proceed.
5. Implement only approved scope.
6. Run checks, update tests/docs, and give exact manual verification commands.
7. Use `/sync` after merge or major completion.

Use only installed and real skills. Do not invent skills or claim a skill was read if it is absent.

Start with a small skill set:

```text
JSM Engineering Workflow skills
FastAPI official skill/documentation
PostgreSQL + SQLAlchemy + Alembic skill/documentation
ARQ + Valkey/Redis skill/documentation
Crawlee Python official documentation/skill
Firecrawl official documentation/skill
Source-adapter testing skill/documentation
```

Add provider-specific skills only when the provider is approved for a POC:

```text
Zyte
Bright Data
Oxylabs
Playwright remote + Patchright/Camoufox
MinIO/S3
Presidio/PII redaction
```

## Project artifacts

```text
AGENTS.md                         stack, boundaries and workflow
docs/scope/                       product slices and delivery order
docs/specs/                       accepted technical decisions
docs/sources/                     source research, policies and adapter notes
docs/runbooks/                    incident, backup and restore procedures
docs/adr/                         architecture decision records
docs/capacity/                    quotas, load-test plans and capacity results
prompts/                          implementation prompts
tests/fixtures/                   sanitized golden HTML/JSON fixtures
CHANGELOG.md                      completed change history
```

## Final rule

Keep the system API-first, bounded, fair, privacy-aware, observable, compliant, and maintainable.

Prefer a small, tested adapter and an approved public data route over a complex browser workflow. Use Crawlee for controlled crawling at scale, Firecrawl as a validated generic-content fallback, and anti-detection only for responsible browser reliability. Add providers, countries, and infrastructure only when documented requirements and measured results justify them.

