"""Business-rule checks on extracted employee data.

Plain functions with "today" passed in, so tests give the same answer every day.
"""

from __future__ import annotations

from datetime import date

from ..models import EmployeeExtraction

REQUIRED_FIELDS = ("full_name", "date_of_birth", "stated_age", "right_to_work_status")
_TIME_LIMITED_WORDS = ("visa", "leave", "permit")


def calculate_age(date_of_birth: date, today: date) -> int:
    # Subtract one if this year's birthday hasn't happened yet.
    # (Someone born on 29 February turns a year older on 1 March in non-leap years.)
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


def validate_extraction(data: EmployeeExtraction, today: date) -> list[str]:
    issues: list[str] = []

    missing = [name for name in REQUIRED_FIELDS if getattr(data, name) in (None, "")]
    if missing:
        issues.append(f"Missing required fields: {', '.join(missing)}")

    if data.date_of_birth:
        if data.date_of_birth > today:
            issues.append(f"Date of birth {data.date_of_birth} is in the future")
        elif data.stated_age is not None:
            actual = calculate_age(data.date_of_birth, today)
            if actual != data.stated_age:
                issues.append(
                    f"Stated age {data.stated_age} does not match age {actual} "
                    f"calculated from date of birth {data.date_of_birth}"
                )

    status = (data.right_to_work_status or "").lower()
    if data.right_to_work_expiry and data.right_to_work_expiry < today:
        issues.append(f"Right to work expired on {data.right_to_work_expiry}")
    elif (
        not data.right_to_work_expiry
        and any(word in status for word in _TIME_LIMITED_WORDS)
        and "indefinite" not in status  # Indefinite Leave to Remain does not expire
    ):
        issues.append("Right to work status looks time-limited but has no expiry date")

    return issues
