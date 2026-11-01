"""Structured data extraction."""

from .extractor import extract_employee_data
from .validation import calculate_age, validate_extraction

__all__ = ["calculate_age", "extract_employee_data", "validate_extraction"]
