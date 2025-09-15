from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

from alfred.api.v1.calendar_oauth import router as calendar_router
from alfred.api.v1.company import router as company_router
from alfred.api.v1.gmail_oauth import router as gmail_oauth_router
from alfred.api.v1.gmail_status import router as gmail_router
from alfred.api.v1.health import router as health_router
from alfred.api.v1.notion import router as notion_router
from alfred.api.v1.rag import router as rag_router
from alfred.api.v1.web_search import router as web_router
from alfred.api.v1.wikipedia import router as wikipedia_router
from alfred.core.config import settings

app = FastAPI(title="Alfred API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(rag_router)
app.include_router(notion_router)
app.include_router(gmail_router)
app.include_router(gmail_oauth_router)
app.include_router(calendar_router)
app.include_router(company_router)
app.include_router(web_router)
app.include_router(wikipedia_router)
