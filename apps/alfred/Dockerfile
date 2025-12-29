FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (minimal). Add more if your providers need them.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps (pinned by uv export). `requirements.txt` includes an
# editable `-e .` line, but editable installs can't be validated with hashes.
# So we install the hashed deps first, then install the app editable.
COPY pyproject.toml /app/pyproject.toml
COPY requirements.txt /app/requirements.txt
COPY alembic.ini /app/alembic.ini
RUN python -c "import re, pathlib; p=pathlib.Path('/app/requirements.txt'); out=p.with_suffix('.docker.txt'); lines=[ln for ln in p.read_text().splitlines(True) if not re.match(r'^-e\\s+\\.?$', ln.strip())]; out.write_text(''.join(lines))" \
 && pip install --upgrade pip \
 && pip install -r /app/requirements.docker.txt \
 && pip install "neo4j>=5,<6"

RUN pip install "email-validator>=2,<3"

COPY apps /app/apps
RUN pip install -e .

# Cloud Run provides $PORT; default to 8000 for local runs
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn alfred.main:app --host 0.0.0.0 --port ${PORT}"]
