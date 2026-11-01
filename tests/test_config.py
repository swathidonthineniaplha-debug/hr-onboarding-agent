"""Tests for settings loading and validation."""

import pytest

from hr_onboarding.config import ConfigError, LLMProvider, Settings


def test_defaults_to_mock_with_no_env():
    settings = Settings.from_env({})
    assert settings.llm_provider is LLMProvider.MOCK
    assert settings.blob_input_container == "onboarding-uploads"
    assert settings.sql_connection_string is None


def test_provider_is_case_insensitive():
    assert Settings.from_env({"LLM_PROVIDER": " Mock "}).llm_provider is LLMProvider.MOCK


def test_invalid_provider_rejected():
    with pytest.raises(ConfigError, match="invalid"):
        Settings.from_env({"LLM_PROVIDER": "gpt"})


def test_anthropic_requires_api_key():
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        Settings.from_env({"LLM_PROVIDER": "anthropic"})


def test_azure_openai_lists_all_missing_settings():
    with pytest.raises(ConfigError) as exc:
        Settings.from_env({"LLM_PROVIDER": "azure_openai", "AZURE_OPENAI_API_KEY": "fake"})
    assert "AZURE_OPENAI_ENDPOINT" in str(exc.value)
    assert "AZURE_OPENAI_DEPLOYMENT" in str(exc.value)


def test_secrets_hidden_from_repr():
    settings = Settings.from_env({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-fake-123"})
    assert "sk-fake-123" not in repr(settings)
