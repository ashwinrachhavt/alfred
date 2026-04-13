from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import AsyncOpenAI

from .settings import LLMProvider, settings


@lru_cache(maxsize=8)
def get_chat_model(
    provider: LLMProvider | None = None,
    model: str | None = None,
) -> BaseChatModel:
    cfg = settings
    provider = provider or cfg.llm_provider
    model = model or cfg.llm_model
    temperature = cfg.llm_temperature

    if provider == LLMProvider.openai:
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=(cfg.openai_api_key.get_secret_value() if cfg.openai_api_key else None),
            base_url=cfg.openai_base_url,
            organization=cfg.openai_organization,
        )

    if provider == LLMProvider.ollama:
        return ChatOllama(
            model=model or cfg.ollama_chat_model,
            temperature=temperature,
            base_url=cfg.ollama_base_url,
        )

    raise ValueError(f"Unsupported provider: {provider}")


# Safe as singleton: FastAPI uses one event loop per uvicorn worker.
@lru_cache(maxsize=1)
def get_async_openai_client() -> AsyncOpenAI:
    """Cached AsyncOpenAI client for direct API usage (streaming, reasoning models)."""
    cfg = settings
    kwargs: dict[str, object] = {}
    if cfg.openai_api_key:
        val = cfg.openai_api_key.get_secret_value()
        if val:
            kwargs["api_key"] = val
    if cfg.openai_base_url:
        kwargs["base_url"] = cfg.openai_base_url
    if cfg.openai_organization:
        kwargs["organization"] = cfg.openai_organization
    return AsyncOpenAI(**kwargs)


@lru_cache(maxsize=8)
def get_embedding_model(
    provider: LLMProvider | None = None,
    model: str | None = None,
) -> Embeddings:
    cfg = settings
    provider = provider or cfg.llm_provider

    if provider == LLMProvider.openai:
        return OpenAIEmbeddings(
            model=model or "text-embedding-3-small",
            api_key=(cfg.openai_api_key.get_secret_value() if cfg.openai_api_key else None),
            base_url=cfg.openai_base_url,
        )

    if provider == LLMProvider.ollama:
        return OllamaEmbeddings(
            model=model or cfg.ollama_embed_model,
            base_url=cfg.ollama_base_url,
        )

    raise ValueError(f"Unsupported provider: {provider}")
