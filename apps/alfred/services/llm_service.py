from __future__ import annotations

import os
from typing import Iterable, Optional, Type, TypeVar

from dotenv import load_dotenv
from ollama import chat as ollama_chat
from openai import OpenAI
from pydantic import BaseModel

from alfred.core.llm_config import LLMProvider, settings

# Ensure local .env is loaded for OPENAI_ and related envs
load_dotenv()

T = TypeVar("T", bound=BaseModel)


class LLMService:
    """
    Unified LLM access for Alfred.
    - Supports OpenAI (cloud) and Ollama (local).
    - Chat, streaming, structured outputs (OpenAI).
    """

    def __init__(self) -> None:
        self.cfg = settings
        self._openai_client: Optional[OpenAI] = None

    # ---------- internal helpers ----------

    @property
    def openai_client(self) -> OpenAI:
        if self._openai_client is None:
            self._openai_client = OpenAI(
                api_key=self.cfg.openai_api_key or os.getenv("OPENAI_API_KEY"),
                base_url=self.cfg.openai_base_url or os.getenv("OPENAI_BASE_URL"),
                organization=self.cfg.openai_organization or os.getenv("OPENAI_ORG"),
            )
        return self._openai_client

    # ---------- Chat (simple text) ----------

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Non-streaming text response.
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        provider = provider or self.cfg.llm_provider
        model = model or self.cfg.llm_model
        temperature = temperature if temperature is not None else self.cfg.llm_temperature

        if provider == LLMProvider.openai:
            resp = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""

        if provider == LLMProvider.ollama:
            resp = ollama_chat(
                model=model or self.cfg.ollama_chat_model,
                messages=messages,
                stream=False,
            )
            return resp["message"]["content"]

        raise ValueError(f"Unsupported provider: {provider}")

    # ---------- Chat (streaming) ----------

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Iterable[str]:
        """
        Streaming text response generator.
        """
        provider = provider or self.cfg.llm_provider
        model = model or self.cfg.llm_model
        temperature = temperature if temperature is not None else self.cfg.llm_temperature

        if provider == LLMProvider.openai:
            stream = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        elif provider == LLMProvider.ollama:
            stream = ollama_chat(
                model=model or self.cfg.ollama_chat_model,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                yield chunk["message"]["content"]

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    # ---------- Structured outputs (OpenAI only) ----------

    def structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[T],
        *,
        model: Optional[str] = None,
    ) -> T:
        """
        Enforce a Pydantic schema using OpenAI's Structured Outputs / JSON Schema.
        NOTE: this uses OpenAI only; Ollama doesn't have equivalent strict JSON schema
        guarantees yet.
        """
        client = self.openai_client
        model_name = model or self.cfg.llm_model

        json_schema = schema.model_json_schema()

        # Recursively normalize all object schemas to be strict for OpenAI
        def _strictify(obj: object) -> None:
            if isinstance(obj, dict):
                t = obj.get("type")
                if t == "object":
                    obj.setdefault("type", "object")
                    # Disallow unknown keys
                    obj["additionalProperties"] = False
                    props = obj.get("properties")
                    if isinstance(props, dict):
                        # OpenAI expects 'required' listing all keys in properties
                        obj["required"] = list(props.keys())
                        # Recurse into nested properties
                        for v in props.values():
                            _strictify(v)
                # Recurse into common schema containers
                for key in ("items", "allOf", "anyOf", "oneOf", "$defs", "definitions"):
                    if key in obj:
                        val = obj[key]
                        if isinstance(val, list):
                            for it in val:
                                _strictify(it)
                        elif isinstance(val, dict):
                            _strictify(val)

        try:
            _strictify(json_schema)
        except Exception:
            # Best-effort; fallback to root-only strict settings
            try:
                if isinstance(json_schema, dict):
                    json_schema.setdefault("type", "object")
                    json_schema["additionalProperties"] = False
                    props = json_schema.get("properties")
                    if isinstance(props, dict):
                        json_schema["required"] = list(props.keys())
            except Exception:
                pass

        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": json_schema,
                    "strict": True,
                },
            },
        )
        raw = resp.choices[0].message.content
        return schema.model_validate_json(raw or "{}")
