from __future__ import annotations

from book_translator.models import PublishingChapterArtifact


def apply_final_review(
    chapters: list[PublishingChapterArtifact],
) -> tuple[list[PublishingChapterArtifact], list[dict[str, str]]]:
    ordered = sorted(chapters, key=lambda item: item.chapter_index)
    editorial_log: list[dict[str, str]] = []
    return ordered, editorial_log
