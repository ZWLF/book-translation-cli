from __future__ import annotations

import re
from collections.abc import Iterable

from booksmith.models import Chapter, Chunk
from booksmith.utils import estimate_tokens, slugify, word_count

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def split_chapter_into_chunks(chapter: Chapter, max_words: int = 3000) -> list[Chunk]:
    if not chapter.text.strip():
        return []

    parts = _paragraph_aware_units(chapter.text, max_words=max_words)
    chunks: list[Chunk] = []
    current: list[str] = []
    current_words = 0
    chunk_index = 0

    for part in parts:
        part_words = word_count(part)
        if current and current_words + part_words > max_words:
            chunks.append(_make_chunk(chapter, chunk_index, "\n\n".join(current)))
            chunk_index += 1
            current = []
            current_words = 0
        current.append(part)
        current_words += part_words

    if current:
        chunks.append(_make_chunk(chapter, chunk_index, "\n\n".join(current)))

    return chunks


def _paragraph_aware_units(text: str, max_words: int) -> list[str]:
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]
    units: list[str] = []
    for paragraph in paragraphs:
        if word_count(paragraph) <= max_words:
            units.append(paragraph)
            continue
        units.extend(_split_long_paragraph(paragraph, max_words))
    return units or [text.strip()]


def _split_long_paragraph(paragraph: str, max_words: int) -> list[str]:
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_SPLIT_PATTERN.split(paragraph)
        if sentence.strip()
    ]
    units: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        sentence_words = word_count(sentence)
        if sentence_words > max_words:
            if current:
                units.append(" ".join(current))
                current = []
                current_words = 0
            units.extend(_split_by_word_budget(sentence.split(), max_words))
            continue
        if current and current_words + sentence_words > max_words:
            units.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words
    if current:
        units.append(" ".join(current))
    return units


def _split_by_word_budget(words: list[str], max_words: int) -> Iterable[str]:
    for start in range(0, len(words), max_words):
        yield " ".join(words[start : start + max_words])


def _make_chunk(chapter: Chapter, chunk_index: int, text: str) -> Chunk:
    return Chunk(
        chunk_id=f"{chapter.chapter_id}-{slugify(chapter.title)}-{chunk_index}",
        chapter_id=chapter.chapter_id,
        chapter_index=chapter.chapter_index,
        chunk_index=chunk_index,
        chapter_title=chapter.title,
        source_text=text.strip(),
        source_token_estimate=estimate_tokens(text),
    )
