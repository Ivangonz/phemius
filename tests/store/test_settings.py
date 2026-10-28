from pathlib import Path

from phemius.store import database
from phemius.store import settings as settings_store


def test_saved_settings_survive_reinit(isolated_env: Path) -> None:
    db_path = isolated_env / "library.db"
    database.init_database(db_path)
    settings_store.save_settings({"model": "local/model", "script_max_tokens": 500})

    database.init_database(db_path)

    assert settings_store.read_settings() == {
        "model": "local/model",
        "script_max_tokens": 500,
    }


def test_saving_none_deletes_the_setting(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")
    settings_store.save_settings({"model": "local/model", "default_voice": "bf_emma"})

    settings_store.save_settings({"model": None})

    assert settings_store.read_settings() == {"default_voice": "bf_emma"}
