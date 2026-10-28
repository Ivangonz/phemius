"""The access token's hash. The token itself is never stored."""

import time

from phemius.store.database import transaction


def read_token_hash() -> str | None:
    with transaction() as connection:
        row = connection.execute(
            "SELECT token_hash FROM access_token WHERE id = 1"
        ).fetchone()
    return str(row["token_hash"]) if row else None


def save_token_hash(token_hash: str) -> None:
    """Replace the token hash, so the previous token stops working at once."""
    with transaction() as connection:
        connection.execute(
            "INSERT INTO access_token (id, token_hash, created) VALUES (1, ?, ?)"
            " ON CONFLICT (id) DO UPDATE"
            " SET token_hash = excluded.token_hash, created = excluded.created",
            (token_hash, time.time()),
        )
