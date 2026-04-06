<div align="center">

# Alfred — Knowledge Factory

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-109989?style=for-the-badge&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js_16-000000?style=for-the-badge&logo=next.js&logoColor=white)
![React](https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![LangGraph](https://img.shields.io/badge/LangGraph-0e7490?style=for-the-badge)
![Qdrant](https://img.shields.io/badge/Qdrant-FF4B4B?style=for-the-badge&logo=qdrant&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)

A knowledge factory for ambitious generalists. Ingest, decompose, connect, and capitalize on what you know.

</div>

## What Is Alfred?

Alfred is a personal knowledge management system that goes beyond bookmarking. It:

- **Ingests** content from 20+ sources (web, Notion, RSS, arXiv, GitHub, Pocket, Readwise, Hypothesis, and more)
- **Decomposes** articles into atomic knowledge cards (zettels) using AI
- **Connects** ideas across domains via semantic similarity and wiki-links
- **Helps you think** with spaced repetition, a dictionary, an AI chat agent, and a canvas whiteboard

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js 16 Frontend                       │
│  Dashboard · Inbox · Knowledge · Notes · Dictionary · Canvas │
├─────────────────────────────────────────────────────────────┤
│                    FastAPI Backend                            │
│  44 API modules · 60+ services · LangGraph agents            │
├──────────┬──────────┬──────────┬────────────────────────────┤
│ PostgreSQL│  Qdrant  │  Redis   │  Celery (15 async tasks)   │
│  (SQLModel)│ (vectors)│ (cache)  │  (enrichment pipeline)     │
└──────────┴──────────┴──────────┴────────────────────────────┘
```

### Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| Backend | FastAPI, SQLModel, Alembic, Pydantic |
| AI/LLM | OpenAI (primary), Ollama, LangGraph multi-agent |
| Vector DB | Qdrant Cloud |
| Database | PostgreSQL |
| Task Queue | Celery + Redis |
| Auth | Clerk (Google + Notion OAuth) |
| Extension | Chrome browser extension (Smart Reader) |

## Quick Start

### Prerequisites
- Python 3.11+, Node.js 20+, [uv](https://github.com/astral-sh/uv), pnpm
- PostgreSQL, Redis (or use Docker)
- API keys: OpenAI (required), Qdrant Cloud (optional)

### Setup
```bash
# 1. Clone and configure
cp apps/alfred/.env.example apps/alfred/.env
# Fill in: OPENAI_API_KEY, DATABASE_URL, (optional) QDRANT_URL/QDRANT_API_KEY

# 2. Backend
make install                    # Install Python deps
make alembic-upgrade            # Run database migrations
make run-api                    # Start FastAPI on :8000

# 3. Frontend (separate terminal)
cd web && pnpm install && pnpm dev   # Start Next.js on :3000

# 4. Worker (separate terminal)
make run-worker                 # Start Celery for async tasks
```

### Docker (full stack)
```bash
docker compose -f infra/docker-compose.yml up -d --build
```

## Key Features

### Knowledge Hub
Browse, search, and filter your zettel cards by topic, tags, or full-text search. Grid, table, timeline, and graph views. Spaced repetition reviews built in.

### Inbox
Ingest documents from web URLs, file uploads, or the Chrome extension. The enrichment pipeline automatically extracts, cleans, summarizes, and decomposes content into atomic zettels.

### AI Agent
Chat with your knowledge base. The LangGraph-powered agent can search your KB, create/update zettels, and surface connections. Streaming SSE responses with tool-calling.

### Notes
Notion-style note editor with TipTap, wiki-links (`[[zettel title]]`), backlinks panel, and autosave.

### Dictionary
Look up words with AI-powered explanations, etymology, usage notes, and personal annotations.

### Canvas
Excalidraw whiteboard for visual thinking and system design.

### Connectors
Import from: Notion, Google Drive, Gmail, RSS, arXiv, Pocket, Readwise, Hypothesis, Semantic Scholar, GitHub, Todoist, Linear, Slack, Wikipedia.

## Project Structure

```
alfred/
├── apps/alfred/        # FastAPI backend
│   ├── api/            # 44 route modules
│   ├── agents/         # LangGraph multi-agent system
│   ├── core/           # Settings, DB, Redis, LLM factory
│   ├── models/         # 16 SQLModel ORM definitions
│   ├── services/       # 60+ business logic services
│   ├── tasks/          # 15 Celery async tasks
│   └── migrations/     # Alembic migrations
├── web/                # Next.js 16 frontend
│   ├── app/(app)/      # 15 app pages
│   ├── components/     # Shared + shadcn/ui components
│   ├── features/       # Data layer (queries, mutations)
│   └── lib/            # API client, stores, utilities
├── extensions/chrome/  # Browser extension
├── infra/              # Docker, GCP configs
└── tests/              # pytest test suite
```

## Development

```bash
make install          # Install all deps
make run-api          # FastAPI on :8000
make run-worker       # Celery worker
make lint             # Ruff check
make format           # Ruff format
make test             # Run tests
make alembic-upgrade  # Apply migrations
make alembic-autogen msg="description"  # Generate migration
```

## Design System

"Midnight Editorial" — editorial warmth meets structured intelligence. Source Serif 4 for display, DM Sans for UI, Berkeley Mono for system data. Deep orange (#E8590C) accent on warm charcoal (#0F0E0D). See [DESIGN.md](DESIGN.md) for the full specification.

## Documentation

| File | Purpose |
|------|---------|
| [CLAUDE.md](CLAUDE.md) | AI assistant instructions, coding conventions, project structure |
| [DESIGN.md](DESIGN.md) | Design system specification (fonts, colors, spacing, components) |
| [AGENTS.md](AGENTS.md) | Coding guidelines and AI agent tool usage |
| [PLANS.md](PLANS.md) | Planning framework for multi-step tasks |
| [TODOS.md](TODOS.md) | Tracked tech debt and feature backlog |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

---

Made with FastAPI + Next.js + LangGraph + Qdrant.
