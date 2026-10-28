"""Liveness check: the database is readable and the data folder is writable."""

import tempfile

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
    try:
        with tempfile.TemporaryFile(dir=data_dir):
            pass
    except OSError as error:
        raise ServiceUnavailableError(
            "The data folder is not writable.",
            hint=f"Make {data_dir} writable or set PHEMIUS_DATA_DIR.",
        ) from error
