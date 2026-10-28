"""Saved settings: one JSON value per key."""

import json
import time
from collections.abc import Mapping

from phemius.store.database import transaction


def read_settings() -> dict[str, object]:
    with transaction() as connection:
        rows = connection.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: json.loads(row["value"]) for row in rows}


def save_settings(changes: Mapping[str, object]) -> None:
    """Save all changes in one transaction. `None` deletes a key."""
    updated = time.time()
    with transaction() as connection:
        for key, value in changes.items():
            if value is None:
                connection.execute("DELETE FROM settings WHERE key = ?", (key,))
                continue
            connection.execute(
                "INSERT INTO settings (key, value, updated) VALUES (?, ?, ?)"
                " ON CONFLICT (key) DO UPDATE"
                " SET value = excluded.value, updated = excluded.updated",
                (key, json.dumps(value), updated),
            )
