"""Builds the configured LLM provider from Settings."""

from __future__ import annotations

from ..config import LLMProvider, Settings
from .base import LLMClient
from .mock_provider import MockLLMClient


def create_llm_client(settings: Settings) -> LLMClient:
    # Real providers are imported only when selected, so mock mode never
    # loads the openai/anthropic SDKs.
    if settings.llm_provider is LLMProvider.AZURE_OPENAI:
        from .azure_openai_provider import AzureOpenAIClient

        return AzureOpenAIClient(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
            temperature=settings.azure_openai_temperature,
        )
    if settings.llm_provider is LLMProvider.ANTHROPIC:
        from .anthropic_provider import AnthropicClient

        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    return MockLLMClient()
