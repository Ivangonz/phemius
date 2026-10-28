"""Checksum-verified downloads of voice model files."""

import hashlib
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path

from phemius.errors import VoiceError

CHUNK_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 30
RETRY_HINT = "Check your internet connection and try again."

type Fetch = Callable[[str], Iterator[bytes]]
type Progress = Callable[[int, int], None]
"""Called with `(bytes_done, bytes_total)` as a download proceeds."""


def fetch_url(url: str) -> Iterator[bytes]:
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        while chunk := response.read(CHUNK_BYTES):
            yield chunk


def download_verified(
    url: str,
    destination: Path,
    *,
    sha256: str,
    size_bytes: int,
    fetch: Fetch,
    on_chunk: Callable[[int], None],
) -> None:
    """Download `url` to `destination`, which appears only if its SHA-256 matches.

    Raises `VoiceError` on a network failure or a checksum mismatch, leaving no
    partial file behind.
    """
    partial = destination.with_name(f"{destination.name}.part")
    try:
        digest = _write_chunks(fetch(url), partial, size_bytes, on_chunk)
        if digest != sha256:
            raise VoiceError(
                f"{destination.name} failed its checksum check.",
                hint="The download was corrupted. Try again.",
            )
        partial.replace(destination)
    except OSError as error:
        raise VoiceError(
            f"Could not download {destination.name}.", RETRY_HINT
        ) from error
    finally:
        partial.unlink(missing_ok=True)


def _write_chunks(
    chunks: Iterator[bytes],
    path: Path,
    size_bytes: int,
    on_chunk: Callable[[int], None],
) -> str:
    digest = hashlib.sha256()
    written = 0
    with path.open("wb") as file:
        for chunk in chunks:
            written += len(chunk)
            # Stop early on an oversized response instead of filling the disk.
            if written > size_bytes:
                break
            file.write(chunk)
            digest.update(chunk)
            on_chunk(len(chunk))
    return digest.hexdigest()
