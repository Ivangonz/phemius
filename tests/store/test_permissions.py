import os
import stat
from pathlib import Path

import pytest

from phemius.store import database, permissions


def mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_new_library_is_private_to_its_owner(isolated_env: Path) -> None:
    db_path = isolated_env / "library.db"
    database.init_database(db_path)

    with database.transaction() as connection:
        connection.execute("INSERT INTO docs (source) VALUES ('deploy-guide.md')")
        assert mode_of(Path(f"{db_path}-wal")) == 0o600
        assert mode_of(Path(f"{db_path}-shm")) == 0o600
    assert mode_of(isolated_env) == 0o700
    assert mode_of(db_path) == 0o600


def test_tightens_a_library_readable_by_others(isolated_env: Path) -> None:
    db_path = isolated_env / "library.db"
    wal_path = Path(f"{db_path}-wal")
    isolated_env.mkdir(mode=0o755)
    db_path.touch(mode=0o644)
    wal_path.touch(mode=0o640)
    os.chmod(isolated_env, 0o755)
    os.chmod(db_path, 0o644)
    os.chmod(wal_path, 0o640)

    tightened = permissions.tighten_library_permissions(isolated_env, db_path)

    assert tightened == [isolated_env, db_path, wal_path]
    assert mode_of(isolated_env) == 0o700
    assert mode_of(db_path) == 0o600
    assert mode_of(wal_path) == 0o600


def test_leaves_a_private_library_alone(isolated_env: Path) -> None:
    db_path = isolated_env / "library.db"
    database.init_database(db_path)

    assert permissions.tighten_library_permissions(isolated_env, db_path) == []


def test_skips_tightening_without_posix_modes(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_env.mkdir()
    os.chmod(isolated_env, 0o755)
    monkeypatch.setattr(os, "name", "nt")

    tightened = permissions.tighten_library_permissions(
        isolated_env, isolated_env / "library.db"
    )

    assert tightened == []
    assert mode_of(isolated_env) == 0o755
