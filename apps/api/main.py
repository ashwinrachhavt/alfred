from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    # Load .env early so routers can access API keys at import
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from alfred_app.api.v1.company import router as company_router
from alfred_app.api.v1.gmail_status import router as gmail_router
from alfred_app.api.v1.health import router as health_router
from alfred_app.api.v1.notion import router as notion_router
from alfred_app.api.v1.rag import router as rag_router
from alfred_app.core.config import settings

app = FastAPI(title="Alfred API")

# CORS (dev-friendly defaults; configure via CORS_ALLOW_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# v1 routes
app.include_router(health_router)
app.include_router(rag_router)
app.include_router(notion_router)
app.include_router(gmail_router)
app.include_router(company_router)
