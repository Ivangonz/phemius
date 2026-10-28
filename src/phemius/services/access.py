"""Access mode, bind address and the access token. The token is never logged."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass

import structlog

from phemius.config import AccessMode
from phemius.store import access as access_store

TOKEN_PREFIX = "phm_"
LOOPBACK_HOST = "127.0.0.1"
ALL_INTERFACES_HOST = "0.0.0.0"

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
