from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from book_translator.models import ExtractedBook, TocEntry


def _flatten_outline(outline: list[Any]) -> list[TocEntry]:
    entries: list[TocEntry] = []
    for item in outline:
        if isinstance(item, list):
            entries.extend(_flatten_outline(item))
            continue
        title = getattr(item, "title", None)
        if title:
            entries.append(TocEntry(title=str(title).strip()))
    return entries


def extract_pdf(path: Path) -> ExtractedBook:
    reader = PdfReader(str(path))
    raw_text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    toc: list[TocEntry] = []
    outline = getattr(reader, "outline", None)
    if outline:
        toc = _flatten_outline(outline)
    return ExtractedBook(title=path.stem, raw_text=raw_text, toc=toc)
