# Job Scraper — Primeiros Passos Atualizados

> **Objetivo:** preparar um MVP API-first do Job Scraper para Áustria e Alemanha, sem dashboard de cliente, sem pagamentos e sem scraping real antes da pesquisa/aprovação da primeira fonte.
>
> **Regra:** construir primeiro a plataforma mínima, depois pesquisar fontes, depois implementar um adapter por vez, e só então considerar APIs/proxies pagos.

---

## 1. Decisões iniciais

```text
Interface pública: FastAPI REST + webhooks HMAC
Consumidores: backend/frontend já existente, CLI, serviços internos, n8n opcional
MVP geográfico: Áustria e Alemanha
Primeira fonte real: uma única fonte austríaca aprovada após pesquisa
Fonte de verdade: PostgreSQL
Fila/locks/cache: Valkey ou Redis + ARQ
Artefactos: MinIO + boto3
Coleta padrão: httpx + JSON-LD/HTML parsing
Browser: serviço Playwright remoto já existente, apenas quando necessário
Providers externos: nenhum por padrão; Zyte/Bright Data/Oxylabs somente após POC
Dashboard de cliente: fora do MVP
```

---

## 2. Instalar workflow skills

No diretório do repositório, instale as skills de workflow JSMastery para Claude Code:

```bash
npx skills@latest add JavaScript-Mastery-Pro/skills -a claude-code
```

Use as skills seletivamente:

```text
/scope             definir fase e resultado
/audit             entender/atualizar contexto do repositório
/architect         decisões de schema, provider, fonte, API e rollout de países
/develop           implementar especificação aprovada
/check verify      validar critérios de aceitação
/test              criar testes/regressões
/check review      revisar antes de merge importante
/document          atualizar runbooks, ADRs e changelog
/sync              sincronizar AGENTS.md, specs e código após conclusão
/debug             investigar causa raiz de falha
```

Não descarte `/architect`: use-o apenas para decisões relevantes, como escolher a primeira fonte, modelar reduplicação cross-source, introduzir Zyte ou mudar API/schema.

### Skills técnicas mínimas

Não crie dezenas de skills agora. Use somente documentação oficial e, quando necessário, adicione/revise skills reais para:

```text
FastAPI
PostgreSQL + SQLAlchemy + Alembic
ARQ + Valkey/Redis
Source adapter testing
```

A comunidade FastAPI indica que o próprio projeto disponibiliza uma skill oficial em `fastapi/.agents/skills/fastapi`; use a skill/documentação oficial atual ao trabalhar com FastAPI, em vez de inventar regras de versão. [web:171]

Skills específicas de Zyte, Bright Data, Oxylabs, Playwright remoto e MinIO/S3 só devem ser adicionadas quando a respectiva integração for aprovada para POC.

---

## 3. Criar repositório e arquivos de memória

```bash
mkdir -p ~/projects/job-scraper
cd ~/projects/job-scraper

git init

mkdir -p \
  app/api/v1 \
  app/core \
  app/db \
  app/domain \
  app/services \
  app/workers \
  app/adapters \
  app/providers \
  app/artifacts \
  app/observability \
  app/webhooks \
  docs/scope \
  docs/specs \
  docs/sources \
  docs/runbooks \
  docs/adr \
  tests/unit \
  tests/integration \
  tests/fixtures \
  prompts \
  infra

touch \
  app/__init__.py \
  app/api/__init__.py \
  app/api/v1/__init__.py \
  app/core/__init__.py \
  app/db/__init__.py \
  app/domain/__init__.py \
  app/services/__init__.py \
  app/workers/__init__.py \
  app/adapters/__init__.py \
  app/providers/__init__.py \
  app/artifacts/__init__.py \
  app/observability/__init__.py \
  app/webhooks/__init__.py \
  tests/__init__.py \
  CHANGELOG.md
```

Coloque o arquivo final `Job-Scraper-AGENTS.md` na raiz e renomeie-o para:

```text
AGENTS.md
```

O agente deve sempre ler esse arquivo antes de trabalhar.

---

## 4. Criar ambiente Python com uv

Verifique pré-requisitos:

```bash
python3 --version
python3.12 --version || true
docker --version
docker compose version
git --version
curl --version
```

