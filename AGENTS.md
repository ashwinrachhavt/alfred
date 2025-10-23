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
- Keep third-party providers or custom clients under `apps/alfred/connectors/`.
- Keep API endpoints and routing inside `apps/alfred/api/`.
- Store standalone scripts in the repository-level `scripts/` directory.

## Build, Test, and Development Commands
- Create env + install deps
  - `python3.11 -m venv .venv && source .venv/bin/activate`
  - `pip install -r apps/alfred/requirements.txt`
  - Or: `make install` (installs app + dev deps)
- Run API locally
  - `cd apps/alfred && uvicorn main:app --reload --port 8080`
  - Or: `make run-api`
- Run Celery
  - Worker: `cd apps/alfred && celery -A celery_app.app worker -l INFO`
  - Beat: `cd apps/alfred && celery -A celery_app.app beat -l INFO`
- Docker (recommended full stack)
  - `docker compose -f infra/docker-compose.yml up --build`
- Env
  - `cp apps/alfred/.env.example apps/alfred/.env` and fill tokens in `.env`.

## Linting & Formatting
- Lint: `make lint` (Ruff checks errors, imports).
- Format: `make format` (Ruff formatter).

## Coding Style & Naming Conventions
- Python 3.11+, PEP 8, 4‑space indent, 88–100 col soft limit.
- Naming: snake_case (functions/modules), PascalCase (classes), UPPER_SNAKE (constants).
- Use type hints and docstrings for public functions.
- Pydantic v2 for config/models (see `alfred/core/config.py`).

## Testing Guidelines
- Framework: pytest. Place tests under `tests/` mirroring package paths (e.g., `tests/alfred/api/system/test_health.py`).
- Name tests `test_*.py`; aim for critical-path coverage (routes, crew runtime, services).
- Run: `pytest -q` (add pytest to your venv if not present).
  - Or: `make test`.

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
