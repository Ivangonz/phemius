"""Liveness check: the database is readable and the data folder is writable."""

import tempfile
from pathlib import Path

from phemius.config import load_config
from phemius.errors import ServiceUnavailableError
from phemius.store import database


def check_health() -> None:
    try:
        database.ping()
    except Exception as error:
        raise ServiceUnavailableError(
            "The library database is not readable.",
            hint="Check the file permissions of the data folder.",
        ) from error
    data_dir = load_config().data_dir
    if not is_writable(data_dir):
        raise ServiceUnavailableError(
            "The data folder is not writable.",
            hint=f"Make {data_dir} writable or set PHEMIUS_DATA_DIR.",
        )


def is_writable(folder: Path) -> bool:
    try:
        with tempfile.TemporaryFile(dir=folder):
            pass
    except OSError:
        return False
    return True
