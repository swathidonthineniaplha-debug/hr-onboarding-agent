"""Tests for employee extraction, validation rules and the pipeline around them."""

import json
from datetime import date

from hr_onboarding.extraction import extract_employee_data, validate_extraction
from hr_onboarding.models import EmployeeExtraction, ProcessingStatus
from hr_onboarding.pipeline import process_document
from tests.fakes import FakeLLM

TODAY = date(2026, 11, 1)

GOOD_RECORD = {
    "full_name": "Alex Example",
    "date_of_birth": "1990-04-12",
    "stated_age": 36,
    "right_to_work_status": "British citizen",
    "right_to_work_expiry": None,
    "previous_employment": [
        {"company": "Example Widgets Ltd", "job_title": "Analyst", "start_date": "2019-01",
         "end_date": "2022-06", "referee_name": "Sam Referee", "referee_contact": "sam@example.com"}
    ],
}


def record(**changes) -> EmployeeExtraction:
    return EmployeeExtraction.model_validate({**GOOD_RECORD, **changes})


# --- Pydantic validation of the LLM reply ---------------------------------

def test_valid_extraction_is_parsed():
    data = extract_employee_data(FakeLLM(json.dumps(GOOD_RECORD)), "doc")
    assert data.date_of_birth == date(1990, 4, 12)
    assert data.previous_employment[0].company == "Example Widgets Ltd"


def test_invalid_json_is_retried_once():
    llm = FakeLLM('{"full_name": "Alex Exa', json.dumps(GOOD_RECORD))  # truncated, then OK
    assert extract_employee_data(llm, "doc").full_name == "Alex Example"
    assert len(llm.requests) == 2


def test_non_iso_date_fails_validation():
    bad = json.dumps({**GOOD_RECORD, "date_of_birth": "12/04/1990"})
    llm = FakeLLM(bad, json.dumps(GOOD_RECORD))
    extract_employee_data(llm, "doc")
    assert "date_of_birth" in llm.requests[1].feedback


# --- Business rules --------------------------------------------------------

def test_clean_record_has_no_issues():
    assert validate_extraction(record(), TODAY) == []


def test_missing_required_fields_are_listed():
    issues = validate_extraction(record(right_to_work_status=None, stated_age=None), TODAY)
    assert issues == ["Missing required fields: stated_age, right_to_work_status"]


def test_expired_right_to_work_is_flagged():
    data = record(right_to_work_status="Skilled Worker visa", right_to_work_expiry="2026-10-31")
    assert validate_extraction(data, TODAY) == ["Right to work expired on 2026-10-31"]


def test_visa_without_expiry_is_flagged():
    issues = validate_extraction(record(right_to_work_status="Skilled Worker visa"), TODAY)
    assert issues == ["Right to work status looks time-limited but has no expiry date"]


def test_indefinite_leave_to_remain_needs_no_expiry():
    assert validate_extraction(record(right_to_work_status="Indefinite Leave to Remain"), TODAY) == []


# --- Pipeline status -------------------------------------------------------

def employee_llm(*extraction_replies: str, confidence: float = 0.9) -> FakeLLM:
    return FakeLLM(
        json.dumps({"category": "EmployeeDocument", "confidence": confidence, "reason": "form"}),
        '{"full_name": "Alex Example"}',
        *extraction_replies,
    )


def test_pipeline_processes_clean_employee_document():
    result = process_document("form.txt", b"doc", employee_llm(json.dumps(GOOD_RECORD)), TODAY)
    assert result.status is ProcessingStatus.PROCESSED
    assert result.calculated_age == 36


def test_pipeline_skips_extraction_below_confidence_threshold():
    llm = employee_llm(confidence=0.7)
    result = process_document("form.txt", b"doc", llm, TODAY)
    assert result.status is ProcessingStatus.NEEDS_REVIEW
    assert result.extraction is None
    assert len(llm.requests) == 2  # classify + name only


def test_pipeline_flags_extraction_that_never_validates():
    result = process_document("form.txt", b"doc", employee_llm("nope", "still nope"), TODAY)
    assert result.status is ProcessingStatus.NEEDS_REVIEW
    assert result.issues[0].startswith("Extraction failed")
