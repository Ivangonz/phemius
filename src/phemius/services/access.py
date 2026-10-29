"""Access mode, bind address and the access token. The token is never logged."""

import hashlib
import hmac
import ipaddress
import secrets
import time
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
# Long enough for a long listen; the player fetches a fresh URL when one expires.
AUDIO_URL_LIFETIME_SECONDS = 6 * 60 * 60
AUDIO_URL_KEY_LABEL = b"phemius-audio-url-v1"
# Unix seconds fit in 12 digits for millennia; a longer value is not ours.
MAX_EXPIRES_DIGITS = 12

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AudioUrlSignature:
    expires: int
    signature: str | None


@dataclass(frozen=True)
class AccessStatus:
    # The mode the server started with; a saved change applies on the next start.
    active_mode: AccessMode
    is_token_required: bool
    has_token: bool
    is_token_from_env: bool


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


def describe_access(active_mode: AccessMode) -> AccessStatus:
    """What the Settings screen may know about access. Never the token or hash."""
    return AccessStatus(
        active_mode=active_mode,
        is_token_required=is_token_required(active_mode),
        has_token=access_store.read_token_hash() is not None,
        is_token_from_env=read_env(ENV_TOKEN_NAME) is not None,
    )


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


def sign_audio_url(audio_id: int) -> AudioUrlSignature:
    """Sign one audio file's URL until it expires.

    Without a token there is nothing to sign with, so the signature is None.
    """
    expires = int(time.time()) + AUDIO_URL_LIFETIME_SECONDS
    stored_hash = access_store.read_token_hash()
    if stored_hash is None:
        return AudioUrlSignature(expires=expires, signature=None)
    signature = _audio_signature(stored_hash, audio_id, expires)
    return AudioUrlSignature(expires=expires, signature=signature)


def is_valid_audio_signature(
    audio_id: int, expires: str | None, signature: str | None
) -> bool:
    expires_at = _unix_seconds(expires)
    if not signature or expires_at is None or expires_at < time.time():
        return False
    stored_hash = access_store.read_token_hash()
    if stored_hash is None:
        return False
    expected = _audio_signature(stored_hash, audio_id, expires_at)
    # compare_digest raises on non-ASCII text, so compare bytes.
    return hmac.compare_digest(expected.encode(), signature.encode())


def _unix_seconds(value: str | None) -> int | None:
    # isdigit() alone accepts characters such as "²" that int() rejects.
    if not value or len(value) > MAX_EXPIRES_DIGITS:
        return None
    return int(value) if value.isascii() and value.isdecimal() else None


def _audio_signature(token_hash: str, audio_id: int, expires: int) -> str:
    # Keyed from the token hash, so regenerating the token revokes every URL.
    key = hmac.new(token_hash.encode(), AUDIO_URL_KEY_LABEL, hashlib.sha256)
    message = f"{audio_id}:{expires}".encode()
    return hmac.new(key.digest(), message, hashlib.sha256).hexdigest()


def _new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def _hash(token: str) -> str:
    # A plain SHA-256 is enough: the token is 256 random bits, not a password,
    # so a slow key-derivation function would add latency to every request.
    return hashlib.sha256(token.encode()).hexdigest()
