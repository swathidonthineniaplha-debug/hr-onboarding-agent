"""Turns uploaded file bytes into plain text for the LLM.

Works on bytes rather than file paths, so the same code serves local files
and Azure Blob triggers.
"""

from __future__ import annotations

import io
from pathlib import PurePath

from pypdf import PdfReader

SUPPORTED_SUFFIXES = {".txt", ".pdf"}


class UnsupportedDocumentError(ValueError):
    """Raised for file types the pipeline cannot read."""


def extract_text(filename: str, content: bytes) -> str:
    suffix = PurePath(filename).suffix.lower()
    if suffix == ".txt":
        return content.decode("utf-8-sig")  # utf-8-sig also strips a Windows BOM
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise UnsupportedDocumentError(f"Unsupported file type: {suffix or '(none)'}")
