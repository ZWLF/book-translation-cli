from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from booksmith.models import ExtractedBook, TocEntry


def _flatten_outline(reader: PdfReader, outline: list[Any]) -> list[TocEntry]:
    entries: list[TocEntry] = []
    for item in outline:
        if isinstance(item, list):
            entries.extend(_flatten_outline(reader, item))
            continue
        title = getattr(item, "title", None)
        if title:
            page_index: int | None = None
            try:
                page_index = reader.get_destination_page_number(item)
            except Exception:
                page_index = None
            entries.append(TocEntry(title=str(title).strip(), page_index=page_index))
    return entries


def extract_pdf(path: Path) -> ExtractedBook:
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    raw_text = "\n\n".join(page for page in pages if page).strip()
    toc: list[TocEntry] = []
    outline = getattr(reader, "outline", None)
    if outline:
        toc = _flatten_outline(reader, outline)
    return ExtractedBook(title=path.stem, raw_text=raw_text, toc=toc, pages=pages)
