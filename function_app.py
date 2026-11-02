"""Azure Functions entry point (Python v2 programming model).

- process_incoming_blob  blob trigger on "incoming": classify and route each new upload
- process_all            POST /api/process-all: process everything currently in "incoming"
- report                 POST /api/report: build the Excel report from the database and
                         save it to "reports" (returns the blob name, never a link)

The handle_* functions hold the logic and take the service as an argument, so
tests can call them with in-memory blobs and SQLite. The decorated functions
only add the Azure Functions bindings.
"""

import json
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import azure.functions as func

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from hr_onboarding.config import ConfigError, get_settings  # noqa: E402
from hr_onboarding.llm import create_llm_client  # noqa: E402
from hr_onboarding.models import ProcessingStatus  # noqa: E402
from hr_onboarding.reporting import save_report_to_blob  # noqa: E402
from hr_onboarding.routing import INCOMING, REPORTS  # noqa: E402
from hr_onboarding.service import OnboardingService, ProcessedDocument, utc_now  # noqa: E402
from hr_onboarding.storage import AzureBlobStore, EmployeeRepository, resolve_database_url  # noqa: E402

logger = logging.getLogger(__name__)

# Flex Consumption only supports Event Grid blob triggers, so that is the default.
# Azurite has no Event Grid: local.settings.json sets LogsAndContainerScan (polling).
BLOB_TRIGGER_SOURCE = func.BlobSource(os.environ.get("BLOB_TRIGGER_SOURCE", func.BlobSource.EVENT_GRID.value))

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


# --- Service (one per worker process, built on first use) ------------------

_service: OnboardingService | None = None
_service_lock = threading.Lock()  # the worker can run sync functions on several threads


def get_service() -> OnboardingService:
    global _service
    with _service_lock:
        if _service is None:
            _service = create_service()  # if this fails, the next invocation tries again
    return _service


def create_service() -> OnboardingService:
    settings = get_settings()
    if not settings.sql_connection_string and running_in_azure():
        # The SQLite fallback writes under OUTPUT_DIR, which only makes sense locally.
        raise ConfigError("SQL_CONNECTION_STRING is required in Azure")
    repository = EmployeeRepository(resolve_database_url(settings.sql_connection_string, settings.output_dir))
    blobs = AzureBlobStore(settings.storage_connection_string)
    service = OnboardingService(create_llm_client(settings), blobs, repository)
    service.setup()
    return service


def running_in_azure() -> bool:
    # Core Tools (func start) sets Development; Azure defaults to Production.
    return os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT", "Production") != "Development"


# --- Handlers ---------------------------------------------------------------

def handle_incoming_blob(service: OnboardingService, blob_name: str) -> ProcessedDocument | None:
    """Process one new upload, or skip it (returns None) if there is nothing new to do.

    Skipped: blobs already moved by /api/process-all, and blobs already marked
    NeedsReview. Setting that metadata changes the blob's ETag, which would
    otherwise make the polling trigger fire again. Re-uploading clears it.
    """
    metadata = service.blobs.get_metadata(INCOMING, blob_name)
    if metadata is None:
        logger.info("%s/%s no longer exists, skipping", INCOMING, blob_name)
        return None
    if metadata.get("status") == ProcessingStatus.NEEDS_REVIEW.value:
        logger.info("%s/%s is already marked for review, skipping", INCOMING, blob_name)
        return None
    return service.process_incoming_blob(blob_name)


def handle_process_all(service: OnboardingService) -> dict[str, Any]:
    documents = service.process_all_incoming()
    return {
        "processed": len(documents),
        "routed": sum(d.routed for d in documents),
        "needs_review": sum(not d.routed for d in documents),
        "documents": [document_summary(d) for d in documents],
    }


def handle_report(service: OnboardingService, now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    report = service.build_report()
    blob_name = save_report_to_blob(report.content, service.blobs, now)
    return {
        "container": REPORTS,
        "blob_name": blob_name,
        "generated_at": f"{now:%Y-%m-%dT%H:%M:%SZ}",
        "row_counts": report.row_counts,
    }


def document_summary(document: ProcessedDocument) -> dict[str, Any]:
    result = document.result
    return {
        "file": result.source_file,
        "category": result.category.value if result.category else None,
        "confidence": result.confidence,
        "status": result.status.value,
        "location": document.location,
        "issues": result.issues,
    }


# --- Triggers ---------------------------------------------------------------

@app.blob_trigger(
    arg_name="blob",
    path=f"{INCOMING}/{{name}}",
    connection="STORAGE_CONNECTION_STRING",
    source=BLOB_TRIGGER_SOURCE,
)
def process_incoming_blob(blob: func.InputStream) -> None:
    # blob.name is "incoming/<name>"; the service downloads the content itself.
    handle_incoming_blob(get_service(), blob.name.removeprefix(f"{INCOMING}/"))


@app.route(route="process-all", methods=["POST"])
def process_all(req: func.HttpRequest) -> func.HttpResponse:
    return json_response(handle_process_all(get_service()))


@app.route(route="report", methods=["POST"])
def report(req: func.HttpRequest) -> func.HttpResponse:
    return json_response(handle_report(get_service()))


def json_response(body: dict[str, Any]) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body), mimetype="application/json")
