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
    rendered_blocks = [
        (block, _render_structured_block(block))
        for block in sorted(chapter.blocks, key=lambda item: item.order_index)
    ]
    rendered_blocks = [
        (block, rendered) for block, rendered in rendered_blocks if rendered
    ]
    if not rendered_blocks:
        return ""

    parts: list[str] = [rendered_blocks[0][1]]
    for index in range(1, len(rendered_blocks)):
        previous_block, _ = rendered_blocks[index - 1]
        current_block, current_text = rendered_blocks[index]
        separator = "\n" if _should_tightly_join(previous_block, current_block) else "\n\n"
        parts.append(separator)
        parts.append(current_text)
    return "".join(parts).strip()


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


def _should_tightly_join(previous: PublishingBlock, current: PublishingBlock) -> bool:
    list_kinds = {"ordered_item", "unordered_item"}
    if previous.kind in list_kinds and current.kind in list_kinds:
        return True
    if previous.kind == "qa_question" and current.kind == "qa_answer":
        return True
    return False


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
