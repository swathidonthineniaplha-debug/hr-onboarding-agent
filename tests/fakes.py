"""Test doubles."""

from hr_onboarding.llm import LLMClient, LLMRequest


class FakeLLM(LLMClient):
    """Returns scripted replies in order and records every request."""

    name = "fake"

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> str:
        self.requests.append(request)
        return self.replies.pop(0)
