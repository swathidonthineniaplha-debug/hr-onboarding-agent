"""The factory picks the provider from config alone - no network calls are made."""

from hr_onboarding.config import Settings
from hr_onboarding.llm import create_llm_client
from hr_onboarding.llm.mock_provider import MockLLMClient


def test_default_is_mock():
    assert isinstance(create_llm_client(Settings.from_env({})), MockLLMClient)


def test_azure_openai_is_built_from_env_only():
    settings = Settings.from_env({
        "LLM_PROVIDER": "azure_openai",
        "AZURE_OPENAI_ENDPOINT": "https://fake-resource.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "fake-key",
        "AZURE_OPENAI_DEPLOYMENT": "fake-deployment",
    })
    client = create_llm_client(settings)
    assert client.name == "azure_openai"
    assert client._deployment == "fake-deployment"
    assert client._temperature is None  # not sent unless configured


def test_anthropic_is_built_from_env_only():
    settings = Settings.from_env({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "fake-key"})
    assert create_llm_client(settings).name == "anthropic"
