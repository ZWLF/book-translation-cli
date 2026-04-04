from __future__ import annotations

import re

from booksmith.models import (
    PublishingAuditFinding,
    PublishingBlock,
    StructuredPublishingChapter,
)

_INLINE_NUMBERED_MARKER_RE = re.compile(r"(?<!\d)(\d{1,3})[.)]\s*")
_BLOCK_NUMBERED_LINE_RE = re.compile(r"^\s*(\d{1,3})[.)]\s+\S")


def apply_editorial_repairs(
    *,
    chapter_text: str,
    source_text: str,
    findings: list[PublishingAuditFinding],
) -> str:
    revised = chapter_text
    if _should_restore_numbered_list(findings):
        revised = _restore_numbered_list_blocks(chapter_text=revised, source_text=source_text)
    return normalize_editorial_spacing(revised)


def apply_structured_editorial_repairs(
    *,
    chapter: StructuredPublishingChapter,
    findings: list[PublishingAuditFinding],
) -> StructuredPublishingChapter:
    repaired_blocks = [
        _repair_structured_block(block, findings=findings)
        for block in chapter.blocks
    ]
    return chapter.model_copy(
        update={
            "blocks": [
                block for block in repaired_blocks if block.text.strip() or block.kind == "image"
            ]
        }
    )


def _repair_structured_block(
    block: PublishingBlock,
    *,
    findings: list[PublishingAuditFinding],
) -> PublishingBlock:
    if block.kind == "ordered_item":
        return block.model_copy(update={"text": normalize_editorial_spacing(block.text)})
    return block.model_copy(update={"text": normalize_editorial_spacing(block.text)})


def normalize_editorial_spacing(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", normalized)
    normalized = re.sub(r"[ \t]+([,.;:!?，。；：！？、）\]}>])", r"\1", normalized)
    normalized = re.sub(r"([（\[{<])[ \t]+", r"\1", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _should_restore_numbered_list(findings: list[PublishingAuditFinding]) -> bool:
    return any(
        finding.finding_type == "collapsed_numbered_list" and finding.auto_fixable
        for finding in findings
    )


def _restore_numbered_list_blocks(*, chapter_text: str, source_text: str) -> str:
    if _has_block_numbered_run(chapter_text, min_run=3):
        return chapter_text

    rebuilt = _rebuild_from_inline_markers(chapter_text)
    if rebuilt is not None:
        return rebuilt

    # Conservative fallback: if target text cannot be segmented safely, do not
    # synthesize translated content from source text.
    if _has_block_numbered_run(source_text, min_run=3):
        return chapter_text
    return chapter_text


def _rebuild_from_inline_markers(text: str) -> str | None:
    matches = list(_INLINE_NUMBERED_MARKER_RE.finditer(text))
    if len(matches) < 3:
        return None

    markers = [int(match.group(1)) for match in matches]
    if markers[:3] != [1, 2, 3]:
        return None

    prefix = text[: matches[0].start()].strip()
    items: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        item_text = text[match.end() : end].strip()
        if not item_text:
            continue
        item_text = re.sub(r"\s+", " ", item_text)
        items.append(f"{match.group(1)}. {item_text}")

    if len(items) < 3:
        return None
    if prefix:
        return f"{prefix}\n\n" + "\n".join(items)
    return "\n".join(items)


def _has_block_numbered_run(text: str, *, min_run: int) -> bool:
    markers: list[int] = []
    for line in text.splitlines():
        match = _BLOCK_NUMBERED_LINE_RE.match(line)
        if match is None:
            continue
        markers.append(int(match.group(1)))
    return _has_sequential_run(markers, min_run=min_run)


def _has_sequential_run(values: list[int], *, min_run: int) -> bool:
    if len(values) < min_run:
        return False

    run_length = 1
    for index in range(1, len(values)):
        if values[index] == values[index - 1] + 1:
            run_length += 1
        else:
            run_length = 1
        if run_length >= min_run:
            run_start = values[index - run_length + 1]
            if run_start == 1:
                return True
    return False
