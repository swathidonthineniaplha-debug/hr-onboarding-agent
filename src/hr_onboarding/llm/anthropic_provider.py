"""LLM provider backed by the Anthropic Claude API."""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from .base import LLMClient, LLMError, LLMRequest

logger = logging.getLogger(__name__)

# Models that support server-side refusal fallbacks ("fallbacks": "default").
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicClient(LLMClient):
    name = "anthropic"

    def __init__(self, *, api_key: str, model: str, max_tokens: int = 16000) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, request: LLMRequest) -> str:
        # No temperature: current Claude models reject sampling parameters.
        options: dict[str, Any] = {}
        if self._model in _FALLBACK_MODELS:
            # If a safety classifier declines, the API retries on a fallback model.
            options = {"betas": [_FALLBACK_BETA], "fallbacks": "default"}
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": request.user_message()}],
                **options,
            )
        except anthropic.APIError as exc:  # the SDK has already retried 429/5xx
            raise LLMError(f"Anthropic request failed: {exc}") from exc
        if response.stop_reason == "refusal":
            # Treated like an invalid reply: retried once, then flagged NeedsReview.
            logger.warning("Claude declined the %s request", request.task.value)
            return ""
        return "".join(block.text for block in response.content if block.type == "text")
