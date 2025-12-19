from __future__ import annotations

import importlib.util
from typing import Iterable, Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from alfred.core.settings import LLMProvider, settings


def _get_ollama_chat():
    if importlib.util.find_spec("ollama") is None:
        return None
    from ollama import chat as ollama_chat  # type: ignore[import-not-found]

    return ollama_chat


T = TypeVar("T", bound=BaseModel)


class LLMService:
    """
    Unified LLM access for Alfred.
    - Supports OpenAI (cloud) and Ollama (local).
    - Chat, streaming, structured outputs (OpenAI).
    """

    def __init__(self, *, openai_client: Optional[OpenAI] = None) -> None:
        self.cfg = settings
        self._openai_client: Optional[OpenAI] = openai_client

    # ---------- internal helpers ----------

    @property
    def openai_client(self) -> OpenAI:
        if self._openai_client is None:
            kwargs: dict[str, object] = {}
            if getattr(self.cfg, "openai_api_key", None):
                val = self.cfg.openai_api_key.get_secret_value()  # type: ignore[union-attr]
                if val:
                    kwargs["api_key"] = val
            if getattr(self.cfg, "openai_base_url", None):
                kwargs["base_url"] = self.cfg.openai_base_url
            if getattr(self.cfg, "openai_organization", None):
                kwargs["organization"] = self.cfg.openai_organization
            self._openai_client = OpenAI(**kwargs)
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
            ollama_chat = _get_ollama_chat()
            if ollama_chat is None:
                raise RuntimeError("Ollama provider is not available (missing 'ollama' package)")
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
            ollama_chat = _get_ollama_chat()
            if ollama_chat is None:
                raise RuntimeError("Ollama provider is not available (missing 'ollama' package)")
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

        # Inline local $ref references because OpenAI structured outputs do not
        # accept $ref in the response_format schema.
        def _deref(obj: object, defs: dict[str, object]) -> object:
            if isinstance(obj, dict):
                # Replace local refs like #/$defs/Name
                if "$ref" in obj:
                    ref = obj["$ref"]
                    if isinstance(ref, str) and ref.startswith("#/$defs/"):
                        name = ref.split("/")[-1]
                        target = defs.get(name, {})
                        # Deep copy via recursion
                        return _deref(target, defs)
                # Recurse
                out: dict[str, object] = {}
                for k, v in obj.items():
                    out[k] = _deref(v, defs)
                return out
            if isinstance(obj, list):
                return [_deref(x, defs) for x in obj]
            return obj

        if isinstance(json_schema, dict):
            defs = {}
            for key in ("$defs", "definitions"):
                if isinstance(json_schema.get(key), dict):
                    defs = json_schema[key]  # type: ignore[assignment]
                    break
            if defs:
                json_schema = _deref(json_schema, defs)  # type: ignore[assignment]
                # Drop defs after inlining
                json_schema.pop("$defs", None)
                json_schema.pop("definitions", None)

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
            # Fall through to harden root below
            pass

        # Ensure root object is strict per OpenAI requirements
        if isinstance(json_schema, dict):
            # Some pydantic schemas use $ref at root; still enforce a strict object wrapper
            if json_schema.get("type") != "object":
                # Wrap in an object if needed
                props = (
                    json_schema.get("properties")
                    if isinstance(json_schema.get("properties"), dict)
                    else {}
                )
                json_schema["type"] = "object"
                if not props:
                    json_schema.setdefault("properties", {})
            json_schema["additionalProperties"] = False
            # If pydantic already provided 'required', keep it; otherwise default to listed properties
            if not json_schema.get("required") and isinstance(json_schema.get("properties"), dict):
                json_schema["required"] = list(json_schema["properties"].keys())

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
