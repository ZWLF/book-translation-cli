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
    matches: list[tuple[str, int, int]] = []
    search_start = 0
    for title in titles:
        pattern = re.compile(rf"(?im)^\s*{re.escape(title)}\s*$")
        match = pattern.search(raw_text, search_start)
        if not match:
            return []
        matches.append((title, match.start(), match.end()))
        search_start = match.end()

    chapters: list[Chapter] = []
    for index, (title, _start, end) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(raw_text)
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
