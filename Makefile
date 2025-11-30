.PHONY: install test lint format run-api run-worker docker-up docker-down

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
	$(if $(filter 1,$(DEBUG)),ALFRED_LOG_LEVEL=DEBUG,) $(RUN) uvicorn alfred.main:app --reload --port 8000 $(if $(filter 1,$(DEBUG)),--log-level debug,)

.PHONY: runapi
runapi: run-api

run-worker:
	$(RUN) celery -A alfred.celery_app.app worker -l INFO

docker-up:
	docker compose -f infra/docker-compose.yml up --build

docker-down:
	docker compose -f infra/docker-compose.yml down -v

.PHONY: ingest-urls
ingest-urls:
	@if [ -z "$(FILE)" ]; then echo "Usage: make ingest-urls FILE=urls.txt [COLLECTION=personal_kb]"; exit 1; fi
	$(RUN) python scripts/ingest.py --urls-file $(FILE) --collection $${COLLECTION:-personal_kb}
