"""Uses the LLM to pull employee fields out of a document."""

from __future__ import annotations

from ..llm import LLMClient, LLMTask, request_json
from ..models import EmployeeExtraction
from ..prompts import EXTRACT_SYSTEM


def extract_employee_data(llm: LLMClient, text: str) -> EmployeeExtraction:
    return request_json(llm, LLMTask.EXTRACT, EXTRACT_SYSTEM, text, EmployeeExtraction)
