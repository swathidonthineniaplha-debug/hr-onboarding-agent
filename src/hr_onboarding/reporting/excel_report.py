"""Builds the Excel summary report.

build_report() returns bytes, so the caller decides where it goes:
a local file (save_report_locally) or the "reports" container (save_report_to_blob).
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ..routing import REPORTS
from ..service import ProcessedDocument
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


def build_report(documents: Sequence[ProcessedDocument]) -> bytes:
    workbook = Workbook()

    classification = workbook.active
    classification.title = "Classification"
    _write_sheet(classification, CLASSIFICATION_COLUMNS, (
        [d.result.source_file, d.result.category.value if d.result.category else None,
         d.result.confidence, d.result.reason, d.result.person_key, d.result.status.value,
         "; ".join(d.result.issues), d.location]
        for d in documents
    ))

    employee_rows = [d.employee_row for d in documents if d.employee_row]
    _write_sheet(workbook.create_sheet("EmployeeData"), EMPLOYEE_COLUMNS, (
        [row[column] for column in EMPLOYEE_COLUMNS] for row in employee_rows
    ))

    _write_sheet(workbook.create_sheet("PreviousEmployment"), EMPLOYMENT_COLUMNS, (
        [row["PersonKey"], row["FileName"], job["company"], job["job_title"], job["start_date"],
         job["end_date"], job["referee_name"], job["referee_contact"]]
        for row in employee_rows
        for job in json.loads(row["PreviousEmploymentJson"])
    ))

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def save_report_locally(report: bytes, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / LOCAL_REPORT_NAME
    path.write_bytes(report)
    return path


def save_report_to_blob(report: bytes, blobs: BlobStore, now: datetime) -> str:
    name = f"onboarding_results_{now:%Y%m%dT%H%M%SZ}.xlsx"
    blobs.upload(REPORTS, name, report)
    return name


def _write_sheet(sheet: Worksheet, headers: list[str], rows: Iterable[list[Any]]) -> None:
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"  # header stays visible while scrolling
    sheet.auto_filter.ref = sheet.dimensions

    for index, column in enumerate(sheet.iter_cols(values_only=True), start=1):
        longest = max(len(_display(value)) for value in column)
        sheet.column_dimensions[get_column_letter(index)].width = min(longest + 2, MAX_COLUMN_WIDTH)


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)
