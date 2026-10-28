"""Access mode, bind address and the access token. The token is never logged."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass

import structlog

from phemius.config import ENV_PREFIX, AccessMode, read_env
from phemius.errors import PhemiusError, SettingLockedError
from phemius.store import access as access_store

TOKEN_PREFIX = "phm_"
LOOPBACK_HOST = "127.0.0.1"
ALL_INTERFACES_HOST = "0.0.0.0"
ENV_TOKEN_NAME = "ACCESS_TOKEN"
MIN_ENV_TOKEN_LENGTH = 16

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BindOptions:
    host: str
    is_proxy_trusted: bool


def bind_options(mode: AccessMode) -> BindOptions:
    """Where the server listens. A proxy is expected on the same host."""
    if mode == "network":
        return BindOptions(host=ALL_INTERFACES_HOST, is_proxy_trusted=False)
    return BindOptions(host=LOOPBACK_HOST, is_proxy_trusted=mode == "proxy")


def is_token_required(mode: AccessMode) -> bool:
    return mode != "local"


def prepare_access_token(mode: AccessMode) -> str | None:
    """Apply PHEMIUS_ACCESS_TOKEN, or create a token when the mode needs one.

    Returns a token only when newly created, so it can be shown once.
    """
    env_token = env_access_token()
    if env_token is not None:
        # Replacing the hash on every start makes changing the variable rotate it.
        access_store.save_token_hash(_hash(env_token))
        log.info("access_token_from_env")
        return None
    return ensure_access_token() if is_token_required(mode) else None


def env_access_token() -> str | None:
    token = read_env(ENV_TOKEN_NAME)
    if token is not None and len(token) < MIN_ENV_TOKEN_LENGTH:
        raise PhemiusError(
            f"{ENV_PREFIX}{ENV_TOKEN_NAME} must be at least"
            f" {MIN_ENV_TOKEN_LENGTH} characters.",
            hint="Set it to a long random value, for example from"
            " `openssl rand -hex 32`.",
        )
    return token


def ensure_access_token() -> str | None:
    """Create the token if none exists. Returns it only when newly created."""
    if access_store.read_token_hash() is not None:
        return None
    token = _new_token()
    access_store.save_token_hash(_hash(token))
    log.info("access_token_created")
    return token


def regenerate_token() -> str:
    """Replace the token. The old one stops working immediately."""
    if read_env(ENV_TOKEN_NAME) is not None:
        raise SettingLockedError(
            "The access token is set by an environment variable.",
            hint=f"Change {ENV_PREFIX}{ENV_TOKEN_NAME} and restart Phemius.",
        )
    token = _new_token()
    access_store.save_token_hash(_hash(token))
    log.info("access_token_regenerated")
    return token


def is_valid_token(candidate: str | None) -> bool:
    stored_hash = access_store.read_token_hash()
    if not candidate or stored_hash is None:
        return False
    return hmac.compare_digest(_hash(candidate), stored_hash)


def _new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def _hash(token: str) -> str:
    # A plain SHA-256 is enough: the token is 256 random bits, not a password,
    # so a slow key-derivation function would add latency to every request.
    return hashlib.sha256(token.encode()).hexdigest()
