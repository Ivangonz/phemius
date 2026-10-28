from pathlib import Path

import pytest

from phemius.config import DEFAULT_MODEL, load_config
from phemius.errors import PhemiusError
from phemius.store import database
from phemius.store import settings as settings_store


@pytest.fixture
def saved_model(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")
    settings_store.save_settings({"model": "saved/model"})


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


def test_script_provider_defaults_to_offline_without_a_key() -> None:
    assert load_config().script_provider == "offline"


def test_script_provider_defaults_to_openrouter_with_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret")

    assert load_config().script_provider == "openrouter"


def test_script_provider_env_var_wins_over_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret")
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "Offline")

    assert load_config().script_provider == "offline"


def test_saved_key_selects_openrouter_by_default(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")
    settings_store.save_settings({"openrouter_api_key": "sk-or-secret"})

    assert load_config().script_provider == "openrouter"


def test_saved_script_provider_wins_over_the_key(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")
    settings_store.save_settings(
        {"openrouter_api_key": "sk-or-secret", "script_provider": "offline"}
    )

    assert load_config().script_provider == "offline"


def test_defaults_apply_before_database_is_initialized() -> None:
    loaded = load_config()

    assert loaded.default_voice is None
    assert loaded.output_format == "wav"


@pytest.mark.usefixtures("saved_model")
def test_saved_setting_overrides_default() -> None:
    assert load_config().model == "saved/model"


@pytest.mark.usefixtures("saved_model")
def test_env_var_overrides_saved_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_MODEL", "env/model")

    assert load_config().model == "env/model"


def test_invalid_env_value_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_FORMAT", "flac")

    with pytest.raises(PhemiusError) as raised:
        load_config()

    assert raised.value.field == "output_format"
    assert raised.value.hint is not None
    assert "PHEMIUS_FORMAT" in raised.value.hint


def test_voice_list_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_OPENAI_SPEECH_VOICES", " nova ,, onyx ")

    assert load_config().openai_speech_voices == "nova,onyx"


def test_voice_list_without_ids_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_ELEVENLABS_VOICES", " , ")

    with pytest.raises(PhemiusError) as raised:
        load_config()

    assert raised.value.field == "elevenlabs_voices"
