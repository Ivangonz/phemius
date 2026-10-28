"""Extract plain text from supported document types."""

import re
from pathlib import Path

PLAIN_TEXT_TYPES = {".md", ".markdown", ".txt", ".rst"}
HTML_TYPES = {".html", ".htm"}
SUPPORTED = PLAIN_TEXT_TYPES | HTML_TYPES | {".docx", ".pdf"}


def extract_text(path: Path) -> str:
    extension = path.suffix.lower()
    if extension in PLAIN_TEXT_TYPES:
        return path.read_text(encoding="utf-8", errors="replace")
    if extension in HTML_TYPES:
        return _strip_html(path.read_text(encoding="utf-8", errors="replace"))
    if extension == ".docx":
        return _extract_docx(path)
    if extension == ".pdf":
        return _extract_pdf(path)
    raise ValueError(f"Unsupported file type: {extension}")


def _strip_html(raw: str) -> str:
    without_scripts = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", raw)
    return re.sub(r"<[^>]+>", " ", without_scripts)


def _extract_docx(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())


def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def guess_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip() or fallback
        if line:
            return line[:80]
    return fallback
