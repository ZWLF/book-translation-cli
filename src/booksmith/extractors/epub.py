from __future__ import annotations

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

from booksmith.models import ExtractedBook, TocEntry


def _flatten_toc(items: list[Any] | tuple[Any, ...]) -> list[TocEntry]:
    entries: list[TocEntry] = []
    for item in items:
        if isinstance(item, list | tuple):
            entries.extend(_flatten_toc(item))
            continue
        title = getattr(item, "title", None)
        if title:
            entries.append(TocEntry(title=str(title).strip()))
    return entries


def _ordered_documents(book: epub.EpubBook) -> list[Any]:
    ordered: list[Any] = []
    by_id = {item.get_id(): item for item in book.get_items_of_type(ITEM_DOCUMENT)}
    for entry in book.spine:
        item_id = entry[0] if isinstance(entry, tuple) else entry
        if item_id == "nav":
            continue
        item = by_id.get(item_id)
        if item:
            ordered.append(item)
    if ordered:
        return ordered
    return list(book.get_items_of_type(ITEM_DOCUMENT))


def extract_epub(path: Path) -> ExtractedBook:
    book = epub.read_epub(str(path))
    documents = _ordered_documents(book)
    text_sections: list[str] = []
    for document in documents:
        soup = BeautifulSoup(document.get_content(), "html.parser")
        text = soup.get_text("\n", strip=True)
        if text:
            text_sections.append(text)
    metadata = book.get_metadata("DC", "title")
    title = metadata[0][0] if metadata else path.stem
    return ExtractedBook(
        title=title,
        raw_text="\n\n".join(text_sections).strip(),
        toc=_flatten_toc(book.toc),
        pages=text_sections,
    )
