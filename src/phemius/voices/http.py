"""HTTP plumbing shared by the hosted voice engines."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import httpx2
import structlog

from phemius.errors import VoiceError

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Provider:
    """How a hosted engine names itself in logs and errors, and hints for fixes."""

    engine: str
    name: str
    unreachable_hint: str
    hint_for: Callable[[httpx2.Response], str | None]


@contextmanager
def session(
    provider: Provider,
    base_url: str,
    headers: dict[str, str],
    timeout: float,
    transport: httpx2.BaseTransport | None = None,
) -> Iterator[httpx2.Client]:
    """An HTTP client whose network failures raise `VoiceError`."""
    try:
        with httpx2.Client(
            base_url=base_url, headers=headers, timeout=timeout, transport=transport
        ) as client:
            yield client
    except httpx2.TransportError as error:
        log.warning(
            "voice_request_failed", engine=provider.engine, error=type(error).__name__
        )
        raise VoiceError(
            f"Could not reach {provider.name}.", hint=provider.unreachable_hint
        ) from error


def raise_for_status(response: httpx2.Response, provider: Provider) -> None:
    # Provider messages can echo part of the key, so errors carry only the status.
    if response.is_success:
        return
    log.warning(
        "voice_request_failed", engine=provider.engine, status=response.status_code
    )
    raise VoiceError(
        f"{provider.name} returned {response.status_code}.",
        hint=provider.hint_for(response),
    )


def error_field(response: httpx2.Response, *path: str) -> object:
    """A field of a JSON error body, such as `error.code`, or None."""
    try:
        value: object = response.json()
    except ValueError:
        return None
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return value
