"""Data models shared across the pipeline (document types, employee records).

Pydantic validates every LLM reply against these models, so a malformed
answer is caught here instead of failing somewhere further down the line.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class DocumentCategory(str, Enum):
    PASSPORT = "Passport"
    DRIVING_LICENCE = "DrivingLicence"
    EMPLOYEE_DOCUMENT = "EmployeeDocument"
    OTHER = "Other"


class ProcessingStatus(str, Enum):
    PROCESSED = "Processed"
    NEEDS_REVIEW = "NeedsReview"


class Classification(BaseModel):
    category: DocumentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class PersonName(BaseModel):
    full_name: str | None = None


# Employment dates are often only month-precise, so YYYY-MM is allowed.
PARTIAL_DATE_PATTERN = r"^\d{4}-\d{2}(-\d{2})?$"


class PreviousEmployment(BaseModel):
    company: str | None = None
    job_title: str | None = None
    start_date: str | None = Field(default=None, pattern=PARTIAL_DATE_PATTERN)
    end_date: str | None = Field(default=None, pattern=PARTIAL_DATE_PATTERN)
    referee_name: str | None = None
    referee_contact: str | None = None


class EmployeeExtraction(BaseModel):
    # Fields are optional so a *missing* value becomes a review issue,
    # while a *malformed* value (e.g. "12/04/1990") fails validation.
    full_name: str | None = None
    date_of_birth: date | None = None
    stated_age: int | None = Field(default=None, ge=0, le=130)
    right_to_work_status: str | None = None
    right_to_work_expiry: date | None = None
    previous_employment: list[PreviousEmployment] = Field(default_factory=list)


class DocumentResult(BaseModel):
    source_file: str
    category: DocumentCategory | None
    confidence: float | None
    reason: str
    person_key: str
    status: ProcessingStatus
    issues: list[str] = Field(default_factory=list)
    extraction: EmployeeExtraction | None = None
    calculated_age: int | None = None
    age_mismatch: bool | None = None  # None when either age is unknown
