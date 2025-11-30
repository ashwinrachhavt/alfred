from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseSettings, Field


class LLMProvider(str, Enum):
    openai = "openai"
    ollama = "ollama"


class LLMSettings(BaseSettings):
    """
    Centralized LLM configuration controlled via environment variables.

    Defaults favor OpenAI for quality; override to Ollama for local dev.
    Env prefix: ALFRED_
    """

    # Global defaults
    llm_provider: LLMProvider = Field(
        default=LLMProvider.openai,
        description="Default provider if none specified.",
    )
    llm_model: str = Field(
        default="gpt-4.1-mini",
        description="Default chat model.",
    )
    llm_temperature: float = 0.2

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None  # override if using a proxy
    openai_organization: Optional[str] = None

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Default Ollama host on your Mac M3.",
    )
    ollama_chat_model: str = Field(
        default="llama3.2",
        description="Default local chat model (e.g., llama3.2, qwen2.5-coder).",
    )
    ollama_embed_model: str = Field(
        default="nomic-embed-text",
        description="Embedding model to use with Ollama.",
    )

    class Config:
        env_prefix = "ALFRED_"
        case_sensitive = False


settings = LLMSettings()

