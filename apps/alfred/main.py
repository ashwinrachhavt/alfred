from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

from alfred.api import register_routes
from alfred.core import db_models  # noqa: F401 - ensure models are imported
from alfred.core.config import settings
from alfred.core.database import init_db

app = FastAPI(title="Alfred API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app)


@app.on_event("startup")
async def _startup() -> None:
    await init_db()
