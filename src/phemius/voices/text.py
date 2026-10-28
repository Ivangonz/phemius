"""Script helpers shared by voice engines."""

import re


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
