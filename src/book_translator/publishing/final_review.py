from __future__ import annotations

from book_translator.models import PublishingChapterArtifact
from book_translator.publishing.proofread import _normalize_publishing_text

FINAL_REVIEW_STAGE_VERSION = "2026-04-03-deep-refinement-1"


def apply_final_review(
    chapters: list[PublishingChapterArtifact],
) -> tuple[list[PublishingChapterArtifact], list[dict[str, str]]]:
    ordered = sorted(chapters, key=lambda item: item.chapter_index)
    reviewed: list[PublishingChapterArtifact] = []
    editorial_log: list[dict[str, str]] = []

    for chapter in ordered:
        normalized_text = _normalize_publishing_text(chapter.text)
        if normalized_text != chapter.text:
            editorial_log.append(
                {
                    "chapter_id": chapter.chapter_id,
                    "type": "whole_book_normalization",
                    "severity": "medium",
                    "message": "Applied final whole-book consistency normalization.",
                }
            )
        reviewed.append(chapter.model_copy(update={"text": normalized_text}))

    if not editorial_log:
        editorial_log.append(
            {
                "chapter_id": "*",
                "type": "whole_book_review",
                "severity": "info",
                "message": "Completed final whole-book review with no additional text changes.",
            }
        )

    return reviewed, editorial_log
