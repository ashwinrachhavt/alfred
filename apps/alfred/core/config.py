# apps/api/alfred_app/core/config.py
from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = Field(default="dev", alias="APP_ENV")
    secret_key: str = Field(default="dev", alias="SECRET_KEY")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Make these optional for local boot
    notion_token: str | None = Field(default=None, alias="NOTION_TOKEN")
    notion_parent_page_id: str | None = Field(default=None, alias="NOTION_PARENT_PAGE_ID")
    notion_clients_db_id: str | None = Field(default=None, alias="NOTION_CLIENTS_DB_ID")
    notion_notes_db_id: str | None = Field(default=None, alias="NOTION_NOTES_DB_ID")

    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="alfred_docs", alias="QDRANT_COLLECTION")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Google / Gmail integration
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

    # Web/CORS
    cors_allow_origins: list[str] = Field(default=["*"], alias="CORS_ALLOW_ORIGINS")

    # Security for Gmail push (Pub/Sub OIDC)
    gmail_push_oidc_audience: Optional[str] = Field(default=None, alias="GMAIL_PUSH_OIDC_AUDIENCE")

    enable_mcp: bool = True
    mcp_filesystem_path: str = "./data"
    enable_mcp_browser: bool = True
    enable_mcp_everything: bool = False  # For testing only

    # Optional additional model keys
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-sonnet-20240229"

    # WhatsApp MCP (if you have a custom server)
    whatsapp_api_key: Optional[str] = None
    whatsapp_phone: Optional[str] = None

    # MCP Server Timeouts
    mcp_timeout: int = 30
    mcp_max_retries: int = 3

    # Supabase will be used via API key + client later; no DB config here

    class Config:
        # Prefer repo-local env when running from project root
        env_file = "apps/alfred/.env"
        extra = "ignore"


settings = Settings()
