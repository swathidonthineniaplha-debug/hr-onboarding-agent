"""SQL repository: schema, upsert on (PersonKey, FileName), connection strings."""

import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from hr_onboarding.storage.sql_repository import (
    EMPLOYEE_COLUMNS,
    employee_data,
    resolve_database_url,
)

SQL_SCRIPT = Path(__file__).resolve().parent.parent / "sql" / "create_employee_data.sql"


def make_row(**changes):
    row = {
        "PersonKey": "alex-example",
        "FileName": "form.txt",
        "FullName": "Alex Example",
        "DateOfBirth": date(1990, 4, 12),
        "StatedAge": 31,
        "CalculatedAge": 36,
        "AgeMismatch": True,
        "RightToWorkStatus": "Skilled Worker visa",
        "RightToWorkExpiry": date(2028, 3, 31),
        "PreviousEmploymentJson": json.dumps([{"company": "Example Widgets Ltd"}]),
        "BlobUrl": "memory://employee-documents/alex-example/form.txt",
        "Confidence": 0.95,
        "Status": "NeedsReview",
        "Issues": "Stated age 31 does not match age 36",
        "ProcessedAt": datetime(2026, 11, 1, 9, 0, 0),
    }
    return {**row, **changes}


def test_insert_round_trips_types(repository):
    repository.upsert(make_row())
    [row] = repository.fetch_all()
    assert row["DateOfBirth"] == date(1990, 4, 12)
    assert row["AgeMismatch"] is True
    assert json.loads(row["PreviousEmploymentJson"]) == [{"company": "Example Widgets Ltd"}]


def test_upsert_same_person_and_file_updates_in_place(repository):
    repository.upsert(make_row())
    repository.upsert(make_row(StatedAge=36, AgeMismatch=False, Status="Processed", Issues=None))
    [row] = repository.fetch_all()
    assert (row["Id"], row["StatedAge"], row["Status"]) == (1, 36, "Processed")


def test_same_file_name_for_different_people_gives_two_rows(repository):
    repository.upsert(make_row())
    repository.upsert(make_row(PersonKey="jordan-placeholder", FullName="Jordan Placeholder"))
    assert sorted(r["PersonKey"] for r in repository.fetch_all()) == ["alex-example", "jordan-placeholder"]


def test_database_enforces_unique_person_key_and_file_name(repository):
    repository.upsert(make_row())
    with pytest.raises(IntegrityError), repository._engine.begin() as conn:
        conn.execute(insert(employee_data).values(**make_row()))  # bypass upsert on purpose


def test_create_schema_is_safe_to_repeat(repository):
    repository.upsert(make_row())
    repository.create_schema()
    assert len(repository.fetch_all()) == 1


def test_default_url_is_local_sqlite(tmp_path):
    assert resolve_database_url(None, tmp_path) == f"sqlite:///{(tmp_path / 'hr_onboarding.db').as_posix()}"


def test_azure_odbc_string_becomes_mssql_pyodbc_url(tmp_path):
    odbc = "Driver={ODBC Driver 18 for SQL Server};Server=tcp:fake.database.windows.net,1433;Database=hr"
    url = resolve_database_url(odbc, tmp_path)
    assert url.startswith("mssql+pyodbc:///?odbc_connect=Driver%3D%7BODBC+Driver+18")


def test_sqlalchemy_url_is_used_as_is(tmp_path):
    assert resolve_database_url("sqlite:///other.db", tmp_path) == "sqlite:///other.db"


def test_portal_script_matches_table_definition():
    script = SQL_SCRIPT.read_text()
    for column in ["Id", *EMPLOYEE_COLUMNS]:
        assert re.search(rf"^\s+{column}\s", script, re.MULTILINE), column
    assert "UNIQUE (PersonKey, FileName)" in script
