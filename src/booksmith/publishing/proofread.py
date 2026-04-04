from __future__ import annotations

import re

from booksmith.models import PublishingChapterArtifact

PROOFREAD_STAGE_VERSION = "2026-04-03-deep-refinement-2"


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
                "message": (
                    "Normalized mixed-script spacing, restored numbered "
                    "list structure, and tightened punctuation."
                ),
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
    normalized = _strip_translation_wrapper(normalized)
    normalized = _restore_inline_numbered_list_layout(normalized)
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", normalized)
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]*(?=[A-Za-z0-9])", " ", normalized)
    normalized = re.sub(r"(?<=[A-Za-z0-9])[ \t]*(?=[\u4e00-\u9fff])", " ", normalized)
    normalized = re.sub(r"[ \t]+([，。！？；：,.!?;:])", r"\1", normalized)
    normalized = re.sub(r"([，。！？；：])[ \t]+", r"\1", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _strip_translation_wrapper(text: str) -> str:
    return re.sub(
        r"^以下是《[^》]+》.*?简体中文翻译[:：]\s*",
        "",
        text,
        count=1,
    )


def _restore_inline_numbered_list_layout(text: str) -> str:
    if "\n1. " in text and "\n2. " in text:
        return text

    matches = list(re.finditer(r"(?<!\d)(\d{1,3})\.\s*", text))
    if len(matches) < 3:
        return text

    if [int(match.group(1)) for match in matches[:3]] != [1, 2, 3]:
        return text

    intro = text[: matches[0].start()].strip()
    items: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        item_text = text[match.end() : end].strip()
        if not item_text:
            continue
        item_text = re.sub(r"\s+", " ", item_text)
        items.append(f"{match.group(1)}. {item_text}")

    if len(items) < 3:
        return text

    if intro:
        return f"{intro}\n\n" + "\n".join(items)
    return "\n".join(items)
