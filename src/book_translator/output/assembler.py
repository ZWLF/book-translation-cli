from __future__ import annotations

import re

from book_translator.models import (
    Chapter,
    Chunk,
    PublishingBlock,
    PublishingChapterArtifact,
    StructuredPublishingBook,
    StructuredPublishingChapter,
    TranslationResult,
)


def assemble_output_text(
    chapters: list[Chapter],
    chunks: list[Chunk],
    translations: dict[str, TranslationResult],
    failed_chunk_ids: set[str],
) -> str:
    chunks_by_chapter: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        chunks_by_chapter.setdefault(chunk.chapter_id, []).append(chunk)

    parts: list[str] = []
    for chapter in chapters:
        chapter_chunks = sorted(
            chunks_by_chapter.get(chapter.chapter_id, []), key=lambda item: item.chunk_index
        )
        if not chapter_chunks:
            continue
        parts.append(chapter.title)
        for chunk in chapter_chunks:
            if chunk.chunk_id in translations:
                parts.append(translations[chunk.chunk_id].translated_text)
            elif chunk.chunk_id in failed_chunk_ids:
                parts.append(f"[[翻译失败: {chapter.title} / chunk {chunk.chunk_index}]]")
        parts.append("")
    return "\n\n".join(part.strip() for part in parts if part is not None).strip() + "\n"


def assemble_structured_chapter_text(chapter: StructuredPublishingChapter) -> str:
    parts: list[str] = []
    for block in sorted(chapter.blocks, key=lambda item: item.order_index):
        rendered = _render_structured_block(block)
        if rendered:
            parts.append(rendered)
    return "\n\n".join(parts).strip()


def assemble_structured_publishing_output_text(
    chapters: list[StructuredPublishingChapter] | StructuredPublishingBook,
) -> str:
    if isinstance(chapters, StructuredPublishingBook):
        structured_chapters = chapters.chapters
    else:
        structured_chapters = chapters

    parts: list[str] = []
    for chapter in sorted(structured_chapters, key=lambda item: item.chapter_index):
        title = chapter.translated_title.strip() or (chapter.source_title or "").strip()
        if title:
            parts.append(title)
        body = assemble_structured_chapter_text(chapter)
        if body.strip():
            parts.append(body.strip())
        parts.append("")
    return "\n\n".join(part for part in parts if part).strip() + "\n"


def _render_structured_block(block: PublishingBlock) -> str:
    if block.kind == "ordered_item":
        if block.source_anchor:
            marker = _extract_ordered_marker(block.source_anchor)
            stripped = block.text.strip()
            if marker and stripped:
                return f"{marker} {stripped}"
        stripped = block.text.strip()
        return f"{block.order_index}. {stripped}" if stripped else ""
    if block.kind in {
        "heading",
        "qa_question",
        "qa_answer",
        "callout",
        "quote",
        "reference_entry",
        "caption",
        "paragraph",
        "unordered_item",
        "image",
    }:
        return block.text.strip()
    return block.text.strip()


def _extract_ordered_marker(source_anchor: str) -> str:
    match = re.match(r"^\s*(\d{1,3}[.)])\s+\S", source_anchor)
    if match is None:
        return ""
    return match.group(1)


def assemble_publishing_output_text(
    chapters: list[PublishingChapterArtifact],
    *,
    deep_review_chapters: list[PublishingChapterArtifact] | None = None,
) -> str:
    chapters_to_assemble = deep_review_chapters or chapters
    parts: list[str] = []
    for chapter in sorted(chapters_to_assemble, key=lambda item: item.chapter_index):
        parts.append(chapter.title)
        parts.append(chapter.text.strip())
        parts.append("")
    return "\n\n".join(part for part in parts if part).strip() + "\n"
