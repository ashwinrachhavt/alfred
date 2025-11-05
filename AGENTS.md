# Repository Guidelines

## Project Structure & Module Organization
- apps/alfred: FastAPI app and Celery worker.
  - alfred/api: HTTP routes grouped by domain (calendar, company, Gmail, etc.).
  - alfred/core: config, logging, settings.
  - alfred/services: external integrations (Notion, vector store, etc.).
  - main.py: FastAPI entrypoint; celery_app.py: Celery factory.
- infra/docker-compose.yml: local Docker services (API, worker, beat, Redis).
- README.md: quick start and tokens.

Maintain separation of concerns:
- Place application service logic in `apps/alfred/services/`.
- Keep third-party providers or custom clients under `apps/alfred/connectors/` (e.g., Google Calendar write API).
- Define ORM models inside `apps/alfred/models/`, inheriting from `Model` and using the `fields.*` helpers for succinct column declarations.
- Keep API endpoints and routing inside `apps/alfred/api/`.
- Store standalone scripts in the repository-level `scripts/` directory.
- All imports always at the top
- Code should be clean and readable
- It should be clear, well structured and easy to read.

## Build, Test, and Development Commands
make-runapi

## Linting & Formatting
- Lint: `make lint` (Ruff checks errors, imports).
- Format: `make format` (Ruff formatter).
- All contributors must write clean, well-typed, and well-structured code; favor small focused modules and keep docstrings/comments purposeful.

## Coding Style & Naming Conventions

## Testing Guidelines
- Framework: pytest. Place tests under `tests/` mirroring package paths (e.g., `tests/alfred/api/system/test_health.py`).
- Name tests `test_*.py`; aim for critical-path coverage (routes, crew runtime, services).
- Run: `pytest -q` (add pytest to your venv if not present).
  - Or: `make test`.

## Backend Capabilities Snapshot
- FastAPI app with OAuth-backed Google Calendar integration (read + event creation with Meet links and slot validation).
- SQLAlchemy ORM with Django-like helpers (`Model`, `fields`) and Alembic migrations for evolving schema.
- Configurable scheduling guardrails via `CALENDAR_*` settings and centralized Pydantic `Settings`.
- Celery + Redis background worker stack, connectors for Notion, Qdrant, Gmail, and more.

## CI
- GitHub Actions runs on push/PR to main/master: installs deps, lints with Ruff, and runs pytest.

## Commit & Pull Request Guidelines
- Commits: prefer Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`). Keep them small and scoped.
- PRs: include a clear description, linked issues, how-to-test steps, and screenshots or `curl` examples for APIs.
- Keep changes focused; update README/AGENTS if behavior or commands change.

## Security & Configuration Tips
- Never commit secrets. Use `apps/alfred/.env`; values are read via Pydantic settings.
- Redis backs Celery; ensure `REDIS_URL` is set in `.env` when not using Docker.
- External tokens: Notion, Qdrant, optional OpenAI. Avoid logging sensitive data.
