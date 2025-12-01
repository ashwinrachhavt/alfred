"""Unified LLM factory supporting both LangGraph and Agno models."""

from __future__ import annotations

from typing import Optional, Union

from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat

from .llm_config import LLMProvider, settings


def make_chat_model(
    backend: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Union[OpenAIChat, Ollama]:
    """
    Factory function to create an Agno chat model.

    Args:
        backend: 'openai' or 'ollama'. Defaults to settings.llm_provider.
        model_name: Model identifier. Defaults to settings.llm_model.
        temperature: Temperature for sampling. Defaults to settings.llm_temperature.

    Returns:
        An instance of OpenAIChat or Ollama.
    """
    backend = backend or settings.llm_provider.value
    model_name = model_name or settings.llm_model
    temperature = temperature if temperature is not None else settings.llm_temperature

    if backend == LLMProvider.openai.value:
        kwargs = {"id": model_name, "temperature": temperature}
        if settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        if settings.openai_organization:
            kwargs["organization"] = settings.openai_organization
        return OpenAIChat(**kwargs)

    elif backend == LLMProvider.ollama.value:
        kwargs = {
            "id": model_name or settings.ollama_chat_model,
            "options": {"temperature": temperature},
        }
        if settings.ollama_base_url:
            kwargs["host"] = settings.ollama_base_url
        return Ollama(**kwargs)

    else:
        raise ValueError(f"Unsupported backend: {backend}")
