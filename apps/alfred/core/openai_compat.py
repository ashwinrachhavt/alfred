from __future__ import annotations

from typing import Any

_GPT5_MODEL_PREFIXES = ("gpt-5",)
_REASONING_MODEL_PREFIXES = ("o1", "o3", "o4")


def _normalized_model(model: str | None) -> str:
    return (model or "").strip().lower()


def is_reasoning_model(model: str | None) -> bool:
    normalized = _normalized_model(model)
    return normalized.startswith(_REASONING_MODEL_PREFIXES)


def uses_max_completion_tokens(model: str | None) -> bool:
    normalized = _normalized_model(model)
    return normalized.startswith(_GPT5_MODEL_PREFIXES) or is_reasoning_model(normalized)


def supports_custom_temperature(model: str | None) -> bool:
    normalized = _normalized_model(model)
    if not normalized:
        return True
    return not (normalized.startswith(_GPT5_MODEL_PREFIXES) or is_reasoning_model(normalized))


def add_temperature_if_supported(
    kwargs: dict[str, Any],
    *,
    model: str | None,
    temperature: float | None,
) -> None:
    if temperature is not None and supports_custom_temperature(model):
        kwargs["temperature"] = temperature
