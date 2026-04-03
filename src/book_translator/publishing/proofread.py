from __future__ import annotations

from book_translator.models import PublishingChapterArtifact


def proofread_chapter(
    chapter: PublishingChapterArtifact,
) -> tuple[PublishingChapterArtifact, list[dict[str, str]]]:
    notes: list[dict[str, str]] = []
    return chapter, notes
