from __future__ import annotations

from alfred.core.openai_compat import (
    add_temperature_if_supported,
    supports_custom_temperature,
    uses_max_completion_tokens,
)


def test_gpt5_models_omit_custom_temperature_and_use_completion_token_limit() -> None:
    kwargs: dict[str, object] = {}

    add_temperature_if_supported(kwargs, model="gpt-5.5", temperature=0.2)

    assert kwargs == {}
    assert not supports_custom_temperature("gpt-5.5")
    assert uses_max_completion_tokens("gpt-5.5")


def test_reasoning_models_omit_custom_temperature_and_use_completion_token_limit() -> None:
    kwargs: dict[str, object] = {}

    add_temperature_if_supported(kwargs, model="o4-mini", temperature=0.2)

    assert kwargs == {}
    assert not supports_custom_temperature("o4-mini")
    assert uses_max_completion_tokens("o4-mini")


def test_standard_chat_models_keep_custom_temperature_and_max_tokens() -> None:
    kwargs: dict[str, object] = {}

    add_temperature_if_supported(kwargs, model="gpt-4o", temperature=0.2)

    assert kwargs == {"temperature": 0.2}
    assert supports_custom_temperature("gpt-4o")
    assert not uses_max_completion_tokens("gpt-4o")
