"""Deterministic offline provider for local development and tests.

It uses keyword and regex rules instead of a model, and returns the same JSON
shape a real LLM would. Rules handle labelled forms ("Field: value") well, but
only pick out a few facts from free-flowing prose; employment history written
as sentences is left empty. Reading prose is what the real LLM is for.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from .base import LLMClient, LLMRequest, LLMTask

_FLAGS = re.IGNORECASE | re.MULTILINE

_CATEGORY_SIGNALS = {
    "Passport": [r"\bpassport\b", r"\bpassport (?:no|number)\b", r"\bnationality\b"],
    "DrivingLicence": [r"\bdriving licence\b", r"\blicence (?:no|number)\b", r"\b(?:entitlement|categories)\b"],
    "EmployeeDocument": [
        r"\bright to work\b",
        r"\b(?:previous employment|career|worked as)\b",
        r"\breferees?\b",
        r"\bnew (?:starter|joiner)\b",
    ],
}

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_ORDINALS = {w: i for i, w in enumerate(
    ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
     "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
     "eighteenth", "nineteenth", "twentieth", "twenty-first", "twenty-second", "twenty-third",
     "twenty-fourth", "twenty-fifth", "twenty-sixth", "twenty-seventh", "twenty-eighth",
     "twenty-ninth", "thirtieth", "thirty-first"], start=1)}


class MockLLMClient(LLMClient):
    name = "mock"

    def complete(self, request: LLMRequest) -> str:
        handlers = {
            LLMTask.CLASSIFY: _classify,
            LLMTask.PERSON_NAME: lambda text: {"full_name": _find_full_name(text)},
            LLMTask.EXTRACT: _extract,
        }
        return json.dumps(handlers[request.task](request.document))


def _classify(text: str) -> dict[str, Any]:
    scores = {
        category: [p for p in patterns if re.search(p, text, _FLAGS)]
        for category, patterns in _CATEGORY_SIGNALS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: len(item[1]), reverse=True)
    (best, matched), (_, runner_up) = ranked[0], ranked[1]
    if not matched or len(matched) == len(runner_up):
        return {"category": "Other", "confidence": 0.4, "reason": "No clear document-type signals found"}
    confidence = {1: 0.55, 2: 0.85}.get(len(matched), 0.95)
    return {"category": best, "confidence": confidence, "reason": f"Matched {len(matched)} {best} signal(s)"}


def _find_full_name(text: str) -> str | None:
    # 1. A labelled name line: "Full name: ...", "Name: ...", "Holder ....... ..."
    if m := re.search(r"^\s*(?:full name|name|holder)\s*[:.]+\s*(.+)$", text, _FLAGS):
        return _tidy_name(m.group(1))
    # 2. Separate surname and given-name fields (passport / licence style)
    surname = re.search(r"\bsurname\s*:\s*(.+)$", text, _FLAGS)
    given = re.search(r"\b(?:given names?|forenames?(?:\(s\))?)\s*:\s*(.+)$", text, _FLAGS)
    if surname and given:
        return _tidy_name(f"{given.group(1)} {surname.group(1)}")
    # 3. A letter subject line: "Re: ... for Jordan Placeholder"
    if m := re.search(r"^Re:.*\bfor\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)+)\s*$", text, re.MULTILINE):
        return _tidy_name(m.group(1))
    return None


def _tidy_name(raw: str) -> str:
    name = " ".join(raw.split())
    return name.title() if name.isupper() else name


def _extract(text: str) -> dict[str, Any]:
    status, expiry = _right_to_work(text)
    return {
        "full_name": _find_full_name(text),
        "date_of_birth": _parse_date(_field(text, r"date of birth|dob|born")),
        "stated_age": _stated_age(text),
        "right_to_work_status": status,
        "right_to_work_expiry": expiry,
        "previous_employment": _employment_blocks(text),
    }


def _field(text: str, label: str) -> str | None:
    m = re.search(rf"\b(?:{label})\b\s*[:.]*\s*(.+)$", text, _FLAGS)
    return m.group(1).strip() if m else None


def _stated_age(text: str) -> int | None:
    m = re.search(r"^\s*age\s*:\s*(\d+)", text, _FLAGS) or re.search(r"\baged\s+(\d+)", text, _FLAGS)
    return int(m.group(1)) if m else None


def _right_to_work(text: str) -> tuple[str | None, str | None]:
    value = _field(text, r"right to work status|status")
    if not value:
        return None, None
    if m := re.match(r"(.+?),?\s+expir(?:es|y|ing)\s*(?:on\s*)?(.+)", value, re.IGNORECASE):
        return m.group(1).strip(), _parse_date(m.group(2))
    return value, None


def _employment_blocks(text: str) -> list[dict[str, Any]]:
    # Only labelled "Company: ..." blocks; prose employment history is not parsed.
    starts = [m.start() for m in re.finditer(r"^.*\bcompany\s*:", text, _FLAGS)]
    jobs = []
    for start, end in zip(starts, starts[1:] + [len(text)]):
        block = text[start:end]
        dates = re.findall(r"\d{4}-\d{2}(?:-\d{2})?", _field(block, "dates") or "")
        referee = _field(block, r"referee(?!\s+contact)")
        jobs.append({
            "company": _field(block, "company"),
            "job_title": _field(block, "job title"),
            "start_date": dates[0] if dates else None,
            "end_date": dates[1] if len(dates) > 1 else None,
            "referee_name": re.sub(r"\s*\(.*?\)\s*$", "", referee) if referee else None,
            "referee_contact": _field(block, "referee contact"),
        })
    return jobs


def _parse_date(value: str | None) -> str | None:
    """Find a date in common UK formats and return it as YYYY-MM-DD."""
    if not value:
        return None
    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", value):
        parts = int(m.group(1)), int(m.group(2)), int(m.group(3))
    elif m := re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", value):  # UK order: day first
        parts = int(m.group(3)), int(m.group(2)), int(m.group(1))
    elif m := re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})\.?\s+(\d{4})\b", value, re.I):
        parts = int(m.group(3)), _MONTHS.get(m.group(2)[:3].lower(), 0), int(m.group(1))
    elif m := re.search(r"\b([a-z-]+)\s+of\s+([a-z]{3,9})\s+(\d{4})\b", value, re.I):
        parts = int(m.group(3)), _MONTHS.get(m.group(2)[:3].lower(), 0), _ORDINALS.get(m.group(1).lower(), 0)
    else:
        return None
    try:
        return date(*parts).isoformat()
    except ValueError:  # e.g. unknown month word or 31 February
        return None
