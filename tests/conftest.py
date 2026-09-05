from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from ai_it_support_assistant.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
