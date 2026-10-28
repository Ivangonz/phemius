"""Script helpers shared by voice engines."""

import re
import textwrap


def split_chunks(script: str, limit: int = 400) -> list[str]:
    """Split a script into sentence-aligned chunks small enough for local models."""
    chunks: list[str] = []
    for paragraph in re.split(r"\n\s*\n", script):
        buffer = ""
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            if len(buffer) + len(sentence) + 1 > limit and buffer:
                chunks.append(buffer)
                buffer = sentence
            else:
                buffer = f"{buffer} {sentence}".strip()
        if buffer:
            chunks.append(buffer)
    return chunks


def pack_chunks(script: str, limit: int) -> list[str]:
    """Sentence-aligned chunks of at most `limit` characters, for hosted engines.

    Unlike `split_chunks`, paragraphs share a chunk when they fit, so a script
    needs as few requests as possible.
    """
    pieces = [
        piece
        for chunk in split_chunks(script, limit)
        for piece in textwrap.wrap(chunk, limit, break_on_hyphens=False)
    ]
    packed: list[str] = []
    for piece in pieces:
        if packed and len(packed[-1]) + len(piece) + 2 <= limit:
            packed[-1] = f"{packed[-1]}\n\n{piece}"
        else:
            packed.append(piece)
    return packed
