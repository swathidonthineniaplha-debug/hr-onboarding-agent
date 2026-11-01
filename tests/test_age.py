"""Tests for age calculation and the stated-age check."""

from datetime import date

import pytest

from hr_onboarding.extraction import calculate_age, validate_extraction
from hr_onboarding.models import EmployeeExtraction

DOB = date(1990, 4, 12)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 4, 11), 35),  # day before birthday
        (date(2026, 4, 12), 36),  # on birthday
        (date(2026, 4, 13), 36),  # day after
    ],
)
def test_calculate_age_around_birthday(today, expected):
    assert calculate_age(DOB, today) == expected


def test_leap_day_birthday_counts_from_1_march():
    leap = date(2004, 2, 29)
    assert calculate_age(leap, date(2026, 2, 28)) == 21
    assert calculate_age(leap, date(2026, 3, 1)) == 22


def _check(stated_age: int, dob: date = DOB) -> list[str]:
    data = EmployeeExtraction(
        full_name="Alex Example", date_of_birth=dob, stated_age=stated_age,
        right_to_work_status="British citizen",
    )
    return validate_extraction(data, today=date(2026, 11, 1))


def test_matching_age_is_not_flagged():
    assert _check(36) == []


def test_age_mismatch_is_flagged():
    assert _check(31) == ["Stated age 31 does not match age 36 calculated from date of birth 1990-04-12"]


def test_future_date_of_birth_is_flagged():
    assert _check(0, dob=date(2030, 1, 1)) == ["Date of birth 2030-01-01 is in the future"]
