"""Tests for PersonKey generation."""

import pytest

from hr_onboarding.person_key import UNKNOWN_PERSON, extract_person_key, make_person_key
from tests.fakes import FakeLLM


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Jane Doe", "jane-doe"),
        ("  JANE   DOE  ", "jane-doe"),
        ("José Núñez", "jose-nunez"),
        ("O'Brien, Mary-Jane", "o-brien-mary-jane"),
        ("Jane/../../Doe", "jane-doe"),  # no path traversal into other folders
        (None, UNKNOWN_PERSON),
        ("", UNKNOWN_PERSON),
        ("???", UNKNOWN_PERSON),
    ],
)
def test_make_person_key(name, expected):
    assert make_person_key(name) == expected


def test_person_key_is_length_limited_without_trailing_hyphen():
    key = make_person_key("a" * 63 + " b")
    assert len(key) <= 64
    assert not key.endswith("-")


def test_extract_person_key_uses_llm_name():
    assert extract_person_key(FakeLLM('{"full_name": "Alex Example"}'), "doc") == "alex-example"


def test_extract_person_key_null_name_is_unknown():
    assert extract_person_key(FakeLLM('{"full_name": null}'), "doc") == UNKNOWN_PERSON
