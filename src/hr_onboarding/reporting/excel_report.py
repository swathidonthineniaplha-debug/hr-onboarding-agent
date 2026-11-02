"""Builds the Excel summary report from ClassificationResults and EmployeeData rows.

build_report() returns the workbook as bytes, so the caller decides where it goes:
a local file (save_report_locally) or the "reports" container (save_report_to_blob).
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ..routing import REPORTS
from ..storage import BlobStore
from ..storage.sql_repository import EMPLOYEE_COLUMNS

LOCAL_REPORT_NAME = "onboarding_results.xlsx"
CLASSIFICATION_COLUMNS = [
    "FileName", "Category", "Confidence", "Reason", "PersonKey", "Status", "Issues", "Location",
]
EMPLOYMENT_COLUMNS = [
    "PersonKey", "FileName", "Company", "JobTitle", "StartDate", "EndDate", "RefereeName", "RefereeContact",
]
MAX_COLUMN_WIDTH = 60


@dataclass
class Report:
    content: bytes  # .xlsx file
    row_counts: dict[str, int]  # data rows per sheet, header excluded


def build_report(
    classification_rows: Sequence[Mapping[str, Any]], employee_rows: Sequence[Mapping[str, Any]]
) -> Report:
    workbook = Workbook()
    counts: dict[str, int] = {}

    classification = workbook.active
    classification.title = "Classification"
    counts[classification.title] = _write_sheet(classification, CLASSIFICATION_COLUMNS, (
        [row[column] for column in CLASSIFICATION_COLUMNS] for row in classification_rows
    ))

    counts["EmployeeData"] = _write_sheet(workbook.create_sheet("EmployeeData"), EMPLOYEE_COLUMNS, (
        [row[column] for column in EMPLOYEE_COLUMNS] for row in employee_rows
    ))

    counts["PreviousEmployment"] = _write_sheet(workbook.create_sheet("PreviousEmployment"), EMPLOYMENT_COLUMNS, (
        [row["PersonKey"], row["FileName"], job["company"], job["job_title"], job["start_date"],
         job["end_date"], job["referee_name"], job["referee_contact"]]
        for row in employee_rows
        for job in json.loads(row["PreviousEmploymentJson"] or "[]")
    ))

    buffer = io.BytesIO()
    workbook.save(buffer)
    return Report(buffer.getvalue(), counts)


def save_report_locally(report: bytes, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / LOCAL_REPORT_NAME
    path.write_bytes(report)
    return path


def save_report_to_blob(report: bytes, blobs: BlobStore, now: datetime) -> str:
    name = f"onboarding_results_{now:%Y%m%dT%H%M%SZ}.xlsx"
    blobs.upload(REPORTS, name, report)
    return name


def _write_sheet(sheet: Worksheet, headers: list[str], rows: Iterable[list[Any]]) -> int:
    """Write a formatted sheet and return the number of data rows."""
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    count = 0
    for row in rows:
        sheet.append(row)
        count += 1
    sheet.freeze_panes = "A2"  # header stays visible while scrolling
    sheet.auto_filter.ref = sheet.dimensions

    for index, column in enumerate(sheet.iter_cols(values_only=True), start=1):
        longest = max(len(_display(value)) for value in column)
        sheet.column_dimensions[get_column_letter(index)].width = min(longest + 2, MAX_COLUMN_WIDTH)
    return count


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)
