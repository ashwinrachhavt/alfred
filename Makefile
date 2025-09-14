.PHONY: install test lint format run-api run-worker docker-up docker-down

PYTHON ?= python3.11

# Prevent creation of __pycache__/ and .pyc files across Make targets
export PYTHONDONTWRITEBYTECODE := 1

install:
	$(PYTHON) -m pip install -r apps/api/requirements.txt -r requirements-dev.txt

test:
	pytest

lint:
	ruff check apps/api tests

format:
	ruff format apps/api tests

run-api:
	cd apps/api && uvicorn main:app --reload --port 8080

run-worker:
	cd apps/api && celery -A celery_app.app worker -l INFO

docker-up:
	docker compose -f infra/docker-compose.yml up --build

docker-down:
	docker compose -f infra/docker-compose.yml down -v

.PHONY: ingest-urls
ingest-urls:
	@if [ -z "$(FILE)" ]; then echo "Usage: make ingest-urls FILE=urls.txt [COLLECTION=personal_kb]"; exit 1; fi
	$(PYTHON) scripts/ingest.py --urls-file $(FILE) --collection $${COLLECTION:-personal_kb}
