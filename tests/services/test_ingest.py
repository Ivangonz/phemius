from pathlib import Path

import pytest

from phemius.services.ingest import extract_text, guess_title


def test_extract_text_strips_html_scripts_and_tags(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text("<html><script>alert(1)</script><p>Hello <b>docs</b></p></html>")

    text = extract_text(page)

    assert "alert" not in text
    assert "<" not in text
    assert "Hello" in text and "docs" in text


def test_extract_text_rejects_unsupported_type(tmp_path: Path) -> None:
    image = tmp_path / "diagram.png"
    image.write_bytes(b"\x89PNG")

    with pytest.raises(ValueError, match="Unsupported"):
        extract_text(image)


def test_guess_title_prefers_markdown_heading() -> None:
    assert guess_title("\n# Deploy Guide\nBody", "fallback") == "Deploy Guide"
    assert guess_title("First line\nSecond", "fallback") == "First line"
    assert guess_title("   \n", "fallback") == "fallback"
