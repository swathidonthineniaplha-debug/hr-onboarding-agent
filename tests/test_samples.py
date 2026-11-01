"""End-to-end: run every sample document through the pipeline with the mock LLM."""

from datetime import date
from pathlib import Path

import pytest

from hr_onboarding.llm.mock_provider import MockLLMClient
from hr_onboarding.pipeline import process_document

SAMPLES = Path(__file__).resolve().parent.parent / "sample_documents"
TODAY = date(2026, 11, 1)

EXPECTED = {
    # file: (category, person_key, status)
    "passport_alex_example.txt": ("Passport", "alex-example", "Processed"),
    "passport_jordan_placeholder.pdf": ("Passport", "jordan-placeholder", "Processed"),
    "driving_licence_alex_example.pdf": ("DrivingLicence", "alex-example", "Processed"),
    "driving_licence_jordan_placeholder.txt": ("DrivingLicence", "jordan-placeholder", "Processed"),
    "employee_alex_example.txt": ("EmployeeDocument", "alex-example", "NeedsReview"),
    "employee_jordan_placeholder.pdf": ("EmployeeDocument", "jordan-placeholder", "NeedsReview"),
    "ambiguous_note.txt": ("Other", "unknown", "NeedsReview"),
}


def run(filename: str):
    return process_document(filename, (SAMPLES / filename).read_bytes(), MockLLMClient(), TODAY)


@pytest.mark.parametrize("filename", EXPECTED)
def test_sample_outcome(filename):
    category, person_key, status = EXPECTED[filename]
    result = run(filename)
    assert (result.category.value, result.person_key, result.status.value) == (category, person_key, status)


def test_alex_form_flags_age_mismatch():
    result = run("employee_alex_example.txt")
    assert result.issues == ["Stated age 31 does not match age 36 calculated from date of birth 1990-04-12"]
    assert len(result.extraction.previous_employment) == 2


def test_jordan_letter_flags_missing_right_to_work():
    result = run("employee_jordan_placeholder.pdf")
    assert result.issues == ["Missing required fields: right_to_work_status"]
    assert result.extraction.stated_age == 41  # read from "aged 41" in the prose
    # Expected in mock mode: the rule-based mock can't read employment history
    # written as sentences, so this list is empty. A real LLM should return both
    # jobs (Mock Retail Group and Testbridge Services Ltd) - see README "Mock vs real LLM".
    assert result.extraction.previous_employment == []


def test_ambiguous_note_is_low_confidence():
    result = run("ambiguous_note.txt")
    assert result.confidence < 0.8
