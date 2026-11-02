"""Reads and writes rows in the EmployeeData table.

SQLAlchemy hides the database differences: SQLite locally, Azure SQL in the
cloud, chosen only by SQL_CONNECTION_STRING. Keep this table definition in
step with sql/create_employee_data.sql.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    Table,
    Unicode,
    UnicodeText,
    UniqueConstraint,
    create_engine,
    insert,
    make_url,
    select,
    update,
)
from sqlalchemy.dialects import mssql

from ..models import DocumentResult

SQLITE_FILENAME = "hr_onboarding.db"

metadata = MetaData()

# Unicode / UnicodeText become NVARCHAR on Azure SQL, so accented names survive.
employee_data = Table(
    "EmployeeData",
    metadata,
    Column("Id", Integer, primary_key=True, autoincrement=True),
    Column("PersonKey", Unicode(64), nullable=False),
    Column("FileName", Unicode(255), nullable=False),
    Column("FullName", Unicode(200)),
    Column("DateOfBirth", Date),
    Column("StatedAge", Integer),
    Column("CalculatedAge", Integer),
    Column("AgeMismatch", Boolean),
    Column("RightToWorkStatus", Unicode(200)),
    Column("RightToWorkExpiry", Date),
    Column("PreviousEmploymentJson", UnicodeText),
    Column("BlobUrl", Unicode(1000)),
    Column("Confidence", Float),
    Column("Status", Unicode(20), nullable=False),
    Column("Issues", UnicodeText),
    Column("ProcessedAt", DateTime().with_variant(mssql.DATETIME2(), "mssql"), nullable=False),  # UTC
    # Same file name can exist for different people (one blob folder each).
    UniqueConstraint("PersonKey", "FileName", name="UQ_EmployeeData_PersonKey_FileName"),
)

EMPLOYEE_COLUMNS = [c.name for c in employee_data.columns if c.name != "Id"]


def resolve_database_url(connection_string: str | None, output_dir: Path) -> str:
    """Turn SQL_CONNECTION_STRING into a SQLAlchemy URL.

    - unset                       -> SQLite file in output_dir
    - "Driver={ODBC Driver 18...}" -> mssql+pyodbc (raw ODBC string from the Azure portal)
    - anything else               -> used as-is (already a SQLAlchemy URL)
    """
    if not connection_string:
        return f"sqlite:///{(output_dir / SQLITE_FILENAME).as_posix()}"
    if connection_string.strip().lower().startswith("driver="):
        return "mssql+pyodbc:///?odbc_connect=" + quote_plus(connection_string.strip())
    return connection_string


def to_employee_row(result: DocumentResult, blob_url: str, processed_at: datetime) -> dict[str, Any]:
    data = result.extraction
    return {
        "PersonKey": result.person_key,
        "FileName": result.source_file,
        "FullName": data.full_name if data else None,
        "DateOfBirth": data.date_of_birth if data else None,
        "StatedAge": data.stated_age if data else None,
        "CalculatedAge": result.calculated_age,
        "AgeMismatch": result.age_mismatch,
        "RightToWorkStatus": data.right_to_work_status if data else None,
        "RightToWorkExpiry": data.right_to_work_expiry if data else None,
        "PreviousEmploymentJson": json.dumps(
            [job.model_dump() for job in data.previous_employment] if data else []
        ),
        "BlobUrl": blob_url,
        "Confidence": result.confidence,
        "Status": result.status.value,
        "Issues": "; ".join(result.issues) or None,
        "ProcessedAt": processed_at,
    }


class EmployeeRepository:
    def __init__(self, database_url: str) -> None:
        url = make_url(database_url)
        if url.drivername.startswith("sqlite") and url.database not in (None, "", ":memory:"):
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        # pool_pre_ping replaces connections Azure SQL has dropped while idle.
        self._engine = create_engine(url, pool_pre_ping=True)

    def create_schema(self) -> None:
        metadata.create_all(self._engine)  # only creates tables that are missing

    def upsert(self, row: dict[str, Any]) -> None:
        """Insert, or update the existing row with the same (PersonKey, FileName).

        Select-then-write works the same on SQLite and Azure SQL; the unique
        constraint stops a duplicate if two writers race.
        """
        same_key = (employee_data.c.PersonKey == row["PersonKey"]) & (
            employee_data.c.FileName == row["FileName"]
        )
        with self._engine.begin() as conn:  # one transaction, committed on success
            existing_id = conn.execute(select(employee_data.c.Id).where(same_key)).scalar_one_or_none()
            if existing_id is None:
                conn.execute(insert(employee_data).values(**row))
            else:
                conn.execute(update(employee_data).where(employee_data.c.Id == existing_id).values(**row))

    def fetch_all(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(employee_data).order_by(employee_data.c.Id))
            return [dict(row._mapping) for row in rows]

    def dispose(self) -> None:
        self._engine.dispose()
