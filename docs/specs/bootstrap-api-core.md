# bootstrap-api-core. Esqueleto vertical da API do Job Scraper (Fase 01)

**Data**: 2026-09-13
**Status**: Accepted
**Feature relacionada**: `docs/scope/phase-01-api-core.md` (features 1 a 8)

## Summary

Esta spec define o primeiro esqueleto vertical real do Job Scraper: uma aplicação FastAPI construída por uma factory, configurada via Pydantic Settings, com logging estruturado (`structlog`) carregando um correlation ID em cada linha; PostgreSQL assíncrono (SQLAlchemy 2.x + asyncpg) com uma migração Alembic inicial; um cliente Valkey/Redis e um worker ARQ mínimo funcionando ponta a ponta; uma abstração de armazenamento de artefatos (MinIO) sem escrita real ainda; e quatro rotas HTTP funcionais. Nenhum scraping real acontece nesta fase — o objetivo é provar que a infraestrutura (banco, fila, worker, storage) funciona de verdade antes de qualquer fonte de vagas ser implementada.

## Context

O repositório tem hoje apenas um esqueleto de pastas (`app/adapters`, `app/api`, `app/core`, `app/db`, etc., todos com `__init__.py` vazios) e dois containers já no ar e saudáveis (`job-scraper-postgres`, `job-scraper-valkey`), conforme o audit anterior. Não existe `app/main.py`, não existe configuração de Alembic, não existe cliente de fila, não existem modelos de dados nem rotas.

O `AGENTS.md` exige que toda escrita externa aceite `Idempotency-Key`, que toda criação de crawl run responda `202 Accepted` + `crawl_run_id` (nunca crawling síncrono), que logs sejam estruturados com `request_id`/`trace_id`, e que o PostgreSQL seja a fonte de verdade enquanto Valkey/Redis serve só fila, cache e locks — nunca estado durável de negócio.

Sem esse esqueleto, qualquer trabalho de fonte de dados (scraping) não teria onde persistir resultados, não teria fila para rodar de forma assíncrona, e não teria um contrato de API estável para o backend consumidor integrar.

## Requirements

**User stories**:
- Como cliente da API, quero criar uma search salva via `POST /v1/searches`, para depois poder disparar execuções dela sem repetir os parâmetros de busca.
- Como cliente da API, quero disparar uma execução da search via `POST /v1/searches/{search_id}/runs` e receber imediatamente um `crawl_run_id`, para acompanhar o progresso sem bloquear minha requisição.
- Como cliente da API, quero reenviar a mesma requisição de criação de run com o mesmo `Idempotency-Key` e receber o run original, para que falhas de rede não criem runs duplicados.
- Como cliente da API, quero consultar o status de um run via `GET /v1/runs/{crawl_run_id}`, para saber se ele terminou.
- Como cliente da API, quero listar jobs via `GET /v1/jobs` com paginação por cursor, para poder percorrer resultados de forma estável mesmo que novas linhas sejam inseridas entre chamadas.
- Como operador, quero que todo log de requisição carregue um `request_id` correlacionável, para investigar problemas em produção.