Instale `uv` pelo método oficial atual:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Abra um novo terminal ou atualize o PATH conforme o instalador indicar, então valide:

```bash
uv --version
```

Inicialize o projeto:

```bash
uv init --python 3.12
```

Se já existir `pyproject.toml`, leia-o antes e não rode `uv init` por cima.

---

## 5. Instalar dependências do vertical slice

Instale somente a base necessária para API, banco, fila, parsing, artefactos, qualidade e testes.

```bash
uv add \
  fastapi \
  "uvicorn[standard]" \
  pydantic \
  pydantic-settings \
  sqlalchemy \
  asyncpg \
  alembic \
  arq \
  redis \
  httpx \
  selectolax \
  lxml \
  extruct \
  trafilatura \
  dateparser \
  url-normalize \
  feedparser \
  protego \
  boto3 \
  structlog \
  tenacity \
  aiolimiter \
  rapidfuzz \
  deepdiff \
  bleach \
  markdownify \
  prometheus-client
```

Ferramentas de desenvolvimento:

```bash
uv add --dev \
  pytest \
  pytest-asyncio \
  pytest-cov \
  respx \
  pytest-recording \
  testcontainers \
  schemathesis \
  ruff \
  pyright \
  pre-commit \
  pip-audit \
  bandit \
  semgrep
```

Instale host tools de segurança pelo gerenciador do seu sistema, ou execute por containers no CI:

```text
Trivy
Gitleaks
```

Não instale agora:

```text
Zyte SDK/client
Bright Data SDK/client
Oxylabs SDK/client
Scrapy
Crawlee Python
Scrapling
Crawl4AI
Firecrawl
Temporal
Celery
TaskIQ
Supabase SDK
Neon SDK
Prisma
Meilisearch/Typesense/OpenSearch
pgvector
Docling
DuckDB
Unleash
Infisical
Appsmith
Harbor
```

Essas ferramentas não estão proibidas. Elas são promovidas somente através de uma spec/POC aprovada.

---

## 6. Configuração inicial

### `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.so
.pytest_cache/
.mypy_cache/
.ruff_cache/
.pyright/
.coverage
htmlcov/

# Environments
.venv/

# Secrets
.env
.env.*
!.env.example
*.pem
*.key

# Local artefacts
artifacts/
*.har
*.trace

# IDE/OS
.vscode/
.idea/
.DS_Store
```

### `.env.example`

```dotenv
APP_ENV=development
LOG_LEVEL=INFO
API_PREFIX=/v1

DATABASE_URL=postgresql+asyncpg://job_scraper:CHANGE_ME@postgres:5432/job_scraper
REDIS_URL=redis://:CHANGE_ME@valkey:6379/0

S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY=CHANGE_ME
S3_SECRET_KEY=CHANGE_ME
S3_BUCKET=job-scraper-artifacts
S3_REGION=us-east-1

API_KEY_PEPPER=CHANGE_ME
WEBHOOK_SIGNING_SECRET=CHANGE_ME

PLAYWRIGHT_SERVICE_URL=http://playwright:3000
PLAYWRIGHT_SERVICE_TOKEN=CHANGE_ME

PROMETHEUS_ENABLED=true
SENTRY_DSN=

# Providers stay empty until a POC is approved.
ZYTE_API_KEY=
BRIGHTDATA_API_KEY=
OXYLABS_USERNAME=
OXYLABS_PASSWORD=
```

Crie o `.env` local:

```bash
cp .env.example .env
chmod 600 .env
```

Nunca faça commit do `.env`. Em produção, use Docker secrets ou um secret manager aprovado.

### `pyproject.toml`

Depois de `uv init`, adicione/mescle:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "ASYNC"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
include = ["app", "tests"]
exclude = [".venv", "migrations"]

[tool.coverage.run]
source = ["app"]
branch = true
```

---

## 7. Serviços de desenvolvimento

Crie `docker-compose.yml` para PostgreSQL, Valkey e MinIO. Ajuste volumes e paths para a sua infraestrutura/TrueNAS antes de executar.

