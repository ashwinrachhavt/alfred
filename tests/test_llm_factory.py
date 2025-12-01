from unittest import mock

import pytest
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from alfred.core import llm as llm_module
from alfred.core.llm import make_chat_model


def test_make_chat_model_openai_explicit():
    model = make_chat_model(backend="openai", model_name="gpt-4o", temperature=0.5)
    assert isinstance(model, OpenAIChat)
    assert model.id == "gpt-4o"
    assert model.temperature == 0.5


def test_make_chat_model_ollama_explicit():
    model = make_chat_model(backend="ollama", model_name="llama3", temperature=0.1)
    assert isinstance(model, Ollama)
    assert model.id == "llama3"
    assert model.options["temperature"] == 0.1


def test_make_chat_model_defaults():
    # Patch the settings object
    with (
        mock.patch.object(llm_module.settings, "llm_provider") as mock_provider,
        mock.patch.object(llm_module.settings, "llm_model", "mistral"),
    ):
        mock_provider.value = "ollama"
        model = make_chat_model()
        assert isinstance(model, Ollama)
        assert model.id == "mistral"

    with (
        mock.patch.object(llm_module.settings, "llm_provider") as mock_provider,
        mock.patch.object(llm_module.settings, "llm_model", "gpt-3.5-turbo"),
    ):
        mock_provider.value = "openai"
        model = make_chat_model()
        assert isinstance(model, OpenAIChat)
        assert model.id == "gpt-3.5-turbo"


def test_invalid_backend():
    with pytest.raises(ValueError, match="Unsupported backend"):
        make_chat_model(backend="invalid")
