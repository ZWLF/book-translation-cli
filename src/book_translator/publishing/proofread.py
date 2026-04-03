from __future__ import annotations

import re

from book_translator.models import PublishingChapterArtifact

PROOFREAD_STAGE_VERSION = "2026-04-03-deep-refinement-1"


def proofread_chapter(
    chapter: PublishingChapterArtifact,
) -> tuple[PublishingChapterArtifact, list[dict[str, str]]]:
    notes: list[dict[str, str]] = []
    revised_text = _normalize_publishing_text(chapter.text)

    if revised_text != chapter.text:
        notes.append(
            {
                "type": "spacing_normalization",
                "severity": "medium",
                "message": "Normalized mixed-script spacing and tightened punctuation.",
            }
        )
    else:
        notes.append(
            {
                "type": "proofread_review",
                "severity": "info",
                "message": "Completed chapter proofreading with no text changes required.",
            }
        )

    return chapter.model_copy(update={"text": revised_text}), notes


def _normalize_publishing_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", normalized)
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])\s*(?=[A-Za-z0-9])", " ", normalized)
    normalized = re.sub(r"(?<=[A-Za-z0-9])\s*(?=[\u4e00-\u9fff])", " ", normalized)
    normalized = re.sub(r"\s+([，。！？；：,.!?;:])", r"\1", normalized)
    normalized = re.sub(r"([，。！？；：])\s+", r"\1", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
