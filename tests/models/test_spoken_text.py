from phemius.models.spoken_text import CODE_EXAMPLE, to_spoken_text


def test_fenced_code_becomes_a_described_code_example() -> None:
    text = "Install it:\n\n```bash\nuv sync\nuv run phemius\n```\n\nDone."

    spoken = to_spoken_text(text)

    assert "```" not in spoken
    assert "[Code example in bash, 2 lines." in spoken
    assert "uv sync\nuv run phemius\n[End of code example.]" in spoken
    assert spoken.endswith("Done.")


def test_tilde_fence_and_unclosed_fence_become_code_examples() -> None:
    spoken = to_spoken_text("~~~\nx = 1\n~~~\n\n```python\nprint(1)")

    assert "~~~" not in spoken and "```" not in spoken
    assert len(CODE_EXAMPLE.findall(spoken)) == 2


def test_indented_code_becomes_a_code_example() -> None:
    text = "Run this:\n\n    make check\n    make run\n\nThen open the app."

    spoken = to_spoken_text(text)

    assert "[Code example, 2 lines." in spoken
    assert "make check\nmake run\n[End of code example.]" in spoken


def test_indented_list_items_are_not_code() -> None:
    text = "Steps:\n\n    - install\n    - run"

    assert to_spoken_text(text) == text


def test_code_inside_a_fence_is_kept_verbatim() -> None:
    code = "def main():\n    fetch('https://example.com/api')\n\n    return [1](2)"

    spoken = to_spoken_text(f"```python\n{code}\n```")

    assert f"\n{code}\n" in spoken
    assert spoken.count("[Code example") == 1


def test_table_is_flattened_into_label_value_lines() -> None:
    text = (
        "Settings:\n\n"
        "| Name | Default |\n|:-----|--------:|\n| port | 8000 |\n| host | |\n\nEnd."
    )

    spoken = to_spoken_text(text)

    assert "|" not in spoken
    assert "A table with columns Name and Default." in spoken
    assert "Name: port; Default: 8000." in spoken
    assert "Name: host." in spoken
    assert spoken.endswith("End.")


def test_pipes_without_a_table_separator_are_left_alone() -> None:
    assert to_spoken_text("Use a | b to pipe.") == "Use a | b to pipe."


def test_links_keep_their_text_and_lose_the_url() -> None:
    text = (
        'Read [the guide](https://example.com/guide "Guide") and [ref docs][1].\n'
        "See https://example.com/a?b=c, or <https://example.com>.\n\n"
        "[1]: https://example.com/ref"
    )

    spoken = to_spoken_text(text)

    assert "http" not in spoken and "](" not in spoken
    assert "Read the guide and ref docs." in spoken
    assert "See or ." not in spoken
    assert spoken.startswith("Read the guide and ref docs.\nSee, or.")


def test_images_are_removed() -> None:
    text = "Before ![Architecture diagram](images/arch.png) after."

    assert to_spoken_text(text) == "Before after."


def test_plain_prose_is_unchanged() -> None:
    text = "# Title\n\nPhemius turns docs into audio.\n\n- One\n- Two"

    assert to_spoken_text(text) == text
