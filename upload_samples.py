"""Upload sample_documents/ to the "incoming" container (Azurite or Azure).

Usage (Azurite running, .venv active):
    python upload_samples.py                 # uses sample_documents/
    python upload_samples.py path\\to\\folder

The target comes from STORAGE_CONNECTION_STRING (default: Azurite).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from azure.core.exceptions import ServiceRequestError  # noqa: E402

from hr_onboarding.config import get_settings  # noqa: E402
from hr_onboarding.documents import SUPPORTED_SUFFIXES  # noqa: E402
from hr_onboarding.routing import ALL_CONTAINERS, INCOMING  # noqa: E402
from hr_onboarding.storage import AzureBlobStore  # noqa: E402


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_documents")
    store = AzureBlobStore(get_settings().storage_connection_string)
    try:
        store.ensure_containers(ALL_CONTAINERS)
    except ServiceRequestError:
        sys.exit("Cannot reach Blob Storage. Is Azurite running? (VS Code: Azurite: Start Blob Service)")

    files = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    for path in files:
        store.upload(INCOMING, path.name, path.read_bytes())
        print(f"uploaded {INCOMING}/{path.name}")
    print(f"\n{len(files)} file(s) uploaded. Next: python run_local.py")


if __name__ == "__main__":
    main()