```yaml
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: job_scraper
      POSTGRES_USER: job_scraper
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U job_scraper -d job_scraper"]
      interval: 10s
      timeout: 5s
      retries: 10
    networks:
      - internal

  valkey:
    image: valkey/valkey:8-alpine
    restart: unless-stopped
    command: ["valkey-server", "--appendonly", "yes", "--requirepass", "${VALKEY_PASSWORD}"]
    environment:
      VALKEY_PASSWORD: ${VALKEY_PASSWORD}
    volumes:
      - valkey_data:/data
    healthcheck:
      test: ["CMD-SHELL", "valkey-cli -a \"$$VALKEY_PASSWORD\" ping | grep PONG"]
      interval: 10s
      timeout: 5s
      retries: 10
    networks:
      - internal

  minio:
    image: minio/minio:latest
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 10
    networks:
      - internal

  minio-init:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >-
      /bin/sh -c "
      mc alias set local http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD &&
      mc mb --ignore-existing local/$$S3_BUCKET &&
      mc anonymous set none local/$$S3_BUCKET
      "
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
      S3_BUCKET: ${S3_BUCKET}
    networks:
      - internal

volumes:
  postgres_data:
  valkey_data:
  minio_data:

networks:
  internal:
    internal: true
```

Adicione ao `.env` local:

```dotenv
POSTGRES_PASSWORD=replace-with-a-long-local-password
VALKEY_PASSWORD=replace-with-a-long-local-password
MINIO_ROOT_USER=replace-with-minio-admin-user
MINIO_ROOT_PASSWORD=replace-with-a-long-minio-password
```

Faça `DATABASE_URL`, `REDIS_URL`, `S3_ACCESS_KEY` e `S3_SECRET_KEY` coincidirem com os valores da composição.

Suba os serviços:

```bash
docker compose up -d postgres valkey minio minio-init
docker compose ps
```

Verifique logs:

```bash
docker compose logs --tail=100 postgres
docker compose logs --tail=100 valkey
docker compose logs --tail=100 minio
```

Não publique PostgreSQL, Valkey, MinIO API ou Playwright diretamente para a internet. Painéis futuros devem passar pela sua política de Traefik, Tailscale e Authentik.

---

## 8. Primeiro prompt para o agente

Antes de escrever código, crie `prompts/bootstrap-api-core.md` com este escopo:

```text
Goal:
Build an API-first Job Scraper vertical slice without customer dashboard,
live third-party scraping, paid providers, or browser calls.

Include:
- FastAPI app factory
- Pydantic settings
- request/correlation IDs and structured logging
- /healthz, /readyz and /metrics
- PostgreSQL async connection/session setup
- SQLAlchemy models + Alembic initial migration
- Valkey/Redis client + ARQ worker skeleton
- MinIO/S3 client abstraction
- country, source, search, crawl_run, crawl_job, job_post and artifact models
- POST /v1/searches
- POST /v1/searches/{search_id}/runs returning 202 + crawl_run_id
- GET /v1/runs/{crawl_run_id}
- GET /v1/jobs with pagination skeleton
- idempotency-key handling for run creation
- unit and integration tests

Do not include:
- live source scraping
- Zyte/Bright Data/Oxylabs calls
- Playwright calls
- customer dashboard
- parent-product payment/registration/auth flows
- CV matching or recommendations
```

No Claude Code/Codex, siga:

```text
/scope
/architect
/develop
/check verify
/test
/document
/sync
```

Respeite a regra em `AGENTS.md`: o agente cria/atualiza prompt/spec, pede aprovação e só então implementa.

---

## 9. Matriz de fontes: Áustria e Alemanha

Antes de qualquer adapter real, crie:

```text
docs/sources/austria-source-matrix.md
docs/sources/germany-source-matrix.md
```

### Áustria: candidatos iniciais