**Acceptance criteria** (o contrato; cada critério é testável de forma independente):
- **AC-1**: `create_app()` retorna uma instância FastAPI funcional; `Settings` carrega todas as variáveis de `.env` com tipos validados (Pydantic Settings), falhando de forma clara se uma variável obrigatória faltar.
- **AC-2**: toda requisição HTTP gera (ou propaga, se já vier no header `X-Request-ID`) um `request_id`; esse valor aparece em todo log estruturado da requisição e é devolvido no header de resposta.
- **AC-3**: `alembic upgrade head` roda sem erro contra o Postgres do `docker-compose.yml` e cria as 7 tabelas (`countries`, `sources`, `searches`, `crawl_runs`, `crawl_jobs`, `job_posts`, `artifacts`) com as FKs e constraints descritas em Feature design; `alembic downgrade -1` reverte a migração sem erro.
- **AC-4**: uma dependency FastAPI fornece uma `AsyncSession` do SQLAlchemy 2.x por requisição, fechando a sessão ao final mesmo em caso de exceção.
- **AC-5**: o pool ARQ consegue enfileirar uma tarefa a partir do processo da API; um processo worker separado (`arq app.workers.settings.WorkerSettings`) processa a tarefa e o resultado é observável (ex.: o `crawl_run` muda de status).
- **AC-6**: existe um `ArtifactStore` (interface) com uma implementação real via boto3/MinIO, configurável via `Settings`; um método de verificação de conectividade confirma que o bucket é alcançável; nenhum método de escrita real de artefato é chamado por nenhuma rota nesta fase.
- **AC-7**: `POST /v1/searches` persiste uma search e retorna `201` com o objeto criado (incluindo `id`).
- **AC-8**: `POST /v1/searches/{search_id}/runs` cria um `crawl_run` com status `queued`, enfileira a tarefa ARQ trivial, e retorna `202 Accepted` com `{"crawl_run_id": ...}`; se `search_id` não existir, retorna `404`.
- **AC-9**: reenviar `POST /v1/searches/{search_id}/runs` com o mesmo header `Idempotency-Key` e o mesmo `search_id` retorna `202` com o `crawl_run_id` do run original (não cria um segundo run); usar o mesmo `Idempotency-Key` em um `search_id` diferente é tratado como conflito (`409`).
- **AC-10**: `GET /v1/runs/{crawl_run_id}` retorna o status persistido do run (`queued` ou `completed`); `404` se o run não existir.
- **AC-11**: `GET /v1/jobs` retorna uma lista (vazia nesta fase, ou seedada em teste) com um cursor keyset opaco em base64 codificando `(created_at, id)`; passar o `next_cursor` retornado avança a página; a última página não retorna `next_cursor`.
- **AC-12**: existe pelo menos um teste de integração (via testcontainers) cobrindo o ciclo completo: criar search → criar run → replay do `Idempotency-Key` → ler status do run → listar jobs paginado.

## Options considered

### Option 1: Uma única migração Alembic inicial para as 7 tabelas
Cria `countries`, `sources`, `searches`, `crawl_runs`, `crawl_jobs`, `job_posts`, `artifacts` numa revisão só.

**Pros**:
- As tabelas nascem juntas, com FKs entre si; uma migração única evita uma cadeia de revisões triviais.
- Mais simples de revisar e de reverter (`downgrade -1` desfaz tudo de uma vez).

**Cons**:
- Uma migração maior é um pouco mais difícil de revisar linha a linha do que várias pequenas.

### Option 2: Uma migração por tabela
Sete revisões separadas.

**Pros**:
- Histórico mais granular no Alembic.

**Cons**:
- Nenhum benefício real aqui: todas as tabelas são necessárias juntas desde o primeiro boot da API, e FKs cruzadas forçariam uma ordem de criação artificial entre migrações.

## Decision

**Chosen option**: Option 1 — uma única migração Alembic (`0001_initial_schema`) para as 7 tabelas.

**Implementation skills**: `python-fastapi` (`aiskillstore/marketplace`, `.claude/skills/python-fastapi/`) · `sqlalchemy-postgres` (`cfircoo/claude-code-toolkit`, `.claude/skills/sqlalchemy-postgres/`)

## Rationale

As sete tabelas deste slice têm dependências de FK diretas entre si (`crawl_runs.search_id → searches.id`, `crawl_jobs.crawl_run_id → crawl_runs.id`, `job_posts.source_id → sources.id`, `artifacts.crawl_job_id → crawl_jobs.id`) e nenhuma delas é utilizável isoladamente pelas rotas deste slice. Dividir em sete migrações não traria benefício de reversibilidade incremental real, só burocracia. O cursor keyset (decidido na sessão de arquitetura) e o enum mínimo de status do `crawl_run` (`queued`/`completed`) seguem o mesmo princípio: modelar exatamente o que este slice prova de verdade, sem estados ou mecanismos que só farão sentido quando o crawling real existir.

## Feature design

**Data model sketch**:

| Tabela | Campos principais | Notas |
|---|---|---|
| `countries` | `code` (PK, ISO 3166-1 alpha-2), `name` | seed mínimo (ex.: `AT`, `DE`) via migração ou fixture, não via rota |
| `sources` | `id` (PK), `source_id` (unique, string, ex. `devjobs_at`), `name`, `country_code` (FK `countries.code`) | catálogo estático nesta fase, sem adapters reais |
| `searches` | `id` (PK, UUID), `name`, `query` (JSONB), `country_code` (FK `countries.code`, nullable), `created_at` | `query` fica como JSONB genérico nesta fase; schema tipado de filtros é decisão de uma fase futura |
| `crawl_runs` | `id` (PK, UUID), `search_id` (FK `searches.id`), `status` (enum: `queued`, `completed`), `idempotency_key` (string, nullable), `created_at`, `completed_at` (nullable) | `UNIQUE (search_id, idempotency_key)` onde `idempotency_key IS NOT NULL` |
| `crawl_jobs` | `id` (PK, UUID), `crawl_run_id` (FK `crawl_runs.id`), `status` (enum: `queued`, `completed`), `created_at` | um `crawl_job` trivial por run nesta fase, prova o relacionamento run→job usado depois pelo crawling real |
| `job_posts` | `id` (PK, UUID), `source_id` (FK `sources.id`, nullable), `title`, `company`, `canonical_url`, `created_at` | campos mínimos para o contrato de paginação; normalização de salário/localização fica para fase de parsing |
| `artifacts` | `id` (PK, UUID), `crawl_job_id` (FK `crawl_jobs.id`), `kind` (string), `storage_key` (string), `created_at` | tabela existe e é migrada, mas nenhuma rota grava nela nesta fase |

