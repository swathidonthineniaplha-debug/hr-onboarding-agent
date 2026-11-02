"""Excel report: sheets, headers, formatting and contents."""

import io
from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook

from hr_onboarding.reporting import build_report, save_report_locally, save_report_to_blob
from hr_onboarding.routing import INCOMING, REPORTS

SAMPLES = Path(__file__).resolve().parent.parent / "sample_documents"


@pytest.fixture
def workbook(blobs, service):
    for path in SAMPLES.iterdir():
        if path.suffix in {".txt", ".pdf"}:
            blobs.upload(INCOMING, path.name, path.read_bytes())
    report = build_report(service.process_all_incoming())
    return load_workbook(io.BytesIO(report))


def test_has_three_sheets(workbook):
    assert workbook.sheetnames == ["Classification", "EmployeeData", "PreviousEmployment"]


@pytest.mark.parametrize("sheet", ["Classification", "EmployeeData", "PreviousEmployment"])
def test_headers_are_bold_and_frozen(workbook, sheet):
    ws = workbook[sheet]
    assert all(cell.font.bold for cell in ws[1])
    assert ws.freeze_panes == "A2"


def test_column_widths_fit_content(workbook):
    ws = workbook["Classification"]
    widths = {ws.cell(1, i).value: ws.column_dimensions[chr(64 + i)].width for i in range(1, ws.max_column + 1)}
    assert widths["Confidence"] >= len("Confidence")
    assert widths["FileName"] >= len("driving_licence_jordan_placeholder.txt")
    assert max(widths.values()) <= 60


def test_row_counts(workbook):
    assert workbook["Classification"].max_row == 1 + 7   # header + every document
    assert workbook["EmployeeData"].max_row == 1 + 2     # Alex + Jordan
    assert workbook["PreviousEmployment"].max_row == 1 + 2  # Alex's two jobs (Jordan's prose: none in mock)


def test_employee_sheet_values(workbook):
    ws = workbook["EmployeeData"]
    headers = [c.value for c in ws[1]]
    rows = [dict(zip(headers, (c.value for c in row))) for row in ws.iter_rows(min_row=2)]
    alex = next(r for r in rows if r["PersonKey"] == "alex-example")
    assert (alex["StatedAge"], alex["CalculatedAge"], alex["AgeMismatch"], alex["Status"]) == (36, 36, False, "Processed")


def test_save_locally_and_to_blob(tmp_path, blobs):
    path = save_report_locally(b"xlsx-bytes", tmp_path)
    assert path == tmp_path / "onboarding_results.xlsx" and path.read_bytes() == b"xlsx-bytes"
    name = save_report_to_blob(b"xlsx-bytes", blobs, datetime(2026, 11, 1, 9, 30, 0))
    assert name == "onboarding_results_20261101T093000Z.xlsx"
    assert blobs.download(REPORTS, name) == b"xlsx-bytes"
