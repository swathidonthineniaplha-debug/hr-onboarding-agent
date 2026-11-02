"""Connects the pipeline to storage: incoming blob -> routed blob (+ SQL row).

Order matters for safe retries: copy to the destination, write SQL, and only
then delete from incoming. If any step fails, the original stays in incoming
and processing it again is harmless (blob overwrite + SQL upsert).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import PurePosixPath
from typing import Any

from .llm import LLMClient
from .models import DocumentCategory, DocumentResult
from .pipeline import process_document
from .routing import (
    ALL_CONTAINERS,
    INCOMING,
    destination_container,
    destination_path,
    review_metadata,
)
from .storage import BlobStore, EmployeeRepository, to_employee_row

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    result: DocumentResult
    location: str  # "container/path" where the file now lives
    blob_url: str
    routed: bool
    employee_row: dict[str, Any] | None = None  # set when written to EmployeeData


def utc_now() -> datetime:
    # Naive UTC: works for SQLite, DATETIME2 and Excel (which rejects time zones).
    return datetime.now(UTC).replace(tzinfo=None)


class OnboardingService:
    def __init__(
        self,
        llm: LLMClient,
        blobs: BlobStore,
        repository: EmployeeRepository,
        today: date | None = None,
    ) -> None:
        self.llm = llm
        self.blobs = blobs
        self.repository = repository
        self.today = today

    def setup(self) -> None:
        self.blobs.ensure_containers(ALL_CONTAINERS)
        self.repository.create_schema()

    def process_all_incoming(self) -> list[ProcessedDocument]:
        return [self.process_incoming_blob(name) for name in self.blobs.list_names(INCOMING)]

    def process_incoming_blob(self, blob_name: str) -> ProcessedDocument:
        content = self.blobs.download(INCOMING, blob_name)
        file_name = PurePosixPath(blob_name).name
        result = process_document(file_name, content, self.llm, self.today)

        container = destination_container(result)
        if container is None:
            self.blobs.set_metadata(INCOMING, blob_name, review_metadata(result))
            logger.info("%s left in %s for review", blob_name, INCOMING)
            return ProcessedDocument(
                result, f"{INCOMING}/{blob_name}", self.blobs.url(INCOMING, blob_name), routed=False
            )

        path = destination_path(result)
        self.blobs.upload(container, path, content)
        blob_url = self.blobs.url(container, path)

        employee_row = None
        if result.category is DocumentCategory.EMPLOYEE_DOCUMENT:
            employee_row = to_employee_row(result, blob_url, utc_now())
            self.repository.upsert(employee_row)

        self.blobs.delete(INCOMING, blob_name)
        logger.info("%s routed to %s/%s", blob_name, container, path)
        return ProcessedDocument(result, f"{container}/{path}", blob_url, routed=True, employee_row=employee_row)
