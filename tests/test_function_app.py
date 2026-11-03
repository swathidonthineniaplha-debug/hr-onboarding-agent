"""Function handlers and trigger wiring, using in-memory blobs and SQLite."""

import io
import json
from datetime import datetime

import azure.functions as func
import pytest
from openpyxl import load_workbook

import function_app
from function_app import handle_incoming_blob, handle_process_all, handle_report
from hr_onboarding.config import ConfigError, Settings
from hr_onboarding.routing import INCOMING, PASSPORTS, REPORTS

PASSPORT = b"Passport\nName: Casey Sample\nPassport number: AB000009\nNationality: Testlandian"
NAMELESS_PASSPORT = b"Passport\nPassport number: AB000009\nNationality: Testlandian"
EMPLOYEE_FORM = (
    b"New starter form\nFull name: Casey Sample\nDate of birth: 01/02/1990\nAge: 36\n"
    b"Right to work status: British citizen\nReferee: Sam Referee"
)
NOTE = b"Saw someone at reception, ID seen."

# get_functions() may only be called once per app (it checks names are unique).
FUNCTIONS = {f.get_function_name(): f for f in function_app.app.get_functions()}


@pytest.fixture
def functions(monkeypatch, service):
    """The registered functions by name, with get_service() returning the test service."""
    monkeypatch.setattr(function_app, "get_service", lambda: service)
    return FUNCTIONS


def post(route: str) -> func.HttpRequest:
    return func.HttpRequest(method="POST", url=f"/api/{route}", body=b"")


# --- Blob trigger ---------------------------------------------------------

def test_new_upload_is_routed(blobs, service):
    blobs.upload(INCOMING, "p.txt", PASSPORT)
    doc = handle_incoming_blob(service, "p.txt")
    assert doc.location == "passports/casey-sample/p.txt"
    assert blobs.list_names(INCOMING) == []


def test_blob_already_moved_is_skipped(service):
    assert handle_incoming_blob(service, "gone.txt") is None  # e.g. /api/process-all got there first


def test_blob_marked_for_review_is_not_processed_again(blobs, service):
    blobs.upload(INCOMING, "note.txt", NOTE)
    assert not handle_incoming_blob(service, "note.txt").routed
    # Setting the review metadata changes the ETag, so the trigger can fire again.
    assert handle_incoming_blob(service, "note.txt") is None


def test_reupload_after_review_is_processed(blobs, service):
    blobs.upload(INCOMING, "scan.txt", NAMELESS_PASSPORT)
    assert not handle_incoming_blob(service, "scan.txt").routed
    blobs.upload(INCOMING, "scan.txt", PASSPORT)  # overwriting clears the metadata
    assert handle_incoming_blob(service, "scan.txt").location == "passports/casey-sample/scan.txt"


def test_blob_trigger_strips_container_from_name(blobs, functions):
    blobs.upload(INCOMING, "p.txt", PASSPORT)
    trigger = functions["process_incoming_blob"].get_user_function()
    trigger(func.blob.InputStream(data=PASSPORT, name="incoming/p.txt"))
    assert blobs.list_names(PASSPORTS) == ["casey-sample/p.txt"]


# --- /api/process-all -----------------------------------------------------

def test_process_all_summarises_every_document(blobs, service):
    blobs.upload(INCOMING, "p.txt", PASSPORT)
    blobs.upload(INCOMING, "form.txt", EMPLOYEE_FORM)
    blobs.upload(INCOMING, "note.txt", NOTE)
    body = handle_process_all(service)
    assert (body["processed"], body["routed"], body["needs_review"]) == (3, 2, 1)
    by_file = {d["file"]: d for d in body["documents"]}
    assert by_file["form.txt"]["location"] == "employee-documents/casey-sample/form.txt"
    assert (by_file["note.txt"]["status"], by_file["note.txt"]["location"]) == ("NeedsReview", "incoming/note.txt")


def test_process_all_with_nothing_incoming(service):
    assert handle_process_all(service) == {"processed": 0, "routed": 0, "needs_review": 0, "documents": []}


