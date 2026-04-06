# Alfred — Knowledge Factory

## Project Overview
Alfred is a knowledge factory for ambitious generalists. It ingests, decomposes, connects, and helps users capitalize on what they know.

### Architecture
- **Backend:** FastAPI + Celery + Redis + PostgreSQL (SQLModel/Alembic)
- **Frontend:** Next.js 16 / React 19 / TypeScript / Tailwind CSS 4 / shadcn/ui
- **Vector DB:** Qdrant Cloud
- **LLMs:** OpenAI (primary), Ollama — provider-agnostic via `apps/alfred/core/llm_factory.py`
- **Auth:** Clerk (Google + Notion OAuth) — currently disabled (keys expired)
- **Agents:** LangGraph multi-agent orchestrator with team-based routing

### Key Directories
```
apps/alfred/           — FastAPI backend (NOT app/)
  api/                 — Route handlers (44 route modules)
  agents/              — LangGraph agents, teams, tools
  core/                — Settings, dependencies, DB, Redis, LLM factory
  models/              — SQLModel ORM definitions (16 models)
  schemas/             — Pydantic request/response schemas
  services/            — Business logic (60+ service files)
  tasks/               — Celery async tasks (15 task files)
  migrations/          — Alembic DB migrations
  mcp/                 — Model Context Protocol server
  connectors/          — Third-party integrations
  pipeline/            — Data processing pipelines
  prompts/             — LLM prompt templates
web/                   — Next.js frontend
  app/(app)/           — App routes (15 pages)
  components/          — Shared React components
  components/ui/       — shadcn/ui base components
  components/editor/   — TipTap markdown editor
  features/            — Data layer (queries, mutations per feature)
  lib/api/             — API client functions
  lib/stores/          — Zustand state management
  hooks/               — Custom React hooks
extensions/chrome/     — Chrome browser extension (Smart Reader)
infra/                 — Docker Compose, GCP configs
tests/                 — Mirrors apps/alfred/ structure
```

### Frontend Pages
dashboard, inbox, knowledge, notes, dictionary, research, canvas, today, connectors, settings, documents, system-design, think, notion, design-system (internal)

### Core API Routes
| Prefix | Feature |
|--------|---------|
| `/api/zettels` | Zettelkasten cards, links, reviews, graph |
| `/api/documents` | Document CRUD, semantic map, search |
| `/api/agent` | AI chat with streaming SSE |
| `/api/capture` | Chrome extension capture endpoint |
| `/api/dictionary` | Vocabulary entries, AI explanations |
| `/api/v1` | Notes CRUD, workspaces, assets |
| `/api/taxonomy` | Topic classification |
| `/api/learning` | Spaced repetition, quizzes |
| `/api/pipeline` | Document enrichment pipeline |
| `/api/intelligence` | AI-powered analysis |
| `/healthz` | Health check |

## Coding Conventions

### Backend (Python)
- **Framework:** FastAPI with `APIRouter` per feature, mounted in `main.py`
- **ORM:** SQLModel — extend `Model` from `alfred.models.base` for auto `id`, `created_at`, `updated_at`
- **Sessions:** `Session = Depends(get_db_session)` in routes. Celery tasks use `next(get_db_session())`
- **Services:** Dataclass-based services that take `session` as constructor arg (e.g., `ZettelkastenService(session)`)
- **Dependencies:** Process-scoped singletons via `@lru_cache` in `core/dependencies.py`
- **Settings:** Pydantic Settings in `core/settings.py`, accessed via `from alfred.core.settings import settings`
- **LLM calls:** Use `get_chat_model()` from `core/llm_factory.py` or `LLMService` from `services/llm_service.py`
- **Async tasks:** Define in `tasks/`, register in `tasks/__init__.py`, dispatch with `.delay()`
- **Imports:** Use `alfred.` prefix (e.g., `from alfred.services.zettelkasten_service import ZettelkastenService`)
- **Linter:** Ruff — run `make lint` / `make format`
- **Tests:** pytest, no network calls, mock external deps

