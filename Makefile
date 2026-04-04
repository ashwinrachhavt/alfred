.PHONY: install test lint format run-api run-worker docker-up docker-down

# Auto-load env vars from apps/alfred/.env into every recipe.
# Filters out comments, blank lines, lines with <placeholders>, and inline comments.
ENV_FILE := apps/alfred/.env
LOAD_ENV = $(if $(wildcard $(ENV_FILE)),export $$(grep -v '^\s*\#' $(ENV_FILE) | grep -v '^\s*$$' | grep -v '<' | sed 's/\s*\#.*//') &&,)

PYTHON ?= python3.11
UV ?= 1
RUN =
INSTALL =
DEBUG ?= 0

ifeq ($(UV),1)
RUN = uv run
INSTALL = uv sync --dev
else
RUN =
INSTALL = $(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt
endif

# Prevent creation of __pycache__/ and .pyc files across Make targets
export PYTHONDONTWRITEBYTECODE := 1

install:
	$(INSTALL)
	uv pip install -e .

test:
	$(RUN) pytest

lint:
	$(RUN) ruff check apps/alfred tests

format:
	$(RUN) ruff format apps/alfred tests

.PHONY: check-no-bytecode cleanup-bytecode
check-no-bytecode:
	$(RUN) python scripts/check_no_bytecode.py

cleanup-bytecode:
	$(RUN) python scripts/cleanup_bytecode.py

run-api:
	$(LOAD_ENV) $(if $(filter 1,$(DEBUG)),ALFRED_LOG_LEVEL=DEBUG,) $(RUN) uvicorn alfred.main:app --reload --port 8000 $(if $(filter 1,$(DEBUG)),--log-level debug,)

.PHONY: runapi
runapi: run-api

run-worker:
	$(LOAD_ENV) $(RUN) celery -A alfred.celery_app.app worker -l INFO -Q default,llm,agent

docker-up:
	docker compose -f infra/docker-compose.yml up --build

docker-down:
	docker compose -f infra/docker-compose.yml down -v

.PHONY: ingest-urls
ingest-urls:
	@if [ -z "$(FILE)" ]; then echo "Usage: make ingest-urls FILE=urls.txt [COLLECTION=personal_kb]"; exit 1; fi
	$(RUN) python scripts/ingest.py --urls-file $(FILE) --collection $${COLLECTION:-personal_kb}

.PHONY: alembic-autogen alembic-upgrade
# Generate a migration from current models (msg="your message" optional).
alembic-autogen:
	@msg=$${msg:-auto}; $(LOAD_ENV) PYTHONPATH=apps $(RUN) alembic revision --autogenerate -m "$${msg}"

alembic-upgrade:
	$(LOAD_ENV) PYTHONPATH=apps $(RUN) alembic upgrade head
