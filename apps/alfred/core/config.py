import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings

# Load environment from project .env early so Settings can pick it up
try:  # optional dependency
    from dotenv import load_dotenv  # type: ignore

    _ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_ENV_PATH)
except Exception:
    pass

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "alfred.db"


class Settings(BaseSettings):
    app_env: str = Field(default="dev", alias="APP_ENV")
    secret_key: str = Field(default="dev", alias="SECRET_KEY")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    python_dont_write_bytecode: bool = Field(default=True, alias="PYTHONDONTWRITEBYTECODE")

    airtable_api_key: Optional[str] = Field(default=None, alias="AIRTABLE_API_KEY")

    notion_token: str | None = Field(default=None, alias="NOTION_TOKEN")
    notion_parent_page_id: str | None = Field(default=None, alias="NOTION_PARENT_PAGE_ID")
    notion_clients_db_id: str | None = Field(default=None, alias="NOTION_CLIENTS_DB_ID")
    notion_notes_db_id: str | None = Field(default=None, alias="NOTION_NOTES_DB_ID")

    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="alfred_docs", alias="QDRANT_COLLECTION")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-mini", alias="OPENAI_MODEL")

    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[AnyHttpUrl] = Field(default=None, alias="GOOGLE_REDIRECT_URI")
    google_project_id: Optional[str] = Field(default=None, alias="GOOGLE_PROJECT_ID")
    google_scopes: list[str] = Field(
        default=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.metadata",
        ],
        alias="GOOGLE_SCOPES",
    )
    gcp_pubsub_topic: Optional[str] = Field(default=None, alias="GCP_PUBSUB_TOPIC")
    token_store_dir: str = Field(default=".alfred_data/tokens", alias="TOKEN_STORE_DIR")
    enable_gmail: bool = Field(default=False, alias="ENABLE_GMAIL")

    cors_allow_origins: list[str] = Field(default=["*"], alias="CORS_ALLOW_ORIGINS")

    gmail_push_oidc_audience: Optional[str] = Field(default=None, alias="GMAIL_PUSH_OIDC_AUDIENCE")

    enable_mcp: bool = True
    mcp_filesystem_path: str = "./data"
    enable_mcp_browser: bool = True
    enable_mcp_everything: bool = False

    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-sonnet-20240229"

    whatsapp_api_key: Optional[str] = None
    whatsapp_phone: Optional[str] = None

    mcp_timeout: int = 30
    mcp_max_retries: int = 3

    openweb_ninja_api_key: Optional[str] = Field(default=None, alias="OPENWEB_NINJA_API_KEY")
    openweb_ninja_base_url: str = Field(
        default="https://api.openwebninja.com/realtime-glassdoor-data",
        alias="OPENWEB_NINJA_BASE_URL",
    )
    # Backward-compat: some environments use this alternate key name
    openweb_ninja_glassdoor_api_key: Optional[str] = Field(
        default=None,
        alias="OPENWEBNINJA_GLASSDOOR_API_KEY",
    )

    langsearch_api_key: Optional[str] = Field(default=None, alias="LANGSEARCH_API_KEY")
    langsearch_base_url: str = Field(
        default="https://api.langsearch.com/v1/web-search",
        alias="LANGSEARCH_BASE_URL",
    )
    langsearch_rerank_url: Optional[str] = Field(
        default="https://api.langsearch.com/v1/semantic-rerank",
        alias="LANGSEARCH_RERANK_URL",
    )
    langsearch_db_path: str = Field(
        default=".alfred_data/langsearch.json",
        alias="LANGSEARCH_DB_PATH",
    )

    # Langfuse (observability)
    langfuse_public_key: Optional[str] = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: Optional[str] = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: Optional[str] = Field(default=None, alias="LANGFUSE_HOST")
    langfuse_debug: bool = Field(default=False, alias="LANGFUSE_DEBUG")
    langfuse_tracing_enabled: bool = Field(default=True, alias="LANGFUSE_TRACING_ENABLED")

    # Connectors (misc)
    linear_api_key: str | None = Field(default=None, alias="LINEAR_API_KEY")
    slack_api_key: str | None = Field(default=None, alias="SLACK_API_KEY")

    database_url: str = Field(
        default=f"sqlite:///{DEFAULT_DB_PATH}",
        alias="DATABASE_URL",
    )

    mongo_uri: str = Field(default="mongodb://localhost:27017", alias="MONGO_URI")
    mongo_database: str = Field(default="notes_db", alias="MONGO_DATABASE")
    mongo_app_name: str = Field(default="notes_db", alias="MONGO_APP_NAME")

    firecrawl_base_url: str = Field(default="http://localhost:8010", alias="FIRECRAWL_BASE_URL")
    firecrawl_timeout: int = Field(default=30, alias="FIRECRAWL_TIMEOUT")
    company_research_model: str = Field(default="gpt-5.1", alias="COMPANY_RESEARCH_MODEL")
    company_research_collection: str = Field(
        default="company_research_reports",
        alias="COMPANY_RESEARCH_COLLECTION",
    )

    calendar_slot_duration_minutes: int = Field(
        default=30,
        alias="CALENDAR_SLOT_DURATION_MINUTES",
        ge=1,
    )
    calendar_working_hours_start: int = Field(
        default=9,
        alias="CALENDAR_WORKING_HOURS_START",
        ge=0,
        le=23,
    )
    calendar_working_hours_end: int = Field(
        default=18,
        alias="CALENDAR_WORKING_HOURS_END",
        ge=0,
        le=23,
    )
    calendar_organizer_email: str | None = Field(
        default=None,
        alias="CALENDAR_ORGANIZER_EMAIL",
    )


class Config:
    env_file = "apps/alfred/.env"
    extra = "ignore"


settings = Settings()

if settings.python_dont_write_bytecode:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
