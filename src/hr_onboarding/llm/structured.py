"""Ask an LLM for JSON, validate it with Pydantic, and retry once if invalid."""

from __future__ import annotations

import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .base import LLMClient, LLMError, LLMRequest, LLMTask

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Models sometimes wrap JSON in ```json ... ``` despite being told not to.
_CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class StructuredOutputError(LLMError):
    """Raised when the model never returns valid JSON for the schema."""


def request_json(
    llm: LLMClient,
    task: LLMTask,
    system: str,
    document: str,
    schema: type[T],
    max_attempts: int = 2,
) -> T:
    feedback: str | None = None
    for attempt in range(1, max_attempts + 1):
        raw = llm.complete(LLMRequest(task, system, document, feedback))
        match = _CODE_FENCE.match(raw)
        try:
            # model_validate_json covers both bad JSON and wrong fields/types.
            return schema.model_validate_json(match.group(1) if match else raw)
        except ValidationError as exc:
            feedback = _summarise(exc)
            logger.warning("%s attempt %d/%d invalid: %s", task.value, attempt, max_attempts, feedback)
    raise StructuredOutputError(f"{task.value}: no valid JSON after {max_attempts} attempts ({feedback})")


def _summarise(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(p) for p in error["loc"])
        parts.append(f"{location}: {error['msg']}" if location else error["msg"])
    return "; ".join(parts)
