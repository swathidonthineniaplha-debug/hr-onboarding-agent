"""Process every document in a folder and print the results.

Usage (from the project root, with .venv active):
    python run_local.py                  # uses sample_documents/
    python run_local.py path\\to\\folder

The LLM provider comes from LLM_PROVIDER in .env (default: mock).
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from hr_onboarding.config import get_settings  # noqa: E402
from hr_onboarding.documents import SUPPORTED_SUFFIXES  # noqa: E402
from hr_onboarding.llm import create_llm_client  # noqa: E402
from hr_onboarding.pipeline import process_document  # noqa: E402


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_documents")
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
    llm = create_llm_client(settings)
    print(f"LLM provider: {llm.name}\nFolder: {folder}\n")

    results = [
        process_document(path.name, path.read_bytes(), llm)
        for path in sorted(folder.iterdir())
        if path.suffix.lower() in SUPPORTED_SUFFIXES
    ]

    header = f"{'File':40} {'Category':17} {'Conf':>5}  {'PersonKey':20} Status"
    print(header)
    print("-" * len(header))
    for r in results:
        category = r.category.value if r.category else "-"
        confidence = f"{r.confidence:.2f}" if r.confidence is not None else "-"
        print(f"{r.source_file:40} {category:17} {confidence:>5}  {r.person_key:20} {r.status.value}")

    for r in results:
        print(f"\n=== {r.source_file} ===")
        print(r.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
