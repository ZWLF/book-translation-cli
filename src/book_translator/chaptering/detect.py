from __future__ import annotations

import re

from book_translator.models import Chapter, ExtractedBook
from book_translator.utils import slugify

HEADING_PATTERN = re.compile(r"(?im)^(chapter\s+[^\n]+|part\s+[^\n]+|section\s+[^\n]+)$")


def detect_chapters(
    extracted: ExtractedBook,
    strategy: str = "toc-first",
    manual_titles: list[str] | None = None,
) -> list[Chapter]:
    normalized_strategy = strategy.lower()

    if normalized_strategy == "manual":
        if not manual_titles:
            raise ValueError("Manual chapter strategy requires manual titles.")
        return _split_by_titles(extracted.raw_text, manual_titles)

    if normalized_strategy in {"toc-first", "auto"} and extracted.toc:
        chapters = _split_by_toc_pages(extracted)
        if chapters:
            return chapters
        toc_titles = [entry.title for entry in extracted.toc]
        chapters = _split_by_titles(extracted.raw_text, toc_titles)
        if chapters:
            return chapters

    if normalized_strategy in {"toc-first", "auto", "rule-only"}:
        chapters = _split_by_headings(extracted.raw_text)
        if chapters:
            return chapters

    if manual_titles:
        chapters = _split_by_titles(extracted.raw_text, manual_titles)
        if chapters:
            return chapters

    return [
        Chapter(
            chapter_id=f"{slugify(extracted.title)}-chapter-0",
            chapter_index=0,
            title=extracted.title,
            text=extracted.raw_text.strip(),
        )
    ]


def _split_by_titles(raw_text: str, titles: list[str]) -> list[Chapter]:
    matched_occurrences = _find_title_occurrences(raw_text, titles)
    if not matched_occurrences:
        return []

    chapters: list[Chapter] = []
    for index, (title, _start, end) in enumerate(matched_occurrences):
        next_start = (
            matched_occurrences[index + 1][1]
            if index + 1 < len(matched_occurrences)
            else len(raw_text)
        )
        body = raw_text[end:next_start].strip()
        chapters.append(
            Chapter(
                chapter_id=f"{slugify(title)}-{index}",
                chapter_index=index,
                title=title,
                text=body,
            )
        )
    return chapters


def _split_by_toc_pages(extracted: ExtractedBook) -> list[Chapter]:
    if not extracted.pages:
        return []

    page_entries = [
        entry
        for entry in extracted.toc
        if entry.page_index is not None and 0 <= entry.page_index < len(extracted.pages)
    ]
    if not page_entries:
        return []

    chapters: list[Chapter] = []
    for index, entry in enumerate(page_entries):
        start_page = entry.page_index
        next_page = (
            page_entries[index + 1].page_index
            if index + 1 < len(page_entries)
            else len(extracted.pages)
        )
        if next_page is None or next_page <= start_page:
            next_page = start_page + 1
        chapter_pages = [
            page.strip()
            for page in extracted.pages[start_page:next_page]
            if page.strip()
        ]
        body = "\n\n".join(chapter_pages).strip()
        body = _strip_leading_title(body, entry.title)
        chapters.append(
            Chapter(
                chapter_id=f"{slugify(entry.title)}-{index}",
                chapter_index=index,
                title=entry.title,
                text=body,
            )
        )
    return chapters


def _find_title_occurrences(raw_text: str, titles: list[str]) -> list[tuple[str, int, int]]:
    occurrence_sets: list[list[tuple[int, int]]] = []
    for title in titles:
        pattern = re.compile(rf"(?im)^\s*{re.escape(title)}\s*$")
        matches = [(match.start(), match.end()) for match in pattern.finditer(raw_text)]
        if not matches:
            return []
        occurrence_sets.append(matches)

    selected: list[tuple[str, int, int]] = []
    upper_bound = len(raw_text) + 1
    for title, matches in zip(reversed(titles), reversed(occurrence_sets), strict=True):
        chosen = next(
            ((start, end) for start, end in reversed(matches) if start < upper_bound),
            None,
        )
        if chosen is None:
            return []
        start, end = chosen
        selected.append((title, start, end))
        upper_bound = start
    selected.reverse()
    return selected


def _strip_leading_title(body: str, title: str) -> str:
    if not body:
        return body
    pattern = re.compile(rf"(?im)^\s*{re.escape(title)}\s*$")
    match = pattern.match(body)
    if match:
        return body[match.end() :].strip()
    return body


def _split_by_headings(raw_text: str) -> list[Chapter]:
    matches = list(HEADING_PATTERN.finditer(raw_text))
    if not matches:
        return []
    chapters: list[Chapter] = []
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
        body = raw_text[start:next_start].strip()
        chapters.append(
            Chapter(
                chapter_id=f"{slugify(title)}-{index}",
                chapter_index=index,
                title=title,
                text=body,
            )
        )
    return chapters
