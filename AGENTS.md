
# Repository Guidelines

This document outlines how the project is structured, how to develop and test it, and the conventions to follow when contributing.

---

## Project Structure

Top-level layout:

- `apps/alfred/` — Main FastAPI app and Celery worker.
  - `alfred/api/` — HTTP routes, grouped by domain (`calendar`, `company`, `gmail`, etc.).
  - `alfred/core/` — Configuration, logging, settings, and other core infrastructure.
  - `alfred/services/` — Application service logic and integrations (Notion, vector store, Gmail, etc.).
  - `alfred/models/` — ORM models (SQLAlchemy) built on the shared `Model` base class.
  - `main.py` — FastAPI entrypoint.
  - `celery_app.py` — Celery app factory.
- `infra/docker-compose.yml` — Local Docker services (API, worker, beat, Redis).
- `scripts/` — Standalone scripts and utilities.
- `README.md` — Quick start, environment setup, tokens, and high-level overview.
- `tests/` — Pytest test suite (mirrors package layout).

### Separation of Concerns

Please keep these boundaries clear:

- **API & routing**  
  - Lives in `apps/alfred/api/`.  
  - Endpoints should be thin: validate input, call services, shape responses.

- **Services & business logic**  
  - Lives in `apps/alfred/services/`.  
  - Encapsulate application behavior here (e.g., “list inbox messages”, “sync calendar events”).

- **Third-party connectors / clients**  
  - Lives in `apps/alfred/connectors/`.  
  - Wrap low-level client behavior for external APIs (e.g., Google Calendar write API, Notion client, etc.).

- **Data models & persistence**  
  - Lives in `apps/alfred/models/`.  
  - All ORM models inherit from `Model` and declare columns directly with SQLAlchemy types.

- **Core config & plumbing**  
  - Lives in `apps/alfred/core/`.  
  - Pydantic `Settings`, logging setup, app configuration, and other cross-cutting concerns.

---

## Development Workflow

### Running the API

Use the provided `make` target:

```bash
make run-api   # alias: make runapi
```

This spins up the FastAPI app for local development.

### Linting & Formatting

We use Ruff for both linting and formatting.

* **Lint** (style, imports, errors):

  ```bash
  make lint
  ```

* **Format** (auto-format using Ruff):

  ```bash
  make format
  ```

Always run `make format` before committing, and make sure `make lint` passes.

### Environment & Imports

- The project is an installable package (editable mode). Run `make install` to install it into your virtualenv.
- `.env` is loaded by Pydantic Settings from `apps/alfred/.env`, with fallback to repo root `.env`.
- Do not add `sys.path` hacks or use `sitecustomize`.
- Avoid wrapping imports in try/except. For optional dependencies, either check availability with `importlib.util.find_spec('pkg')` and fall back, or catch `ImportError` at instantiation time and log a warning.

### Logging

- Use the central logging configuration (`apps/alfred/core/logging`) and the standard `logging` module.
- Avoid `print()` in scripts; use `logging.info/warning/error`.

---

## Coding Style & Conventions

General principles:

* Keep modules **small, focused, and readable**.
* Prefer **explicit, descriptive names** over clever ones.
* Minimize side effects; functions and methods should do one thing well.
* Keep comments and docstrings **purposeful** (explain *why*, not just *what*).

### Imports

* All imports go at the **top of the file**.
* Group them logically:

  1. Standard library.
  2. Third-party packages.
  3. Local modules.
* Let Ruff manage import ordering where possible.

### Type Hints

* Use **type hints** throughout (functions, methods, class attributes where applicable).
* Prefer `from __future__ import annotations` (if used in the project) for forward references.
* Treat type errors as real bugs; don’t ignore them unless there’s a very good reason.

### Naming

* Modules & packages: `snake_case`.
* Functions & methods: `snake_case`.
* Classes: `PascalCase`.
* Constants: `UPPER_SNAKE_CASE`.
* Avoid abbreviations unless they are widely understood (`id`, `URL`, `API`, etc.).

### Error Handling & Logging

* Handle expected error cases with clear exceptions or `HTTPException` in API layers.
* Use the central logging configuration (`apps/alfred/core/logging` or similar) instead of printing.
* Avoid logging sensitive information (tokens, secrets, personal data).
* Avoid import-in-try/except; prefer explicit availability checks or instantiation-time handling for optional features.

---

## Testing

We use **pytest**.

* Test files live under `tests/`, mirroring the package structure.

  * Example: `apps/alfred/api/system/health.py` → `tests/alfred/api/system/test_health.py`.
* Name test files `test_*.py` and test functions `test_*`.

### What to Test

Focus on the critical paths:

* API routes (including validation and error cases).
* Service logic (e.g., Gmail listing, calendar scheduling).
* Important connectors (basic happy path + error handling).

### Running Tests

```bash
pytest -q
```

or:

```bash
make test
```

Make sure tests pass before opening a PR.

---

## Backend Capabilities Snapshot

