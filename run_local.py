"""Process documents end to end and print the results.

Usage (from the project root, with .venv active):
    python run_local.py              # read the "incoming" container (Azurite or Azure)
    python run_local.py --offline    # no Azurite: in-memory blobs loaded from sample_documents/

Both modes route documents, upsert EmployeeData (SQLite unless SQL_CONNECTION_STRING
is set) and save the Excel report to output/onboarding_results.xlsx.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from azure.core.exceptions import ServiceRequestError  # noqa: E402

from hr_onboarding.config import get_settings  # noqa: E402
from hr_onboarding.documents import SUPPORTED_SUFFIXES  # noqa: E402
from hr_onboarding.llm import create_llm_client  # noqa: E402
from hr_onboarding.reporting import save_report_locally  # noqa: E402
from hr_onboarding.routing import INCOMING  # noqa: E402
from hr_onboarding.service import OnboardingService  # noqa: E402
from hr_onboarding.storage import (  # noqa: E402
    AzureBlobStore,
    EmployeeRepository,
    InMemoryBlobStore,
    resolve_database_url,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="use in-memory blobs instead of Azurite")
    parser.add_argument("--folder", default="sample_documents", help="source folder for --offline")
    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")

    database_url = resolve_database_url(settings.sql_connection_string, settings.output_dir)
    repository = EmployeeRepository(database_url)
    blobs = InMemoryBlobStore() if args.offline else AzureBlobStore(settings.storage_connection_string)
    service = OnboardingService(create_llm_client(settings), blobs, repository)

    try:
        service.setup()
        if args.offline:
            for path in sorted(Path(args.folder).iterdir()):
                if path.suffix.lower() in SUPPORTED_SUFFIXES:
                    blobs.upload(INCOMING, path.name, path.read_bytes())
        documents = service.process_all_incoming()
    except ServiceRequestError:
        sys.exit("Cannot reach Blob Storage. Is Azurite running? (VS Code: Azurite: Start Blob Service)")

    print(f"LLM provider: {service.llm.name} | Blobs: {'in-memory' if args.offline else 'Azure/Azurite'}"
          f" | Database: {make_safe(database_url)}\n")
    if not documents:
        print(f"No documents in '{INCOMING}'. Run: python upload_samples.py")
        return

    header = f"{'File':40} {'Category':17} {'Conf':>5}  {'Status':12} Location"
    print(header)
    print("-" * (len(header) + 30))
    for d in documents:
        category = d.result.category.value if d.result.category else "-"
        confidence = f"{d.result.confidence:.2f}" if d.result.confidence is not None else "-"
        print(f"{d.result.source_file:40} {category:17} {confidence:>5}  {d.result.status.value:12} {d.location}")

    print("\nIssues:")
    for d in documents:
        for issue in d.result.issues:
            print(f"  {d.result.source_file}: {issue}")

    rows = sum(1 for d in documents if d.employee_row)
    print(f"\nEmployeeData rows written: {rows} (table now has {len(repository.fetch_all())})")
    try:
        path = save_report_locally(service.build_report().content, settings.output_dir)
    except PermissionError:
        sys.exit("Could not write the Excel report - close it in Excel and run again.")
    print(f"Excel report: {path.resolve()}")
    repository.dispose()


def make_safe(database_url: str) -> str:
    # Never print credentials from a connection string.
    return database_url if database_url.startswith("sqlite") else database_url.split(":", 1)[0] + "://***"


if __name__ == "__main__":
    main()