def test_process_all_http_returns_json(blobs, functions):
    blobs.upload(INCOMING, "p.txt", PASSPORT)
    response = functions["process_all"].get_user_function()(post("process-all"))
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert json.loads(response.get_body())["routed"] == 1


# --- /api/report ----------------------------------------------------------

def test_report_is_saved_to_reports_container(blobs, service):
    blobs.upload(INCOMING, "form.txt", EMPLOYEE_FORM)
    blobs.upload(INCOMING, "note.txt", NOTE)
    handle_process_all(service)

    body = handle_report(service, now=datetime(2026, 11, 1, 9, 30, 0))
    assert body == {
        "container": "reports",
        "blob_name": "onboarding_results_20261101T093000Z.xlsx",
        "generated_at": "2026-11-01T09:30:00Z",
        "row_counts": {"Classification": 2, "EmployeeData": 1, "PreviousEmployment": 0},
    }
    workbook = load_workbook(io.BytesIO(blobs.download(REPORTS, body["blob_name"])))
    locations = [row[-1] for row in workbook["Classification"].iter_rows(min_row=2, values_only=True)]
    assert sorted(locations) == ["employee-documents/casey-sample/form.txt", "incoming/note.txt"]


def test_report_keeps_only_latest_classification(blobs, service):
    blobs.upload(INCOMING, "scan.txt", NAMELESS_PASSPORT)
    handle_process_all(service)  # left in incoming for review
    blobs.upload(INCOMING, "scan.txt", PASSPORT)
    handle_process_all(service)  # now routed
    workbook = load_workbook(io.BytesIO(service.build_report().content))
    rows = list(workbook["Classification"].iter_rows(min_row=2, values_only=True))
    assert [(row[0], row[5], row[-1]) for row in rows] == [("scan.txt", "Processed", "passports/casey-sample/scan.txt")]


def test_report_http_returns_blob_name_not_link(blobs, functions):
    response = functions["report"].get_user_function()(post("report"))
    body = json.loads(response.get_body())
    assert body["blob_name"] in blobs.list_names(REPORTS)
    assert "url" not in json.dumps(body).lower()
    assert body["row_counts"] == {"Classification": 0, "EmployeeData": 0, "PreviousEmployment": 0}


# --- Health ---------------------------------------------------------------

def test_health_returns_ok_without_building_the_service(monkeypatch):
    def fail():
        raise AssertionError("health must not touch storage, SQL or the LLM")

    monkeypatch.setattr(function_app, "get_service", fail)
    request = func.HttpRequest(method="GET", url="/api/health", body=b"")
    response = FUNCTIONS["health"].get_user_function()(request)
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert json.loads(response.get_body()) == {"status": "ok"}


# --- Registration ---------------------------------------------------------

def test_functions_are_registered_with_expected_bindings():
    bindings = {name: f.get_dict_repr()["bindings"][0] for name, f in FUNCTIONS.items()}
    assert bindings["process_incoming_blob"]["type"] == "blobTrigger"
    assert bindings["process_incoming_blob"]["path"] == "incoming/{name}"
    assert bindings["process_incoming_blob"]["connection"] == "STORAGE_CONNECTION_STRING"
    for name, route in [("process_all", "process-all"), ("report", "report")]:
        assert bindings[name]["route"] == route
        assert bindings[name]["authLevel"] == func.AuthLevel.FUNCTION
        assert [str(m.value) for m in bindings[name]["methods"]] == ["POST"]
    assert bindings["health"]["route"] == "health"
    assert bindings["health"]["authLevel"] == func.AuthLevel.FUNCTION
    assert [str(m.value) for m in bindings["health"]["methods"]] == ["GET"]


def test_sqlite_fallback_is_refused_in_azure(monkeypatch):
    monkeypatch.setenv("AZURE_FUNCTIONS_ENVIRONMENT", "Production")
    monkeypatch.setattr(function_app, "get_settings", lambda: Settings.from_env({}))  # no SQL_CONNECTION_STRING
    with pytest.raises(ConfigError, match="SQL_CONNECTION_STRING"):
        function_app.create_service()
