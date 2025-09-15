FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (minimal). Add more if your providers need them.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
COPY apps/alfred/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# Copy application code
COPY apps/alfred /app/alfred

# Cloud Run provides $PORT; default to 8080 for local runs
ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "uvicorn alfred.main:app --host 0.0.0.0 --port ${PORT}"]