**State transitions**:
- `crawl_run.status`: `queued` → `completed` (a tarefa ARQ trivial marca como `completed` ao processar; nenhum outro estado é alcançável nesta fase).
- `crawl_job.status`: espelha o `crawl_run` nesta fase (`queued` → `completed`), criado junto com o run.

**API surface**:

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/v1/searches` | POST | `name: str`, `query: dict`, `country_code: str \| None` | `id`, `name`, `query`, `country_code`, `created_at` | nenhuma nesta fase (fora do escopo) | 422 |
| `/v1/searches/{search_id}/runs` | POST | path `search_id`; header `Idempotency-Key: str \| None` | `crawl_run_id` | nenhuma nesta fase | 404 (search inexistente), 409 (idempotency key reusada com search_id diferente) |
| `/v1/runs/{crawl_run_id}` | GET | path `crawl_run_id` | `id`, `search_id`, `status`, `created_at`, `completed_at` | nenhuma nesta fase | 404 |
| `/v1/jobs` | GET | query `cursor: str \| None`, `limit: int = 20` | `items: list[JobPost]`, `next_cursor: str \| None` | nenhuma nesta fase | 422 (cursor inválido) |

**Value sourcing**:

| Action | Value produced / displayed | Source |
|---|---|---|
| `POST /v1/searches` | `id` | gerado (UUID) na criação |
| `POST /v1/searches/{search_id}/runs` | `crawl_run_id` | gerado (UUID) na criação, ou reaproveitado do run existente quando `Idempotency-Key` já foi usado para o mesmo `search_id` |
| `POST /v1/searches/{search_id}/runs` | `status` inicial do run | fixo em `queued` no momento da criação |
| worker ARQ | transição `queued` → `completed` | efeito colateral da tarefa trivial processando o `crawl_run_id` enfileirado |
| `GET /v1/runs/{crawl_run_id}` | `status`, `completed_at` | coluna `crawl_runs.status` / `crawl_runs.completed_at` |
| `GET /v1/jobs` | `next_cursor` | derivado do `(created_at, id)` do último item da página atual, codificado em base64 |
| todo log de requisição | `request_id` | header `X-Request-ID` da requisição se presente, senão gerado (UUID) pelo middleware |

**Key invariants**:
- Um `crawl_run` só existe se seu `search_id` existir (FK obrigatória).
- `(search_id, idempotency_key)` é único quando `idempotency_key` não é nulo — garante que o replay nunca duplica o run.
- `crawl_run.status` e `crawl_job.status` só assumem `queued` ou `completed` nesta fase (enum restrito no banco).
- Nenhuma rota escreve em `artifacts` nesta fase (a tabela existe só para a migração e para o `ArtifactStore` verificar conectividade).

**Security model**:
Fora de escopo nesta fase (`AGENTS.md` exclui autenticação da primeira versão). Todas as rotas ficam abertas dentro da rede interna; autenticação real é decisão de uma fase futura.

**Configuration required**:
- `DATABASE_URL`: string de conexão asyncpg para o Postgres.
- `REDIS_URL`: string de conexão para o Valkey (usada tanto pelo cliente de fila quanto pelo pool ARQ).
- `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_REGION`: configuração do `ArtifactStore` (MinIO).
- `API_PREFIX`: prefixo de versão da API (`/v1`).
- `LOG_LEVEL`: nível de log do `structlog`.

**Critical test scenarios** (cada um mapeia para um AC):
- Happy path: criar search → criar run → worker processa → `GET /runs/{id}` mostra `completed`, verifica **AC-8**, **AC-5**, **AC-10**.
- Idempotência: duas chamadas `POST /runs` com o mesmo `Idempotency-Key` e mesmo `search_id` retornam o mesmo `crawl_run_id`; com `search_id` diferente, retorna `409`, verifica **AC-9**.
- Paginação: seedar N `job_posts`, paginar com `limit` menor que N até `next_cursor` ser `None`, conferir que nenhum item se repete ou falta, verifica **AC-11**.
- Falha de configuração: subir `Settings` sem uma variável obrigatória e confirmar erro claro na inicialização, verifica **AC-1**.
- Migração: `alembic upgrade head` seguido de `alembic downgrade -1` contra o Postgres do compose, sem erro, verifica **AC-3**.

## Build plan

1. Criar `app/core/config.py` com `Settings` (Pydantic Settings) lendo todas as variáveis de `.env`, satisfaz **AC-1**.
2. Criar `app/core/logging.py` (configuração `structlog`) e middleware de correlation ID em `app/main.py`, satisfaz **AC-2**.
3. Criar `app/main.py` com `create_app()` (application factory) registrando middleware e routers, satisfaz **AC-1**, **AC-2**.
4. Configurar Alembic (`alembic.ini`, `alembic/env.py` assíncrono) e criar os modelos SQLAlchemy 2.x das 7 tabelas em `app/domain/models.py`, satisfaz **AC-3**.
5. Gerar e revisar a migração `0001_initial_schema` com as 7 tabelas, FKs e constraints do Feature design, satisfaz **AC-3**.
6. Criar `app/db/session.py` com engine assíncrono (asyncpg) e dependency `get_session()`, satisfaz **AC-4**.
7. Criar `app/core/queue.py` (cliente Valkey/Redis + pool ARQ) e `app/workers/settings.py` (`WorkerSettings` com a tarefa trivial `complete_crawl_run`), satisfaz **AC-5**.
8. Criar `app/artifacts/store.py` com a interface `ArtifactStore` e a implementação `MinioArtifactStore` (boto3) + verificação de conectividade, satisfaz **AC-6**.
9. Implementar `POST /v1/searches` em `app/api/v1/searches.py`, satisfaz **AC-7**.
10. Implementar `POST /v1/searches/{search_id}/runs` (criação do `crawl_run`, enfileiramento ARQ, lógica de `Idempotency-Key`) em `app/api/v1/runs.py`, satisfaz **AC-8**, **AC-9**.
11. Implementar `GET /v1/runs/{crawl_run_id}` em `app/api/v1/runs.py`, satisfaz **AC-10**.
12. Implementar `GET /v1/jobs` com o cursor keyset em `app/api/v1/jobs.py`, satisfaz **AC-11**.
13. Escrever testes unitários (`tests/unit/`) para `Settings`, modelos, e a codificação/decodificação do cursor.
14. Escrever testes de integração (`tests/integration/`, testcontainers) cobrindo os cenários críticos acima, satisfaz **AC-12**.

## Consequences

**Positive**:
- Toda fase futura de scraping tem onde persistir dados, uma fila real para rodar de forma assíncrona, e um contrato de API estável.
- O padrão de idempotência e o cursor keyset já nascem corretos, evitando retrabalho quando o volume de dados crescer.

**Negative / tradeoffs**:
- O enum mínimo de `crawl_run.status` (`queued`/`completed`) exigirá uma migração adicional para acrescentar `running`, `failed`, `cost_limited` etc. quando o crawling real chegar.
- `searches.query` como JSONB genérico adia a validação tipada dos filtros de busca para uma fase futura.

**Neutral**:
- `testcontainers-python` passa a ser exigido para rodar `uv run pytest` localmente (sobe containers Docker durante os testes).

## Follow-up

- [ ] Quando o crawling real for implementado, ampliar o enum de `crawl_run.status`/`crawl_job.status` via nova migração.
- [ ] Definir schema tipado para `searches.query` quando os filtros de busca reais forem especificados.
- [ ] Avaliar autenticação de API client quando essa decisão for endereçada (fora desta fase).

## References

**Project sources**:
- `AGENTS.md` (regras de API, idempotência, `202` + `crawl_run_id`, logging estruturado, stack)
- `docs/scope/phase-01-api-core.md` (features 1 a 8 desta fase)
- skill instalada `python-fastapi`
- skill instalada `sqlalchemy-postgres`

**Practices & standards**:
- Idempotency-Key para operações de escrita que podem ser repetidas pelo cliente
- Keyset pagination para listas que podem crescer e sofrer inserções concorrentes
