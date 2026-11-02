"""Routing: where each document ends up, using an in-memory blob store."""

from pathlib import Path

import pytest

from hr_onboarding.routing import DRIVING_LICENCES, EMPLOYEE_DOCUMENTS, INCOMING, PASSPORTS

SAMPLES = Path(__file__).resolve().parent.parent / "sample_documents"

PASSPORT = b"Passport\nName: Casey Sample\nPassport number: AB000009\nNationality: Testlandian"
LICENCE = b"Driving licence\nName: Casey Sample\nLicence no: DL000009\nCategories: B"
EMPLOYEE_FORM = (
    b"New starter form\nFull name: Casey Sample\nDate of birth: 01/02/1990\nAge: 36\n"
    b"Right to work status: British citizen\nReferee: Sam Referee"
)
# Clearly a passport / employee form, but with no name anywhere.
NAMELESS_PASSPORT = b"Passport\nPassport number: AB000010\nNationality: Testlandian"
NAMELESS_EMPLOYEE_FORM = b"New starter form\nRight to work status: British citizen\nReferee: Sam Referee"


def test_passport_goes_to_person_folder_and_leaves_incoming(blobs, service):
    blobs.upload(INCOMING, "p.txt", PASSPORT)
    doc = service.process_incoming_blob("p.txt")
    assert doc.location == "passports/casey-sample/p.txt"
    assert blobs.download(PASSPORTS, "casey-sample/p.txt") == PASSPORT
    assert blobs.list_names(INCOMING) == []
    assert doc.employee_row is None  # identity documents never go to SQL


def test_licence_goes_to_person_folder(blobs, service, repository):
    blobs.upload(INCOMING, "l.txt", LICENCE)
    assert service.process_incoming_blob("l.txt").location == "driving-licences/casey-sample/l.txt"
    assert blobs.list_names(DRIVING_LICENCES) == ["casey-sample/l.txt"]
    assert repository.fetch_all() == []


def test_employee_document_is_routed_and_stored_in_sql(blobs, service, repository):
    blobs.upload(INCOMING, "form.txt", EMPLOYEE_FORM)
    doc = service.process_incoming_blob("form.txt")
    assert blobs.list_names(EMPLOYEE_DOCUMENTS) == ["casey-sample/form.txt"]
    [row] = repository.fetch_all()
    assert (row["PersonKey"], row["FileName"], row["Status"]) == ("casey-sample", "form.txt", "Processed")
    assert row["BlobUrl"] == doc.blob_url == "memory://employee-documents/casey-sample/form.txt"


def test_other_document_stays_in_incoming_marked_for_review(blobs, service):
    blobs.upload(INCOMING, "note.txt", b"Saw someone at reception, ID seen.")
    doc = service.process_incoming_blob("note.txt")
    assert not doc.routed
    assert blobs.list_names(INCOMING) == ["note.txt"]
    assert blobs.metadata[(INCOMING, "note.txt")]["status"] == "NeedsReview"


@pytest.mark.parametrize("content", [NAMELESS_PASSPORT, NAMELESS_EMPLOYEE_FORM])
def test_name_not_found_stays_in_incoming(blobs, service, repository, content):
    blobs.upload(INCOMING, "doc.txt", content)
    doc = service.process_incoming_blob("doc.txt")
    assert doc.result.confidence >= 0.8  # classified fine - only the name is missing
    assert not doc.routed
    assert "Name not found" in doc.result.issues
    assert blobs.list_names(INCOMING) == ["doc.txt"]
    assert "Name not found" in blobs.metadata[(INCOMING, "doc.txt")]["issues"]
    assert repository.fetch_all() == []  # no SQL row for an unrouted document


def test_sql_failure_keeps_original_in_incoming(blobs, service, monkeypatch):
    def broken_upsert(row):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(service.repository, "upsert", broken_upsert)
    blobs.upload(INCOMING, "form.txt", EMPLOYEE_FORM)
    with pytest.raises(RuntimeError):
        service.process_incoming_blob("form.txt")
    assert blobs.list_names(INCOMING) == ["form.txt"]  # safe to retry


def test_all_samples_end_to_end(blobs, service, repository):
    for path in SAMPLES.iterdir():
        if path.suffix in {".txt", ".pdf"}:
            blobs.upload(INCOMING, path.name, path.read_bytes())

    service.process_all_incoming()

    assert blobs.list_names(INCOMING) == ["ambiguous_note.txt"]
    assert blobs.list_names(PASSPORTS) == [
        "alex-example/passport_alex_example.txt",
        "jordan-placeholder/passport_jordan_placeholder.pdf",
    ]
    assert len(blobs.list_names(DRIVING_LICENCES)) == 2
    rows = {row["PersonKey"]: row for row in repository.fetch_all()}
    assert set(rows) == {"alex-example", "jordan-placeholder"}
    assert (rows["alex-example"]["Status"], rows["alex-example"]["AgeMismatch"]) == ("Processed", False)
    assert rows["jordan-placeholder"]["Status"] == "NeedsReview"
    assert rows["jordan-placeholder"]["Issues"] == "Missing required fields: right_to_work_status"