| `source_id` | Plataforma | Prioridade de pesquisa | Nota |
|---|---|---:|---|
| `ams_alle_jobs` | AMS `alle jobs` | Alta | É uma busca oficial/aggregadora; alta chance de sobreposição com outros portais |
| `ams_ejob_room` | AMS eJob-Room | Alta | Usar apenas rota pública não autenticada, se aprovada |
| `karriere_at` | karriere.at | Alta | Grande cobertura geral; pesquisar acesso e duplicação |
| `devjobs_at` | DEVjobs.at | Alta | Bom candidato para POC IT devido a estrutura de vagas aparentemente clara |
| `hokify_at` | hokify | Média-alta | Detalhes públicos aparentam ter Job ID e campos visíveis |
| `willhaben_jobs` | willhaben Jobs | Média | Pesquisar cuidadosamente; acessibilidade pode variar por IP/política |
| `jobs_at` | jobs.at | Média | Generalista/SME/regional; verificar rota e sobreposição |
| `stepstone_at` | StepStone Austria | Média | Pesquisar termos e rota antes de qualquer adapter |
| `derstandard_jobs` | DER STANDARD Jobs | Média | Pode acrescentar segmentos de mídia/academia/ONG |
| `jobboerse_gv_at` | Jobbörse der Republik Österreich | Média | Fonte oficial de setor público |
| `work_in_austria` | Work in Austria / ABA Talent Hub | Média | Foco internacional/qualificado; verificar feed/acesso e duplicação |
| `eures` | EURES | Posterior | Fonte pública transfronteiriça; forte risco de duplicar AMS/BA e outros |
| `linkedin_jobs` | LinkedIn Jobs | Needs review | Não implementar sem rota permitida e sustentável |

### Alemanha: candidatos de backlog

| `source_id` | Plataforma | Nota |
|---|---|---|
| `bundesagentur_arbeit` | BA Jobsuche / Jobbörse | Fonte pública oficial; prioridade de pesquisa alta |
| `make_it_in_germany` | Make it in Germany | Portal oficial para profissionais internacionais; pode sobrepor BA |
| `stepstone_de` | StepStone Germany | Generalista/profissional; pesquisar primeiro |
| `xing_jobs` | XING Jobs | Relevante para mercado DACH; pesquisar rota permitida |
| `meinestadt_de` | meinestadt.de | Forte em procura regional/local |
| `stellenanzeigen_de` | stellenanzeigen.de | Board alemão relevante |
| `jobware_de` | Jobware | Generalista/profissional |
| `arbeitsagentur_eures` | EURES/BA cross-border | Tratar como duplicação potencial |
| `indeed_de` | Indeed Germany | Needs review por ser agregador e por política/acesso |
| `linkedin_jobs_de` | LinkedIn Jobs | Needs review; mesma política global do LinkedIn |

A Alemanha deve ficar no registry desde o começo, mas a primeira implementação live ainda deve ser uma fonte austríaca aprovada. Fontes oficiais como AMS/`alle jobs` e EURES são valiosas, mas podem agregar anúncios de terceiros; isso torna a deduplicação cross-source obrigatória. O AMS informa que `alle jobs` pesquisa ofertas geridas pelo AMS, eJob-Room, fontes de empresas/instituições, administração pública e algumas vagas alemãs; EURES oferece vagas transfronteiriças. [web:186][web:216][web:219]

---

## 10. Pesquisa de fonte antes de escrever adapter

Para cada fonte, crie `docs/sources/<source_id>.md` com:

```text
Nome e domínio verificados
País(es) e idioma(s)
Tipo de fonte: oficial, generalista, agregador, nicho, ATS
Rota pública/autorizada considerada
API, RSS, sitemap, JSON-LD, JSON embutido, HTML ou browser necessário
Revisão de termos e robots, quando aplicável
Login necessário? Sim/não
Campos encontrados: ID, título, empresa, local, descrição, data, salário
Risco de duplicação com outras fontes
Limite de requests/concurrency
Provider policy: direct HTTP / provider POC / Playwright
Custo estimado
Fixtures permitidas
Canary strategy
Adapter version
Status: approved_for_poc / needs_review / unsupported / blocked / postponed
```

Só crie um adapter se o status for `approved_for_poc`.

---

## 11. Deduplicação cross-source desde o primeiro adapter

A deduplicação não é melhoria futura: ela entra no schema e no pipeline desde o começo, mesmo que inicialmente só exista uma fonte.

Implementar em fases:

```text
1. source_id + source_job_id
2. source_id + canonical_url_hash
3. normalized_company + normalized_title + normalized_location/country
4. description/content hash
5. rapidfuzz para candidatos prováveis
6. job_duplicate_candidates para casos incertos
```

