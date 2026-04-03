from __future__ import annotations

from book_translator.models import Chapter, Chunk, PublishingChapterArtifact, TranslationResult


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
