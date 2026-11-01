"""Uses the LLM to decide what kind of document was uploaded."""

from __future__ import annotations

from ..llm import LLMClient, LLMTask, request_json
from ..models import Classification
from ..prompts import CLASSIFY_SYSTEM

# Below this, a person checks the document instead of the pipeline acting on it.
CONFIDENCE_THRESHOLD = 0.8


def classify_document(llm: LLMClient, text: str) -> Classification:
    return request_json(llm, LLMTask.CLASSIFY, CLASSIFY_SYSTEM, text, Classification)
