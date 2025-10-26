<div align="center">

# Alfred — Agentic RAG API

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-109989?style=for-the-badge&logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0F0F0F?style=for-the-badge&logo=chainlink&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0e7490?style=for-the-badge)
![Qdrant](https://img.shields.io/badge/Qdrant-FF4B4B?style=for-the-badge&logo=qdrant&logoColor=white)
![Chroma](https://img.shields.io/badge/Chroma-222?style=for-the-badge)
![DuckDuckGo](https://img.shields.io/badge/DuckDuckGo-FF6600?style=for-the-badge&logo=duckduckgo&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)

An elegant FastAPI service that answers questions using Agentic RAG. It chooses between your personal notes (Qdrant/Chroma) and live web research (DuckDuckGo), then writes in your voice with minimal, professional style.

</div>

## System Design

```mermaid
flowchart TB
    subgraph Client
        UI[Swagger / CLI / cURL]
    end

    UI -->|HTTP| API[FastAPI /rag/answer]

    subgraph App[Agentic RAG Service]
        GEN[Generate Query or Respond]
        TOOLS[ToolNode]
        GRADE[Grade Documents]
        REWRITE[Rewrite Question]
        ANSWER[Generate Answer]
    end

    API --> GEN --> TOOLS
    TOOLS -->|retrieve_notes| RETRIEVE[Qdrant/Chroma Retriever]
    TOOLS -->|web_search| DDG[DuckDuckGo]
    RETRIEVE --> GRADE
    DDG --> GRADE
    GRADE -->|relevant| ANSWER
    GRADE -->|not relevant| REWRITE --> GEN
    ANSWER --> API

    subgraph Data
        VS[(Qdrant / Chroma)]
        EMB[OpenAI Embeddings]
    end

    RETRIEVE <---> VS
    VS -.uses .-> EMB
```

Highlights
- Agentic retrieval with LangGraph: decide to retrieve, search, or answer directly.
- Qdrant (cloud) preferred; Chroma fallback for local dev.
- Flexible answer styles via `mode`: minimal, concise, formal, deep.
- Clean, grounded voice; inline attributions and tiny Sources section.

## Quick Start

Prereqs
- Docker + Docker Compose
- Python 3.11+
- uv (https://github.com/astral-sh/uv) — optional but recommended
- API keys: OpenAI (for embeddings/LLM); optional Qdrant Cloud

Configure
```bash
cp apps/alfred/.env.example apps/alfred/.env
# Fill in: OPENAI_API_KEY, (optional) QDRANT_URL/QDRANT_API_KEY, NOTION_TOKEN, etc.
```

Install & Run API
```bash
uv python install 3.11          # optional: ensure matching runtime
uv sync --dev                    # install app + tooling into .venv
uv run playwright install chromium  # optional: enable dynamic crawling
make run-api  # or: PYTHONPATH=apps uv run uvicorn alfred.main:app --reload --port 8080
```

Legacy virtualenv (pip)
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium  # optional: enable dynamic crawling
make run-api UV=0  # or: PYTHONPATH=apps uvicorn alfred.main:app --reload --port 8080
```

Docker (full stack)
```bash
docker compose -f infra/docker-compose.yml up --build
```

## Ingest Knowledge

Use built-in web and PDF ingestion to populate your vector store.

```bash
# Optionally set recursion depth for link-following (0 = off)
export RECURSIVE_DEPTH=1

# Qdrant Cloud
export QDRANT_URL=...; export QDRANT_API_KEY=...; export QDRANT_COLLECTION=personal_kb

# Run ingest
uv run python scripts/ingest.py --urls-file urls.txt --collection personal_kb
# Or direct URLs
uv run python scripts/ingest.py --url https://example.com --url https://arxiv.org/abs/2012.07587
```
If you're working from an existing virtualenv, swap `uv run python` for `python` and append `UV=0` to Make targets (e.g. `make ingest-urls UV=0`).


Notes
- WebBaseLoader + optional RecursiveUrlLoader gather pages; PDFs from `data/` via PyPDFLoader.
- Chunking defaults: size 12000, overlap 200; deterministic IDs avoid duplicates.
- Embeddings: `EMBED_MODEL` (default `text-embedding-3-small`).

## RAG API

Endpoint
- `GET /rag/answer`

Query params
- `q` string: question
- `k` int: top-k retrieval (default 4)
- `include_context` bool: include retrieved chunks metadata
- `mode` string: `minimal` | `concise` | `formal` | `deep`

Example
```bash
curl "http://localhost:8080/rag/answer?q=Research%20Harmonic%20and%20write%20a%20cover%20letter&k=8&mode=deep&include_context=true"
```

Behavior
- Agent decides to use `retrieve_notes` (Qdrant/Chroma) and/or `web_search` (DuckDuckGo).
- Answers in your voice, grounded strictly in context; admits when unknown.

### `GET /company/research`

Query params
- `name` string: company to investigate.

Returns a long-form report (≈1.5–2.5k words) produced by the LangGraph company research agent.

### `GET /company/outreach`

Query params
- `name` string: target company name.
- `role` string (optional, default `AI Engineer`): angle to tailor the outreach.

Response
- Structured JSON including `summary`, `positioning`, `suggested_topics`, `outreach_email`, `follow_up`, and `sources` combining resume/profile knowledge with live company research.

### `POST /company/outreach`

Body
```json
{
  "name": "Anthropic",
  "role": "Senior AI Engineer",
  "context": "Focus on my applied research background and experience building RAG pipelines.",
  "k": 8
}
```

Behavior
- Same personalized outreach agent with optional extra instructions (`context`) and retrieval depth override `k`.
- Outputs JSON identical to the GET variant.

> Tip: run `uv run python scripts/ingest.py` (or `python scripts/ingest.py` with `UV=0`) so your resume and personal URLs are embedded before calling the outreach endpoints.

## Makefile

Useful targets
- `make install` — app + dev deps
- `make run-api` — run FastAPI locally
- `make run-worker` — Celery worker (if used)
- `make docker-up` / `make docker-down`
- `make lint` / `make format`
- `make ingest-urls FILE=urls.txt [COLLECTION=personal_kb]`

## Configuration

Core env vars
- `OPENAI_API_KEY` — required
- `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` — for Qdrant backend
- `CHROMA_PATH` — local fallback store (default `./chroma_store`)
- `EMBED_MODEL`, `CHAT_MODEL`, `FALLBACK_MODEL`
- `RECURSIVE_DEPTH` — optional crawl depth for ingest (default 0)

## Tech Stack Badges

![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![GitHub%20Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)

## Notes & Tips
- Robots-aware crawling; polite rate limiting. LinkedIn and auth-gated sites are skipped.
- `PYTHONDONTWRITEBYTECODE=1` is set in Makefile and Docker to avoid `__pycache__` noise.
- Keep secrets out of Git; use `apps/alfred/.env`.

---

Made with FastAPI + LangChain + LangGraph. PRs welcome.