### Frontend (TypeScript/React)
- **Routing:** Next.js App Router with `(app)` layout group
- **Data fetching:** TanStack React Query — queries in `features/*/queries.ts`, mutations in `features/*/mutations.ts`
- **API client:** `apiFetch()` from `lib/api/client.ts`, routes defined in `lib/api/routes.ts`
- **State:** Zustand stores in `lib/stores/` with `useShallow` selectors
- **Components:** shadcn/ui base in `components/ui/`, feature components colocated with pages
- **Styling:** Tailwind CSS 4 with semantic classes (`bg-card`, `text-foreground`, `text-primary`)
- **Alfred CSS vars:** `--alfred-accent-subtle`, `--alfred-accent-muted`, `--alfred-text-tertiary`, `--alfred-ruled-line`
- **Editor:** TipTap in `components/editor/markdown-notes-editor.tsx` with wiki-link extension
- **Performance:** Use `React.memo` on list item components, `useCallback` on handlers passed as props

### Adding a New Feature (checklist)
1. **Model:** `apps/alfred/models/new_feature.py` → register in `models/__init__.py`
2. **Migration:** `make alembic-autogen msg="add new_feature table"`
3. **Schema:** `apps/alfred/schemas/new_feature.py` (Pydantic request/response)
4. **Service:** `apps/alfred/services/new_feature_service.py`
5. **Routes:** `apps/alfred/api/new_feature/routes.py` → register in `api/__init__.py`
6. **Frontend API:** `web/lib/api/new-feature.ts` + add routes to `lib/api/routes.ts`
7. **Queries/Mutations:** `web/features/new-feature/queries.ts` + `mutations.ts`
8. **Page:** `web/app/(app)/new-feature/page.tsx`
9. **Nav:** Add to `web/app/(app)/_components/app-sidebar.tsx`

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.

### Quick Reference
- **Direction:** "Midnight Editorial" — editorial warmth meets structured intelligence
- **Fonts:** Source Serif 4 (display), DM Sans (body/UI/labels), Berkeley Mono (data/meta/system)
- **Accent:** #E8590C (deep orange) — the ONLY color used for emphasis
- **Dark base:** #0F0E0D — warm charcoal, NOT cool blue-black
- **Light base:** #FAF8F5 — warm off-white, NOT pure white
- **Neutrals:** Warm grays (stone, not steel)
- **Labels/nav:** DM Sans, 500 weight, uppercase, small size, tracked
- **System layer:** Berkeley Mono for timestamps, metadata, shortcuts
- **Border radius:** sm(4px) md(8px) lg(12px) — sharp, not bubbly

## Database
- **URL:** `DATABASE_URL` env var (defaults to PostgreSQL `postgresql+psycopg://localhost:5432/alfred`)
- **Migrations:** `make alembic-upgrade` to apply, `make alembic-autogen msg="..."` to generate
- **Pool:** Configurable via `DB_POOL_SIZE` (default 10), `DB_MAX_OVERFLOW` (default 20)
- **Redis:** Used for caching (topics/tags, semantic map), Celery broker, and knowledge notifications

## Commands
```bash
make install          # Install all deps
make run-api          # FastAPI on :8000
make run-worker       # Celery worker
make lint             # Ruff check
make format           # Ruff format
make test             # pytest
make alembic-upgrade  # Apply migrations
make docker-up        # Full Docker stack
```

## Skill Routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health

## Important Notes
- NEVER touch `.env` files unless explicitly asked
- Do not run servers in the background — assume they are already running
- The backend path is `apps/alfred/` not `app/`
- OpenAI models available: gpt-5.4, gpt-5.4-mini, gpt-5.4-pro, gpt-5.2, gpt-5.1, gpt-5, gpt-4o, o3, o4-mini
- GPT-5.x requires `max_completion_tokens` not `max_tokens`
- Tailwind uses semantic classes — use `bg-card`, `text-foreground` not raw CSS vars
