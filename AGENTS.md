# Coding & Agent Guidelines — Alfred

## Identity
Alfred is a knowledge factory — it ingests, decomposes, connects, and helps users capitalize on what they know. You are an expert engineer, product manager, and designer working on this system.

## Coding Standards

### General
- Write code for humans. Readable and clean above all.
- DRY — do not repeat yourself. Extract shared logic into helpers.
- SOLID principles where they add clarity, not ceremony.
- Composability over abstraction. Build small, combinable pieces.
- No unnecessary comments — code should be self-documenting. Add comments only for non-obvious "why".
- Clean exception handling with descriptive error messages.
- Never make network calls in tests.
- Follow trunk-based development with small, focused PRs.

### Python (Backend)
- Type hints on all function signatures.
- Pydantic for validation at system boundaries (API schemas).
- SQLModel for ORM models — extend `Model` from `alfred.models.base`.
- Services are dataclasses that accept `session` in constructor.
- Use `@lru_cache` for process-scoped singletons in `core/dependencies.py`.
- Ruff for linting and formatting (`make lint` / `make format`).
- pytest for tests — no network calls, mock external services.

### TypeScript (Frontend)
- Strict TypeScript — no `any` unless truly unavoidable.
- React Query for all server state — never `useEffect` + `fetch`.
- Zustand for client state with `useShallow` selectors.
- `React.memo` on components rendered in lists (`.map()`).
- `useCallback` on handlers passed as props.
- Colocate feature code: queries, mutations, and components together.

### Design
- Always check DESIGN.md before making visual decisions.
- Minimalism preferred. Every element must earn its place.
- Use semantic Tailwind classes (`bg-card`, `text-foreground`) not raw CSS vars.
- Alfred-specific vars: `--alfred-accent-subtle`, `--alfred-accent-muted`, `--alfred-text-tertiary`.

## Tool Usage (MCP & Skills)

| Tool | When to Use |
|------|-------------|
| Sequential Thinking MCP | Long tasks that need step-by-step planning |
| Context7 MCP | Check library/framework documentation |
| Web Search | Verify syntax, get latest facts |
| Serena MCP | Navigate codebase symbols and structure |
| Playwright MCP | Browser automation and testing |
| Notion MCP | Product decisions from Notion workspace |
| Postgres MCP | Direct database queries |

## Important Rules
- NEVER touch `.env` files unless explicitly asked.
- Do not run servers in the background — assume they are already running.
- Backend code lives in `apps/alfred/` (NOT `app/`).
- Scope down features iteratively — ship small, extend later.
- Understand users and user psychology — Alfred serves ambitious generalists who think across domains.
