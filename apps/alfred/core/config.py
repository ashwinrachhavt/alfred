from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = Field(default="dev", alias="APP_ENV")
    secret_key: str = Field(default="dev", alias="SECRET_KEY")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

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

    class Config:
        env_file = "apps/alfred/.env"
        extra = "ignore"


settings = Settings()