The current backend stack includes:

* **FastAPI** app with OAuth-backed Google Calendar integration:

  * Read events.
  * Create events, including Meet links and scheduling guardrails.
* **SQLAlchemy ORM** with Django-like helpers:

  * `Model` base class for concise, timestamped model definitions.
  * Alembic migrations for schema evolution.
* **Celery + Redis**:

  * Background tasks and async workflows.
* **Connectors**:

  * Notion.
  * Qdrant (vector store).
  * Gmail.
  * Web search providers (DuckDuckGo, Searx, Brave, Tavily, You.com, Exa) — optional.

* **Mind Palace**:

  * Simplified service with optional LLM enrichment (falls back to heuristics when keys/packages are missing).
  * Mongo-backed Doc Storage service (`DocStorageService`) for notes/documents/chunks; indexes ensured at API startup.

---

## Global LLM Service

We use a single, modular LLM spine that supports both OpenAI (cloud) and Ollama (local). It exposes two layers:

- LangChain/LangGraph-friendly factory: `alfred/core/llm_factory.py`
  - `get_chat_model(provider?, model?, temperature?) -> BaseChatModel`
  - `get_embedding_model(provider?, model?) -> Embeddings`
- Lower-level service: `alfred/core/llm_service.py`
  - Direct chat and streaming across providers
  - OpenAI-only structured outputs enforced via Pydantic schemas

Preferred usage in agents (LangGraph/LCEL):
```python
from alfred.core.llm_config import LLMProvider
from alfred.core.llm_factory import get_chat_model, get_embedding_model

llm = get_chat_model()  # uses defaults from env
embed = get_embedding_model()

# override per-node if needed
llm_local = get_chat_model(provider=LLMProvider.ollama, model="llama3.2")
llm_cloud = get_chat_model(provider=LLMProvider.openai, model="gpt-4.1-mini")
```

Structured outputs (OpenAI JSON schema):
```python
from pydantic import BaseModel
from alfred.core.llm_service import LLMService

class Quiz(BaseModel):
    topic: str
    questions: list[str]

svc = LLMService()
quiz = svc.structured([
    {"role": "system", "content": "Return valid JSON only."},
    {"role": "user", "content": "Generate a short quiz about LangGraph."},
], schema=Quiz)
```

Environment variables (prefix `ALFRED_`):
- `ALFRED_LLM_PROVIDER` — `openai` (default) or `ollama`
- `ALFRED_LLM_MODEL` — default chat model (`gpt-4.1-mini`)
- `ALFRED_LLM_TEMPERATURE` — default temperature (`0.2`)
- `ALFRED_OPENAI_API_KEY`, `ALFRED_OPENAI_BASE_URL`, `ALFRED_OPENAI_ORGANIZATION`
- `ALFRED_OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `ALFRED_OLLAMA_CHAT_MODEL` (default `llama3.2`)
- `ALFRED_OLLAMA_EMBED_MODEL` (default `nomic-embed-text`)

Notes
- Agents should prefer the factory functions over instantiating `ChatOpenAI`/`ChatOllama` directly.
- Use `LLMService.structured()` any time you need strict JSON outputs bound to Pydantic schemas.
- Ollama must be running locally (`ollama serve`) and the target model pulled.

---

## CI

GitHub Actions runs on `push` and `pull_request` to `main` / `master`:

* Installs dependencies.
* Runs `ruff` (lint + import checks).
* Runs `pytest`.

PRs should be green in CI before merging.

### Optional Dependencies

Install as needed when enabling providers/features:
- DuckDuckGo: `duckduckgo-search`
- Searx & You.com: `langchain-community`
- Tavily: `langchain-tavily`
- Exa: `langchain-exa`
- TinyDB (LangSearch caching): `tinydb`
- OpenAI (enrichment): `openai`

---

## Commits & Pull Requests

### Commits

* Use **Conventional Commit** prefixes:

  * `feat:` new features.
  * `fix:` bug fixes.
  * `chore:` maintenance / tooling.
  * `docs:` documentation updates.
* Keep commits **small and scoped**; one logical change per commit.

### Pull Requests

Each PR should include:

* A **clear description** of the change.
* Any **linked issues**.
* Simple **how-to-test** steps (commands, sample curls, or screenshots for APIs/flows).
* Updates to `README.md` or other docs (`AGENTS`, etc.) if behavior or configuration changes.

Try to keep PRs focused; large, multi-purpose PRs are harder to review and maintain.

---

## Security & Configuration

* **Never commit secrets.**

  * Use `apps/alfred/.env` for local development.
  * Secrets are loaded via Pydantic settings.
* **Redis**:

  * Used as the Celery broker and/or backend.
  * Ensure `REDIS_URL` is set in `.env` when not using Docker.
* **External tokens**:

  * Notion, Qdrant, OpenAI, Google, etc. belong in environment variables, not in code.
  * Avoid logging tokens, authorization headers, or other sensitive data at any log level.


```
