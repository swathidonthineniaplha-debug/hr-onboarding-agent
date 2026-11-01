"""LLM provider backed by Azure OpenAI (including models deployed via Microsoft Foundry).

All connection details are passed in from Settings, which reads them from
environment variables. Nothing is called until complete() is used.
"""

from __future__ import annotations

from typing import Any

import openai
from openai import AzureOpenAI

from .base import LLMClient, LLMError, LLMRequest


class AzureOpenAIClient(LLMClient):
    name = "azure_openai"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str,
        temperature: float | None = None,
    ) -> None:
        self._client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)
        self._deployment = deployment
        self._temperature = temperature

    def complete(self, request: LLMRequest) -> str:
        options: dict[str, Any] = {}
        if self._temperature is not None:
            options["temperature"] = self._temperature
        try:
            response = self._client.chat.completions.create(
                model=self._deployment,  # Azure routes by deployment name
                messages=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user_message()},
                ],
                response_format={"type": "json_object"},  # JSON mode
                **options,
            )
        except openai.APIError as exc:  # the SDK has already retried 429/5xx
            raise LLMError(f"Azure OpenAI request failed: {exc}") from exc
        # Empty content (e.g. content filter) flows on as invalid JSON and is retried.
        return response.choices[0].message.content or ""
