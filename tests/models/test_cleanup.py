import pytest

from phemius.models.cleanup import clean_script


@pytest.mark.parametrize(
    "reply",
    [
        "```\nThis document covers setup.\n```",
        "```text\nThis document covers setup.\n```\n",
        "Here is the script:\n\nThis document covers setup.",
        "Sure! Here's the spoken script for Setup:\nThis document covers setup.",
        "Certainly, here is your script:\n\n```md\nThis document covers setup.\n```",
    ],
)
def test_fences_and_preambles_are_stripped(reply: str) -> None:
    assert clean_script(reply) == "This document covers setup."


def test_markdown_markers_are_removed() -> None:
    reply = "## Overview\n\nThis is **important**.\n\n- First, install it."

    assert clean_script(reply) == "Overview\n\nThis is important.\n\nFirst, install it."


def test_a_first_sentence_that_mentions_here_is_kept() -> None:
    reply = "Here is how the billing service works.\n\nIt runs nightly."

    assert clean_script(reply) == reply


def test_identifiers_with_underscores_are_kept() -> None:
    assert clean_script("Set max_tokens to 100.") == "Set max_tokens to 100."
