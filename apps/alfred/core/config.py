import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "alfred.db"

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load env vars from apps/alfred/.env first, then repo root .env
        env_file=[
            str((Path(__file__).resolve().parents[1] / ".env")),  # apps/alfred/.env
            str((Path(__file__).resolve().parents[3] / ".env")),  # repo root .env
        ],
        extra="ignore",
    )
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

    # Text cleaning
    text_cleaning_strategy: str = Field(
        default="basic", alias="TEXT_CLEANING_STRATEGY"
    )  # one of: basic, langextract, llm
    text_cleaning_langextract_model: str = Field(
        default="gpt-4o-mini", alias="TEXT_CLEANING_LANGEXTRACT_MODEL"
    )
    text_cleaning_langextract_passes: int = Field(
        default=1, alias="TEXT_CLEANING_LANGEXTRACT_PASSES", ge=1, le=5
    )
    text_cleaning_langextract_workers: int = Field(
        default=0, alias="TEXT_CLEANING_LANGEXTRACT_WORKERS", ge=0, le=64
    )  # 0 -> library default
    text_cleaning_langextract_char_buffer: int = Field(
        default=0, alias="TEXT_CLEANING_LANGEXTRACT_CHAR_BUFFER", ge=0, le=10000
    )  # 0 -> disabled, else e.g. 1000
    text_cleaning_model_url: str | None = Field(
        default=None, alias="TEXT_CLEANING_MODEL_URL"
    )  # e.g., Ollama http://localhost:11434

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

    # MongoDB Lens MCP
    mcp_server_url: Optional[str] = Field(default="http://localhost:8001", alias="MCP_SERVER_URL")
    mcp_database: Optional[str] = Field(default=None, alias="MCP_DATABASE")

    # Agent tracing (LangGraph reasoning trace)
    enable_agent_trace: bool = Field(default=False, alias="ENABLE_AGENT_TRACE")

    # Enrichment & graph (optional)
    enable_ingest_enrichment: bool = Field(default=False, alias="ENABLE_INGEST_ENRICHMENT")
    neo4j_uri: Optional[str] = Field(default=None, alias="NEO4J_URI")
    neo4j_user: Optional[str] = Field(default=None, alias="NEO4J_USER")
    neo4j_password: Optional[str] = Field(default=None, alias="NEO4J_PASSWORD")

    # Classification (taxonomy)
    enable_ingest_classification: bool = Field(default=False, alias="ENABLE_INGEST_CLASSIFICATION")
    classification_taxonomy_path: Optional[str] = Field(
        default=None, alias="CLASSIFICATION_TAXONOMY_PATH"
    )


settings = Settings()

if settings.python_dont_write_bytecode:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
