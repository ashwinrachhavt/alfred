#!/usr/bin/env bash
set -euo pipefail

# Usage: DATABASE_URL=postgresql+psycopg://... ./scripts/alembic_autogen.sh "add new table"

MSG=${1:-auto}
PYTHONPATH=${PYTHONPATH:-apps}
DATABASE_URL=${DATABASE_URL:?DATABASE_URL is required}

export PYTHONPATH DATABASE_URL

# Use uv run if available; otherwise fall back to venv alembic
if command -v uv >/dev/null 2>&1; then
  uv run alembic revision --autogenerate -m "${MSG}"
else
  if [ -x ".venv/bin/alembic" ]; then
    .venv/bin/alembic revision --autogenerate -m "${MSG}"
  else
    alembic revision --autogenerate -m "${MSG}"
  fi
fi
