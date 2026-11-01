"""PersonKey: a blob-path-safe identifier built from a person's full name.

"Alex Example" -> "alex-example". Used as the per-person folder name in Blob
Storage, so it must be predictable and contain only a-z, 0-9 and hyphens.
"""

from __future__ import annotations

import re
import unicodedata

from .llm import LLMClient, LLMTask, request_json
from .models import PersonName
from .prompts import PERSON_NAME_SYSTEM

UNKNOWN_PERSON = "unknown"
MAX_KEY_LENGTH = 64


def make_person_key(full_name: str | None) -> str:
    if not full_name:
        return UNKNOWN_PERSON
    # NFKD splits "é" into "e" + accent; encoding to ASCII then drops the accent.
    ascii_name = unicodedata.normalize("NFKD", full_name).encode("ascii", "ignore").decode()
    key = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    key = key[:MAX_KEY_LENGTH].rstrip("-")
    return key or UNKNOWN_PERSON


def extract_person_key(llm: LLMClient, text: str) -> str:
    result = request_json(llm, LLMTask.PERSON_NAME, PERSON_NAME_SYSTEM, text, PersonName)
    return make_person_key(result.full_name)
