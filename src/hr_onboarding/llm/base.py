"""Common interface that every LLM provider implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class LLMTask(str, Enum):
    CLASSIFY = "classify"
    PERSON_NAME = "person_name"
    EXTRACT = "extract"


@dataclass(frozen=True)
class LLMRequest:
    # Real providers only use system + user_message(); the mock uses task
    # to pick which rule set to run.
    task: LLMTask
    system: str
    document: str
    feedback: str | None = None  # validation error from the previous attempt

    def user_message(self) -> str:
        message = f"<document>\n{self.document}\n</document>"
        if self.feedback:
            message += (
                f"\n\nYour previous reply was invalid: {self.feedback}\n"
                "Reply again with valid JSON only."
            )
        return message


class LLMError(RuntimeError):
    """Raised when a provider call fails (network, auth, quota...)."""


class LLMClient(ABC):
    name: str

    @abstractmethod
    def complete(self, request: LLMRequest) -> str:
        """Return the model's raw text reply (expected to be JSON)."""
