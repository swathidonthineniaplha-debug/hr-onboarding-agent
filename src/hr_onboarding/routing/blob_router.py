"""Decides which container and folder each processed document belongs in.

Passport        -> passports/<PersonKey>/<FileName>
DrivingLicence  -> driving-licences/<PersonKey>/<FileName>
EmployeeDocument -> employee-documents/<PersonKey>/<FileName>
Anything else (Other, low confidence, name not found) stays in incoming.
"""

from __future__ import annotations

import re

from ..classification import CONFIDENCE_THRESHOLD
from ..models import DocumentCategory, DocumentResult
from ..person_key import UNKNOWN_PERSON

INCOMING = "incoming"
PASSPORTS = "passports"
DRIVING_LICENCES = "driving-licences"
EMPLOYEE_DOCUMENTS = "employee-documents"
REPORTS = "reports"
ALL_CONTAINERS = (INCOMING, PASSPORTS, DRIVING_LICENCES, EMPLOYEE_DOCUMENTS, REPORTS)

_DESTINATIONS = {
    DocumentCategory.PASSPORT: PASSPORTS,
    DocumentCategory.DRIVING_LICENCE: DRIVING_LICENCES,
    DocumentCategory.EMPLOYEE_DOCUMENT: EMPLOYEE_DOCUMENTS,
}


def destination_container(result: DocumentResult) -> str | None:
    """Target container, or None if the document must stay in incoming for review."""
    if result.person_key == UNKNOWN_PERSON:
        return None
    if result.confidence is None or result.confidence < CONFIDENCE_THRESHOLD:
        return None
    return _DESTINATIONS.get(result.category)


def destination_path(result: DocumentResult) -> str:
    return f"{result.person_key}/{result.source_file}"


def review_metadata(result: DocumentResult) -> dict[str, str]:
    """Blob metadata marking a document left in incoming.

    Azure metadata values must be ASCII without line breaks, and are size-limited.
    """
    issues = "; ".join(result.issues) or "-"
    issues = re.sub(r"\s+", " ", issues.encode("ascii", "replace").decode())
    return {"status": result.status.value, "issues": issues[:1000]}
