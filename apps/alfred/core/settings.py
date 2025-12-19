from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "alfred.db"


class LLMProvider(str, Enum):
    openai = "openai"
    ollama = "ollama"


class Settings(BaseSettings):
    """Unified application settings for Alfred.

    Loads from env with support for repo ".env" files. Avoids manual load_dotenv().
    """

    _app_env = (os.getenv("APP_ENV") or "").strip().lower()
    _env_files = (
        []
        if _app_env in {"test", "ci"}
        else [
            str((Path(__file__).resolve().parents[1] / ".env")),  # apps/alfred/.env
            str((Path(__file__).resolve().parents[3] / ".env")),  # repo root .env
        ]
    )

    # Load env vars from apps/alfred/.env first, then repo root .env
    model_config = SettingsConfigDict(
        env_file=_env_files,
        case_sensitive=False,
        extra="ignore",
    )

    # --- App / Core ---
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_name: str = Field(default="alfred", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    # Logging
    log_level: str | None = Field(default=None, alias="ALFRED_LOG_LEVEL")
    log_level_fallback: str | None = Field(default=None, alias="LOG_LEVEL")

    secret_key: SecretStr | None = Field(default=None, alias="SECRET_KEY")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    python_dont_write_bytecode: bool = Field(default=True, alias="PYTHONDONTWRITEBYTECODE")

    cors_allow_origins: list[str] = Field(default=["*"], alias="CORS_ALLOW_ORIGINS")

    # --- Integrations ---
    airtable_api_key: Optional[str] = Field(default=None, alias="AIRTABLE_API_KEY")

    # Notion
    notion_token: SecretStr | None = Field(default=None, alias="NOTION_TOKEN")
    notion_parent_page_id: str | None = Field(default=None, alias="NOTION_PARENT_PAGE_ID")
    notion_clients_db_id: str | None = Field(default=None, alias="NOTION_CLIENTS_DB_ID")
    notion_notes_db_id: str | None = Field(default=None, alias="NOTION_NOTES_DB_ID")

    # Qdrant
    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: SecretStr | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="alfred_docs", alias="QDRANT_COLLECTION")

    # OpenAI (also used by downstream libs)
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-mini", alias="OPENAI_MODEL")
    openai_base_url: Optional[str] = Field(default=None, alias="OPENAI_BASE_URL")
    openai_organization: Optional[str] = Field(default=None, alias="OPENAI_ORG")

    # Google / Gmail
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

    gmail_push_oidc_audience: Optional[str] = Field(default=None, alias="GMAIL_PUSH_OIDC_AUDIENCE")

    # MCP / tools
    enable_mcp: bool = True
    mcp_filesystem_path: str = "./data"
    enable_mcp_browser: bool = True
    enable_mcp_everything: bool = False

    # Anthropic (optional)
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-3-sonnet-20240229"

    # Misc
    whatsapp_api_key: Optional[str] = None
    whatsapp_phone: Optional[str] = None

    mcp_timeout: int = 30
    mcp_max_retries: int = 3

    # OpenWeb Ninja / Glassdoor connector
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

    # LangSearch
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
    langfuse_secret_key: SecretStr | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: Optional[str] = Field(default=None, alias="LANGFUSE_HOST")
    langfuse_debug: bool = Field(default=False, alias="LANGFUSE_DEBUG")
    langfuse_tracing_enabled: bool = Field(default=True, alias="LANGFUSE_TRACING_ENABLED")
    # Observability (MLflow)
    observability_backend: str | None = Field(default=None, alias="OBSERVABILITY_BACKEND")
    mlflow_tracking_uri: str = Field(default="http://localhost:5000", alias="MLFLOW_TRACKING_URI")
    mlflow_experiment_name: str = Field(default="alfred", alias="MLFLOW_EXPERIMENT_NAME")
    mlflow_run_name_prefix: str = Field(default="", alias="MLFLOW_RUN_NAME_PREFIX")

    # Connectors (misc)
    linear_api_key: SecretStr | None = Field(default=None, alias="LINEAR_API_KEY")
    slack_api_key: SecretStr | None = Field(default=None, alias="SLACK_API_KEY")

    # Database
    database_url: str = Field(
        default=f"sqlite:///{DEFAULT_DB_PATH}",
        alias="DATABASE_URL",
    )

    # MongoDB
    mongo_uri: str = Field(default="mongodb://localhost:27017", alias="MONGO_URI")
    mongo_database: str = Field(default="notes_db", alias="MONGO_DATABASE")
    mongo_app_name: str = Field(default="notes_db", alias="MONGO_APP_NAME")

    # Firecrawl
    firecrawl_base_url: str = Field(default="http://localhost:8010", alias="FIRECRAWL_BASE_URL")
    firecrawl_timeout: int = Field(default=30, alias="FIRECRAWL_TIMEOUT")
    company_research_model: str = Field(default="gpt-5.1", alias="COMPANY_RESEARCH_MODEL")
    company_research_collection: str = Field(
        default="company_research_reports",
        alias="COMPANY_RESEARCH_COLLECTION",
    )

    # Text cleaning
    text_cleaning_strategy: str = Field(default="basic", alias="TEXT_CLEANING_STRATEGY")
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

    # Calendar defaults
    calendar_slot_duration_minutes: int = Field(
        default=30, alias="CALENDAR_SLOT_DURATION_MINUTES", ge=1
    )
    calendar_working_hours_start: int = Field(
        default=9, alias="CALENDAR_WORKING_HOURS_START", ge=0, le=23
    )
    calendar_working_hours_end: int = Field(
        default=18, alias="CALENDAR_WORKING_HOURS_END", ge=0, le=23
    )
    calendar_organizer_email: str | None = Field(default=None, alias="CALENDAR_ORGANIZER_EMAIL")

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

    # --- LLM unified ---
    llm_provider: LLMProvider = Field(default=LLMProvider.openai, alias="ALFRED_LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4.1-mini", alias="ALFRED_LLM_MODEL")
    llm_temperature: float = Field(default=0.2, alias="ALFRED_LLM_TEMPERATURE")

    # Ollama specifics
    ollama_base_url: str = Field(default="http://localhost:11434", alias="ALFRED_OLLAMA_BASE_URL")
    ollama_chat_model: str = Field(default="llama3.2", alias="ALFRED_OLLAMA_CHAT_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="ALFRED_OLLAMA_EMBED_MODEL")

    # Search providers / connectors
    brave_search_api_key: str | None = Field(default=None, alias="BRAVE_SEARCH_API_KEY")
    exa_api_key: str | None = Field(default=None, alias="EXA_API_KEY")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    ydc_api_key: str | None = Field(default=None, alias="YDC_API_KEY")
    searxng_host: str | None = Field(default=None, alias="SEARXNG_HOST")
    searx_host: str | None = Field(default=None, alias="SEARX_HOST")
    user_agent: str = Field(
        default="Mozilla/5.0 (compatible; AlfredBot/1.0; +https://github.com/alfred)",
        alias="USER_AGENT",
    )
    # Scripts / utilities
    recursive_depth: int = Field(default=0, alias="RECURSIVE_DEPTH")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Convenience singleton for modules still expecting a module-level "settings"
settings = get_settings()
