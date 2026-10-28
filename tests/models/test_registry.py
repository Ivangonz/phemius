import pytest

from phemius.config import load_config
from phemius.errors import ModelError
from phemius.models import get_script_model
from phemius.models.offline import OfflineModel
from phemius.models.openai_compatible import OpenAICompatibleModel


def test_no_provider_configured_uses_offline_rules() -> None:
    assert isinstance(get_script_model(load_config()), OfflineModel)


def test_openrouter_key_selects_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret")

    assert isinstance(get_script_model(load_config()), OpenAICompatibleModel)


def test_unknown_provider_raises_with_valid_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "mystery")

    with pytest.raises(ModelError, match="mystery") as raised:
        get_script_model(load_config())

    assert raised.value.hint is not None
    assert "offline" in raised.value.hint and "openrouter" in raised.value.hint
