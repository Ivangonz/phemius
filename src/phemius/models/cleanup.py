"""Tidy a model's script reply so the voice reads only the script.

Small local models often wrap the script in a code fence, open with "Here is the
script:" or keep markdown despite the prompt.
"""

import re

FENCE_LINE = re.compile(r"^\s*```[\w-]*\s*$", re.M)
# Only a lead-in that ends with a colon, so "Here is how it works." stays.
PREAMBLE = re.compile(
    r"\A\s*(?:(?:sure|okay|ok|certainly|of course)\b[!,.]?\s*)?"
    r"(?:here(?:'s| is| are)|below is)\b[^\n]*:[ \t]*\n",
    re.I,
)
HEADING_MARKER = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.M)
BULLET_MARKER = re.compile(r"^[ \t]*[-*+][ \t]+", re.M)
EMPHASIS_MARKER = re.compile(r"\*{1,3}|__")


def clean_script(reply: str) -> str:
    script = PREAMBLE.sub("", reply)
    script = FENCE_LINE.sub("", script)
    script = HEADING_MARKER.sub("", script)
    script = BULLET_MARKER.sub("", script)
    script = EMPHASIS_MARKER.sub("", script)
    return re.sub(r"\n{3,}", "\n\n", script).strip()
