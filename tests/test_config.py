from pathlib import Path

import pytest

from phemius.config import DEFAULT_MODEL, load_config


def test_env_vars_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_MODEL", "local/model")
    monkeypatch.setenv("PHEMIUS_FORMAT", "M4A")

    loaded = load_config()

    assert loaded.model == "local/model"
    assert loaded.output_format == "m4a"


def test_defaults_use_home_data_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHEMIUS_DATA_DIR")

    loaded = load_config()

    assert loaded.data_dir == Path.home() / ".phemius"
    assert loaded.model == DEFAULT_MODEL
    assert loaded.output_format == "wav"


def test_empty_env_var_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_MODEL", "")

    assert load_config().model == DEFAULT_MODEL


def test_api_key_is_hidden_from_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret")

    assert "sk-or-secret" not in repr(load_config())
