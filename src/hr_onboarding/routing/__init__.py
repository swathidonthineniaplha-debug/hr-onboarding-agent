"""Document routing."""

from .blob_router import (
    ALL_CONTAINERS,
    DRIVING_LICENCES,
    EMPLOYEE_DOCUMENTS,
    INCOMING,
    PASSPORTS,
    REPORTS,
    destination_container,
    destination_path,
    review_metadata,
)

__all__ = [
    "ALL_CONTAINERS",
    "DRIVING_LICENCES",
    "EMPLOYEE_DOCUMENTS",
    "INCOMING",
    "PASSPORTS",
    "REPORTS",
    "destination_container",
    "destination_path",
    "review_metadata",
]
