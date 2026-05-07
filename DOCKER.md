# Docker Local Development

Alfred's root `docker-compose.yml` is the local full-stack entrypoint. It starts:

- `frontend`: Next.js dev server on `http://localhost:3010`
- `api`: FastAPI on `http://localhost:8000`
- `worker` and `beat`: Celery processing
- `postgres`: Alfred application database on host port `5432`
- `redis`: Redis Stack on host port `6379`
- `qdrant`: local vector store on host ports `6333` and `6334`
- `meilisearch`: full-text search on host port `7700`
- `tika`: document parsing on host port `9998`
- `litellm`: local LLM proxy on host port `4000`
- `gotenberg`: PDF generation on host port `3030`
- `n8n`: workflow automation UI on host port `5678`
- `searxng`: local web search on host port `8090`
- `firecrawl`: local Firecrawl API on host port `3002`
- `search-gateway`: unified local search gateway on `http://localhost:8010`
- `firecrawl-playwright`, `firecrawl-redis`, `firecrawl-rabbitmq`, `firecrawl-postgres`: Firecrawl internals

## Environment

Do not copy secrets into Docker images. Put keys in one of these local files:

- `.env`
- `.env.local`
- `apps/alfred/.env`
- `apps/alfred/.env.local`

Compose passes those files into Alfred containers at runtime. The stack then overrides only container-network values such as `DATABASE_URL`, `REDIS_URL`, `QDRANT_LOCAL_URL`, `FIRECRAWL_BASE_URL`, and `SEARXNG_HOST`.

SearxNG uses `infra/searxng/settings.yml` so Alfred can call the JSON search API
from inside Docker. If search returns a 403 after pulling config changes, recreate
the SearxNG container so the mounted settings file is applied.

Minimum useful setup:

```bash
cp apps/alfred/.env.example apps/alfred/.env
```

Then set:

```bash
OPENAI_API_KEY=...
```

Optional connector keys like `NOTION_TOKEN`, `READWISE_TOKEN`, `GOOGLE_CLIENT_ID`, and `GITHUB_TOKEN` can live in the same file.

## Commands

Start everything:

```bash
docker compose up --build
```

Start in the background:

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f api worker frontend firecrawl
```

Stop containers while preserving local data:

```bash
docker compose down
```

Stop containers and delete local volumes:

```bash
docker compose down -v
```

Run migrations manually:

```bash
docker compose run --rm migrate
```

Open shells:

```bash
docker compose exec api bash
docker compose exec postgres psql -U postgres -d alfred
```

## Ports

Override host ports when local services already occupy the defaults:

```bash
ALFRED_WEB_PORT=3020 ALFRED_API_PORT=8020 docker compose up --build
```

Keep `8010` reserved for `search-gateway`; local agent tooling expects
`http://localhost:8010/health` to be the search infrastructure gateway.

Supported host port variables:

- `ALFRED_WEB_PORT`
- `ALFRED_API_PORT`
- `SEARCH_GATEWAY_PORT`
- `ALFRED_POSTGRES_PORT`
- `ALFRED_REDIS_PORT`
- `QDRANT_HTTP_PORT`
- `QDRANT_GRPC_PORT`
- `MEILISEARCH_PORT`
- `TIKA_PORT`
- `LITELLM_PORT`
- `GOTENBERG_PORT`
- `N8N_PORT`
- `SEARXNG_PORT`
- `FIRECRAWL_PORT`

## Optional Neo4j

Neo4j is still optional:

```bash
docker compose --profile graph up --build
```

If you want Alfred to use it, set these in your env file:

```bash
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password
```
