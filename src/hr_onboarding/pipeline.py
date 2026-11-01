"""Orchestrates the flow: read -> classify -> person key -> extract -> validate.

A document the pipeline can't be sure about is never dropped: it comes back as
NeedsReview with the reasons in `issues`. Provider failures (network, auth)
are not caught here, so the Azure Function can retry them.
"""

from __future__ import annotations

from datetime import date

from pypdf.errors import PdfReadError

from .classification import CONFIDENCE_THRESHOLD, classify_document
from .documents import UnsupportedDocumentError, extract_text
from .extraction import calculate_age, extract_employee_data, validate_extraction
from .llm import LLMClient, StructuredOutputError
from .models import DocumentCategory, DocumentResult, ProcessingStatus
from .person_key import UNKNOWN_PERSON, extract_person_key


def process_document(
    filename: str, content: bytes, llm: LLMClient, today: date | None = None
) -> DocumentResult:
    today = today or date.today()

    try:
        text = extract_text(filename, content)
    except (UnsupportedDocumentError, PdfReadError, UnicodeDecodeError) as exc:
        return _needs_review(filename, f"Could not read file: {exc}")
    if not text.strip():
        return _needs_review(filename, "File contains no readable text (scanned image?)")

    try:
        classification = classify_document(llm, text)
    except StructuredOutputError as exc:
        return _needs_review(filename, f"Classification failed: {exc}")

    issues: list[str] = []
    try:
        person_key = extract_person_key(llm, text)
    except StructuredOutputError as exc:
        person_key = UNKNOWN_PERSON
        issues.append(f"Name lookup failed: {exc}")
    else:
        if person_key == UNKNOWN_PERSON:
            issues.append("No full name found; person key is 'unknown'")

    extraction = None
    calculated_age = None
    if classification.confidence < CONFIDENCE_THRESHOLD:
        issues.append(
            f"Low classification confidence ({classification.confidence:.2f} < {CONFIDENCE_THRESHOLD})"
        )
    elif classification.category is DocumentCategory.OTHER:
        issues.append("Not a recognised onboarding document type")
    elif classification.category is DocumentCategory.EMPLOYEE_DOCUMENT:
        try:
            extraction = extract_employee_data(llm, text)
        except StructuredOutputError as exc:
            issues.append(f"Extraction failed: {exc}")
        else:
            issues.extend(validate_extraction(extraction, today))
            if extraction.date_of_birth:
                calculated_age = calculate_age(extraction.date_of_birth, today)

    return DocumentResult(
        source_file=filename,
        category=classification.category,
        confidence=classification.confidence,
        reason=classification.reason,
        person_key=person_key,
        status=ProcessingStatus.NEEDS_REVIEW if issues else ProcessingStatus.PROCESSED,
        issues=issues,
        extraction=extraction,
        calculated_age=calculated_age,
    )


def _needs_review(filename: str, issue: str) -> DocumentResult:
    return DocumentResult(
        source_file=filename,
        category=None,
        confidence=None,
        reason="Not classified",
        person_key=UNKNOWN_PERSON,
        status=ProcessingStatus.NEEDS_REVIEW,
        issues=[issue],
    )
