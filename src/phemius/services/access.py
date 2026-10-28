"""Access mode, bind address and the access token. The token is never logged."""

import hashlib
import hmac
import ipaddress
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


def bind_options(mode: AccessMode, host: str | None = None) -> BindOptions:
    """Where the server listens: the mode's address, or `host` when it is safe.

    A proxy is expected on the same host.
    """
    is_proxy_trusted = mode == "proxy"
    if host is not None:
        _refuse_unprotected_host(mode, host)
        return BindOptions(host=host, is_proxy_trusted=is_proxy_trusted)
    if mode == "network":
        return BindOptions(host=ALL_INTERFACES_HOST, is_proxy_trusted=False)
    return BindOptions(host=LOOPBACK_HOST, is_proxy_trusted=is_proxy_trusted)


def _refuse_unprotected_host(mode: AccessMode, host: str) -> None:
    """Without a token, only this computer may reach the library."""
    if is_token_required(mode) or is_loopback_host(host):
        return
    raise PhemiusError(
        f"Refusing to listen on {host} in local access mode: anyone who can reach"
        " it could read and delete the library without an access token.",
        hint=f"Set {ENV_PREFIX}ACCESS_MODE=network to require an access token"
        f" (choose it with {ENV_PREFIX}{ENV_TOKEN_NAME}), or listen on"
        f" {LOOPBACK_HOST}.",
    )


def is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # A host name other than localhost may resolve beyond this computer.
        return False


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
