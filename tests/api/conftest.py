from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app
from tests.models.fakes import UseScriptModel
from tests.services.test_runner import BlockingScriptModel


@pytest.fixture
def network_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("PHEMIUS_ACCESS_MODE", "network")
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def blocking_model(use_script_model: UseScriptModel) -> Iterator[BlockingScriptModel]:
    model = BlockingScriptModel()
    use_script_model(model)
    yield model
    model.release.set()