Não apagar registros originais de fontes. Um job canônico precisa preservar proveniência:

```text
fonte original
URL original
source_job_id
horário de coleta
confiança/motivo de grupo duplicado
versão do adapter
```

A API pode retornar a vaga canônica sem repetições e fornecer as fontes de origem em endpoint de detalhe. Assim, AMS, Karriere.at, willhaben e uma página de empresa podem contribuir para o mesmo emprego lógico sem o utilizador receber quatro resultados iguais.

---

## 12. POC de provider: Zyte é exemplo, não decisão automática

Zyte é uma opção válida para testar, sobretudo se no futuro Scrapy for adotado: a Zyte mantém produtos de API/proxy e infraestrutura ligada ao ecossistema Scrapy. Mas ela deve ser avaliada como qualquer provider, não colocada como obrigação porque foi citada como exemplo. Scrapy 2.14 inclui melhorias modernas de async/await e agendamento, o que torna Zyte/Scrapy uma combinação possível para escala posterior — não para o bootstrap do projeto. [web:152][web:164]

Após o primeiro adapter HTTP-first, se existir um problema real de acessibilidade, crie uma POC comparando:

```text
A. DirectHttpProvider
B. ZyteProvider
C. BrightDataProvider ou OxylabsProvider
D. PlaywrightProvider, apenas se JavaScript legítimo for necessário
```

Para 30–100 URLs permitidas, medir:

```text
valid_job_rate
p50_latency_ms
p95_latency_ms
provider_error_rate
blocked_rate
parser_failure_rate
estimated_cost_per_valid_job
required operational complexity
```

Só promova um provider quando os números justificarem.

---

## 13. Checks iniciais

Depois de cada implementação aprovada, execute e registre o resultado:

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

`Trivy` e `Gitleaks` podem estar instalados no host ou rodar por container no CI. Não declare que passaram sem executar.

---

## 14. Primeiro runtime

Depois de a aplicação FastAPI existir:

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Em outro terminal:

```bash
curl -i http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/readyz
curl -i http://127.0.0.1:8000/docs
```

Quando os endpoints de domínio existirem, use a documentação OpenAPI gerada para obter os payloads reais. Não invente chamadas/IDs antes de os contratos Pydantic serem implementados.

---

## 15. Não fazer agora

```text
- Não criar dashboard de cliente.
- Não adicionar 10+ fontes simultaneamente.
- Não executar scraping live antes de aprovar uma fonte.
- Não usar n8n como executor do scraper.
- Não expor Playwright, PostgreSQL, Valkey ou MinIO publicamente.
- Não adicionar Supabase, Neon e PostgreSQL self-hosted como donos simultâneos do banco.
- Não adicionar Prisma ao core Python.
- Não adicionar Temporal, Celery e ARQ juntos.
- Não adicionar Scrapy e Crawlee juntos.
- Não implementar bypass de login/CAPTCHA/paywall ou evasão de controles explícitos.
- Não contratar/integrar providers pagos antes de uma POC controlada.
- Não remover ou fundir registros de fonte sem preservar proveniência.
```

---

## 16. Próxima sequência exata

1. Criar o repositório e colocar `AGENTS.md` na raiz.
2. Instalar as skills de workflow JSMastery.
3. Instalar `uv` e inicializar Python 3.12.
4. Adicionar dependências do vertical slice.
5. Criar `.env`, `.env.example`, `pyproject.toml` e `docker-compose.yml`.
6. Subir PostgreSQL, Valkey e MinIO.
7. Usar `/scope` e `/architect` para gerar `prompts/bootstrap-api-core.md`.
8. Aprovar o prompt e implementar somente o vertical slice API-first.
9. Criar matrizes de fontes Áustria/Alemanha e pesquisar cada candidata.
10. Escolher **uma** fonte austríaca aprovada e criar o primeiro adapter HTTP-first com fixtures e canary.
11. Implementar deduplicação/proveniência antes de adicionar a segunda fonte.
12. Fazer POC de provider apenas se a primeira fonte provar que HTTP direto não é suficiente.
