# Alfred — API + CrewAI + SSE

## Prereqs
- Docker + Docker Compose
- Python 3.11+ (optional for local venv runs)
- Tokens: Notion, (optional) OpenAI

## Configure
```bash
cp apps/api/.env.example apps/api/.env
# Fill in NOTION_TOKEN, NOTION_PARENT_PAGE_ID, OPENAI_API_KEY if used
```

## Run API locally
```bash
make install
make run-api  # or: cd apps/api && uvicorn main:app --reload --port 8080
```

## RAG Streaming (SSE)
- Endpoint: `GET /stream/rag?q=...&k=4`
- Streams Server-Sent Events with:
  - `start` → question metadata
  - `context` → top-k retrieved items
  - `token` → partial text chunks
  - `end` → completion signal

Example with curl:
```bash
curl -N "http://localhost:8080/stream/rag?q=What%20did%20I%20ship%20last%20week%3F&k=4"
```

CLI that prints tokens live:
```bash
python scripts/rag_cli.py "What did I ship last week?"
```

Notes:
- RAG uses a persistent Chroma collection populated by the ingest script below.
- Select models via `CHAT_MODEL`, `FALLBACK_MODEL`, and embeddings via `EMBED_MODEL`.

## Ingest to Chroma (Crawl4AI)
- Install deps: `pip install -r apps/api/requirements.txt` (adds `crawl4ai`)
- Prepare env: set `OPENAI_API_KEY`; optionally set `CHROMA_PATH` (default `./chroma_store`) and `CHROMA_COLLECTION`.

Ingest URLs into persistent Chroma collection:
```bash
python scripts/ingest_crawl4ai.py --urls-file urls.txt --collection personal_kb
# or specify multiple URLs directly
python scripts/ingest_crawl4ai.py --url https://example.com --url https://openai.com
```

Behavior:
- Tries Crawl4AI; falls back to `httpx + readability + bs4` if unavailable.
- Chunks text (default 1200 chars, 200 overlap), embeds with `EMBED_MODEL` (default `text-embedding-3-small`), and upserts to a Chroma collection with metadata `{source, title, chunk}`.
- Data is persisted to `CHROMA_PATH`.

Use with RAG endpoints:
- Non-streaming: `GET /rag/answer?q=...` reads from the configured Chroma collection.
- Streaming SSE: `GET /stream/rag?q=...` for token-by-token output.

Makefile helper:
- `make ingest-urls FILE=urls.txt [COLLECTION=personal_kb]`
