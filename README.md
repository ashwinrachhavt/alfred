# Alfred — API + CrewAI + SSE

## Prereqs
- Docker + Docker Compose
- Python 3.11+ (optional for local venv runs)
- Tokens: Notion, (optional) OpenAI, Qdrant

## Configure
```bash
cp apps/api/.env.example apps/api/.env
# Fill in NOTION_TOKEN, NOTION_PARENT_PAGE_ID, QDRANT_*, OPENAI_API_KEY if used
