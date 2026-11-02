"""Shared pytest fixtures: in-memory blobs and a throwaway SQLite database."""

from datetime import date

import pytest

from hr_onboarding.llm.mock_provider import MockLLMClient
from hr_onboarding.routing import ALL_CONTAINERS
from hr_onboarding.service import OnboardingService
from hr_onboarding.storage import EmployeeRepository, InMemoryBlobStore


@pytest.fixture
def blobs():
    store = InMemoryBlobStore()
    store.ensure_containers(ALL_CONTAINERS)
    return store


@pytest.fixture
def repository(tmp_path):
    repo = EmployeeRepository(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    repo.create_schema()
    yield repo
    repo.dispose()  # release the file so Windows can delete tmp_path


@pytest.fixture
def service(blobs, repository):
    return OnboardingService(MockLLMClient(), blobs, repository, today=date(2026, 11, 1))
