from __future__ import annotations

from functools import lru_cache
from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings

from .llm_config import LLMProvider, LLMSettings, settings


@lru_cache(maxsize=8)
def get_chat_model(
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """Return a LangChain-compatible chat model for the chosen provider.

    Cached to avoid reconnect / re-initialization overhead across agents.
    """
    cfg: LLMSettings = settings
    provider = provider or cfg.llm_provider
    temperature = temperature if temperature is not None else cfg.llm_temperature

    if provider == LLMProvider.openai:
        return ChatOpenAI(
            model=model or cfg.llm_model,
            temperature=temperature,
            api_key=cfg.openai_api_key,
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


@lru_cache(maxsize=8)
def get_embedding_model(
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
) -> Embeddings:
    """Return an Embeddings implementation for the chosen provider."""
    cfg: LLMSettings = settings
    provider = provider or cfg.llm_provider

    if provider == LLMProvider.openai:
        return OpenAIEmbeddings(
            model=model or "text-embedding-3-small",
            api_key=cfg.openai_api_key,
            base_url=cfg.openai_base_url,
        )

    if provider == LLMProvider.ollama:
        return OllamaEmbeddings(
            model=model or cfg.ollama_embed_model,
            base_url=cfg.ollama_base_url,
        )

    raise ValueError(f"Unsupported provider: {provider}")

