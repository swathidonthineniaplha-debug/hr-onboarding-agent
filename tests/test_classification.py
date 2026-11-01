"""Tests for classification and the shared JSON/retry helper."""

import pytest

from hr_onboarding.classification import classify_document
from hr_onboarding.llm import StructuredOutputError
from hr_onboarding.llm.mock_provider import MockLLMClient
from hr_onboarding.models import DocumentCategory
from tests.fakes import FakeLLM

VALID = '{"category": "Passport", "confidence": 0.93, "reason": "Has a passport number"}'


def test_valid_reply_is_parsed():
    result = classify_document(FakeLLM(VALID), "doc")
    assert result.category is DocumentCategory.PASSPORT
    assert result.confidence == 0.93


def test_markdown_code_fence_is_tolerated():
    result = classify_document(FakeLLM(f"```json\n{VALID}\n```"), "doc")
    assert result.category is DocumentCategory.PASSPORT


def test_invalid_category_is_retried_with_feedback():
    llm = FakeLLM('{"category": "Visa", "confidence": 0.9, "reason": "x"}', VALID)
    assert classify_document(llm, "doc").category is DocumentCategory.PASSPORT
    assert len(llm.requests) == 2
    assert llm.requests[0].feedback is None
    assert "category" in llm.requests[1].feedback  # the model is told what was wrong


def test_confidence_outside_range_is_rejected():
    llm = FakeLLM('{"category": "Passport", "confidence": 1.5, "reason": "x"}', VALID)
    classify_document(llm, "doc")
    assert len(llm.requests) == 2


def test_gives_up_after_two_invalid_replies():
    with pytest.raises(StructuredOutputError):
        classify_document(FakeLLM("not json", "still not json"), "doc")


def test_mock_classifies_clear_documents():
    mock = MockLLMClient()
    assert classify_document(mock, "Passport number: AB000001\nNationality: Testlandian").category \
        is DocumentCategory.PASSPORT
    assert classify_document(mock, "Driving licence\nLicence no: DL000001\nCategories: B").category \
        is DocumentCategory.DRIVING_LICENCE


def test_mock_gives_low_confidence_other_for_vague_text():
    result = classify_document(MockLLMClient(), "Saw someone at reception, ID seen.")
    assert result.category is DocumentCategory.OTHER
    assert result.confidence < 0.8
