from __future__ import annotations

import re

from booksmith.models import (
    PublishingAsset,
    PublishingBlock,
    PublishingChapterArtifact,
    StructuredPublishingBook,
    StructuredPublishingChapter,
)

_NUMBERED_ITEM_RE = re.compile(r"^\s*(\d{1,3})[.)]\s*(.+?)\s*$")
_INLINE_NUMBERED_MARKER_RE = re.compile(r"(?<!\d)(\d{1,3})[.)]\s*")
_TAIL_REFERENCE_MARKER_RE = re.compile(r"(?<!\d)(\d{2,4})\s+(?=\S)")
_WHITESPACE_RE = re.compile(r"\s+")
_MARKDOWN_HEADING_RE = re.compile(r"^\s*(?:\*\*|__)(.+?)(?:\*\*|__)\s*$")
_MARKDOWN_SEPARATOR_RE = re.compile(r"^\s*\*{3,}\s*$")
_WRAPPER_LINE_PREFIXES = (
    "\u672c\u4e66\uff1a",
    "\u4e66\u7c4d\uff1a",
    "\u7ae0\u8282\uff1a",
    "\u5206\u5757\u7d22\u5f15\uff1a",
    "\u7d22\u5f15\uff1a",
    "\u539f\u6587\u7247\u6bb5\u7d22\u5f15\uff1a",
    "\u7ffb\u8bd1\u5982\u4e0b\uff1a",
)


def build_structured_book(
    *,
    title: str,
    chapters: list[StructuredPublishingChapter],
) -> StructuredPublishingBook:
    return StructuredPublishingBook(title=title, chapters=chapters)


def build_structured_chapter(
    *,
    artifact: PublishingChapterArtifact,
    source_text: str,
    source_assets: list[dict[str, object]],
    source_title: str | None = None,
) -> StructuredPublishingChapter:
    normalized_text, translated_title = _normalize_translated_chapter_text(
        translated_text=artifact.text,
        source_title=source_title,
        fallback_title=artifact.title,
    )
    blocks = _build_blocks_from_text(
        chapter_id=artifact.chapter_id,
        translated_text=normalized_text,
        source_text=source_text,
    )
    assets = _normalize_source_assets(source_assets)
    _attach_caption_blocks(
        chapter_id=artifact.chapter_id,
        blocks=blocks,
        assets=assets,
    )
    return StructuredPublishingChapter(
        chapter_id=artifact.chapter_id,
        chapter_index=artifact.chapter_index,
        source_title=source_title,
        translated_title=translated_title,
        blocks=blocks,
        assets=assets,
    )


def _build_blocks_from_text(
    *,
    chapter_id: str,
    translated_text: str,
    source_text: str,
) -> list[PublishingBlock]:
    numbered_source_anchors = _extract_numbered_source_anchors(source_text)
    blocks: list[PublishingBlock] = []
    block_index = 1
    numbered_anchor_index = 0

    for paragraph in _split_paragraphs(translated_text):
        paragraph = _strip_leading_wrapper_lines(paragraph)
        if not paragraph:
            continue
        if _MARKDOWN_SEPARATOR_RE.match(paragraph):
            continue

        heading_text, body_text = _extract_markdown_heading(paragraph)
        if heading_text:
            blocks.append(
                PublishingBlock(
                    block_id=_block_id(chapter_id=chapter_id, order_index=block_index),
                    kind="heading",
                    text=heading_text,
                    order_index=block_index,
                )
            )
            block_index += 1
            paragraph = body_text
            if not paragraph:
                continue

        numbered_items = _extract_numbered_items(paragraph)
        if numbered_items:
            for _, item_text in numbered_items:
                primary_text, overflow_blocks = _split_numbered_item_overflow(item_text)
                blocks.append(
                    PublishingBlock(
                        block_id=_block_id(chapter_id=chapter_id, order_index=block_index),
                        kind="ordered_item",
                        text=primary_text,
                        order_index=block_index,
                        source_anchor=(
                            numbered_source_anchors[numbered_anchor_index]
                            if numbered_anchor_index < len(numbered_source_anchors)
                            else None
                        ),
                    )
                )
                block_index += 1
                numbered_anchor_index += 1
                for overflow_kind, overflow_text in overflow_blocks:
                    blocks.append(
                        PublishingBlock(
                            block_id=_block_id(chapter_id=chapter_id, order_index=block_index),
                            kind=overflow_kind,
                            text=overflow_text,
                            order_index=block_index,
                        )
                    )
                    block_index += 1
            continue

        paragraph = _normalize_paragraph_text(paragraph)
        if not paragraph:
            continue
        blocks.append(
            PublishingBlock(
                block_id=_block_id(chapter_id=chapter_id, order_index=block_index),
                kind="paragraph",
                text=paragraph,
                order_index=block_index,
            )
        )
        block_index += 1

    return blocks


def _split_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n+", normalized)
        if paragraph.strip()
    ]


def _normalize_translated_chapter_text(
    *,
    translated_text: str,
    source_title: str | None,
    fallback_title: str,
) -> tuple[str, str]:
    normalized = translated_text.replace("\r\n", "\n").strip()
    normalized = _strip_compact_translation_wrapper(normalized)
    paragraphs = [
        cleaned
        for paragraph in _split_paragraphs(normalized)
        if (cleaned := _strip_leading_wrapper_lines(paragraph))
    ]
    resolved_title = fallback_title
    if paragraphs:
        extracted_title, remaining_paragraph = _extract_translated_title(paragraphs[0])
        has_following_body = bool(remaining_paragraph) or len(paragraphs) > 1
        if (
            extracted_title
            and has_following_body
            and source_title
            and _looks_like_english_heading(source_title)
        ):
            resolved_title = extracted_title
            if remaining_paragraph:
                paragraphs[0] = remaining_paragraph
            else:
                paragraphs = paragraphs[1:]
    return "\n\n".join(paragraphs).strip(), resolved_title


def _strip_compact_translation_wrapper(text: str) -> str:
    return re.sub(
        r"^(?:(?:\u672c\u4e66\uff1a|\u4e66\u7c4d\uff1a)[^\n]*[\s\u3000]*)?"
        r"(?:(?:\u7ae0\u8282\uff1a)[^\n]*[\s\u3000]*)?"
        r"(?:(?:\u5206\u5757\u7d22\u5f15\uff1a|\u7d22\u5f15\uff1a|\u539f\u6587\u7247\u6bb5\u7d22\u5f15\uff1a)\d+[\s\u3000]*)*"
        r"(?:\u7ffb\u8bd1\u5982\u4e0b\uff1a[\s\u3000]*)?",
        "",
        text,
        count=1,
    ).strip()


def _strip_leading_wrapper_lines(paragraph: str) -> str:
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    while lines and lines[0].startswith(_WRAPPER_LINE_PREFIXES):
        lines.pop(0)
    return "\n".join(lines).strip()


def _extract_translated_title(paragraph: str) -> tuple[str | None, str]:
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if not lines:
        return None, ""
    first_line = _strip_markdown_markers(lines[0])
    if not _looks_like_translated_title_candidate(first_line):
        return None, paragraph.strip()
    remaining = "\n".join(lines[1:]).strip()
    return first_line, remaining


def _extract_markdown_heading(paragraph: str) -> tuple[str | None, str]:
    lines = [line.rstrip() for line in paragraph.splitlines() if line.strip()]
    if not lines:
        return None, ""
    match = _MARKDOWN_HEADING_RE.match(lines[0].strip())
    if match is None:
        return None, paragraph
    heading = _strip_markdown_markers(match.group(1))
    body = "\n".join(line.strip() for line in lines[1:] if line.strip()).strip()
    return heading, body


def _normalize_paragraph_text(paragraph: str) -> str:
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if not lines:
        return ""
    merged = _merge_orphan_numeric_lines(lines)
    return "\n".join(merged).strip()


def _merge_orphan_numeric_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    pending_numbers: list[str] = []
    for line in lines:
        if line.isdigit():
            pending_numbers.append(line)
            continue
        if pending_numbers:
            combined_numbers = " ".join(pending_numbers)
            if merged:
                merged[-1] = f"{merged[-1]} {combined_numbers}".strip()
            else:
                line = f"{combined_numbers} {line}".strip()
            pending_numbers = []
        merged.append(line)
    if pending_numbers:
        combined_numbers = " ".join(pending_numbers)
        if merged:
            merged[-1] = f"{merged[-1]} {combined_numbers}".strip()
        else:
            merged.append(combined_numbers)
    return merged


def _strip_markdown_markers(text: str) -> str:
    return text.strip().strip("*_").strip()


def _looks_like_translated_title_candidate(text: str) -> bool:
    candidate = text.strip()
    if not candidate:
        return False
    if _NUMBERED_ITEM_RE.match(candidate):
        return False
    if candidate.startswith("[") or candidate.startswith("【"):
        return False
    if len(candidate) > 40:
        return False
    if re.search(r"[。！？；!?]$", candidate):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", candidate))


def _looks_like_english_heading(text: str) -> bool:
    candidate = text.strip()
    return bool(re.search(r"[A-Za-z]", candidate)) and not bool(
        re.search(r"[\u4e00-\u9fff]", candidate)
    )


def _extract_numbered_items(paragraph: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if not lines:
        return []

    items: list[tuple[str, str]] = []
    for line in lines:
        match = _NUMBERED_ITEM_RE.match(line)
        if match is None:
            return _extract_inline_numbered_items(paragraph)
        if len(list(_INLINE_NUMBERED_MARKER_RE.finditer(line))) > 1:
            return _extract_inline_numbered_items(paragraph)
        items.append((match.group(1), match.group(2).strip()))
    return items


def _extract_inline_numbered_items(paragraph: str) -> list[tuple[str, str]]:
    compact = re.sub(r"\s+", " ", paragraph).strip()
    matches = list(_INLINE_NUMBERED_MARKER_RE.finditer(compact))
    if len(matches) < 3:
        return []

    markers = [int(match.group(1)) for match in matches]
    if markers[:3] != [1, 2, 3]:
        return []

    items: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(compact)
        item_text = compact[match.end() : end].strip()
        if not item_text:
            continue
        items.append((match.group(1), item_text))
    return items if len(items) >= 3 else []


def _split_numbered_item_overflow(item_text: str) -> tuple[str, list[tuple[str, str]]]:
    compact = re.sub(r"\s+", " ", item_text).strip()
    if not compact:
        return "", []

    matches = list(_TAIL_REFERENCE_MARKER_RE.finditer(compact))
    run_start = _find_tail_marker_run_start(compact, matches)
    if run_start is None:
        return compact, []

    first_marker = matches[run_start]
    primary_text = compact[: first_marker.start()].rstrip()
    if not primary_text:
        return compact, []

    overflow_blocks: list[tuple[str, str]] = []
    for index in range(run_start, len(matches)):
        start = matches[index].start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(compact)
        segment = compact[start:end].strip()
        if not segment:
            continue
        kind = "reference_entry" if _looks_like_reference_entry(segment) else "paragraph"
        overflow_blocks.append((kind, segment))
    return primary_text, overflow_blocks


def _find_tail_marker_run_start(text: str, matches: list[re.Match[str]]) -> int | None:
    if len(matches) < 2:
        return None

    values = [int(match.group(1)) for match in matches]
    for index in range(len(values) - 1):
        if values[index + 1] != values[index] + 1:
            continue
        prefix = text[: matches[index].start()].rstrip()
        if not prefix or prefix[-1] not in ".!?)]}\"'。！？）":
            continue
        return index
    return None


def _looks_like_reference_entry(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    if not re.match(r"^\d{2,4}\s+\S", compact):
        return False
    if re.search(r"https?://|www\.", compact, re.I):
        return True
    if re.search(r'["“”]', compact):
        return True
    return bool(
        re.search(
            r"\b(?:podcast|summit|conference|speech|interview|blog|transcript|episode|plan)\b",
            compact,
            re.I,
        )
    )


def _extract_numbered_source_anchors(source_text: str) -> list[str]:
    anchors: list[str] = []
    for line in source_text.splitlines():
        match = _NUMBERED_ITEM_RE.match(line.strip())
        if match is None:
            continue
        anchors.append(line.strip())
    return anchors


def _normalize_source_assets(source_assets: list[dict[str, object]]) -> list[PublishingAsset]:
    assets: list[PublishingAsset] = []
    for raw_asset in source_assets:
        if isinstance(raw_asset, PublishingAsset):
            assets.append(raw_asset.model_copy(deep=True))
            continue
        assets.append(PublishingAsset.model_validate(raw_asset))
    return assets


def _attach_caption_blocks(
    *,
    chapter_id: str,
    blocks: list[PublishingBlock],
    assets: list[PublishingAsset],
) -> None:
    for asset in assets:
        if not asset.caption:
            continue

        caption_block = _find_matching_caption_block(blocks=blocks, caption=asset.caption)
        if caption_block is None:
            caption_block = PublishingBlock(
                block_id=_block_id(chapter_id=chapter_id, order_index=len(blocks) + 1),
                kind="caption",
                text=asset.caption.strip(),
                order_index=len(blocks) + 1,
                source_anchor=asset.source_location_hint or asset.caption.strip(),
            )
            blocks.append(caption_block)
        else:
            caption_block.kind = "caption"
            caption_block.text = _canonicalize_caption_text(
                block_text=caption_block.text,
                caption=asset.caption,
            )
            if caption_block.source_anchor is None:
                caption_block.source_anchor = asset.source_location_hint or asset.caption.strip()

        asset.block_anchor_id = caption_block.block_id


def _find_matching_caption_block(
    *,
    blocks: list[PublishingBlock],
    caption: str,
) -> PublishingBlock | None:
    caption_key = _normalize_caption_key(caption)
    for block in blocks:
        if _normalize_caption_key(block.text) == caption_key:
            return block
    return None


def _canonicalize_caption_text(*, block_text: str, caption: str) -> str:
    cleaned = _strip_caption_prefix(block_text)
    if _normalize_caption_key(cleaned) == _normalize_caption_key(caption):
        return caption.strip()
    return cleaned or caption.strip()


def _strip_caption_prefix(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\[[^\]]+\]\s*", "", cleaned)
    cleaned = re.sub(r"^(?:figure|fig\.?|image)\s*\d+[:.\-]?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^图\s*\d*[:：.\-]?\s*", "", cleaned)
    return cleaned.strip()


def _normalize_caption_key(text: str) -> str:
    cleaned = _strip_caption_prefix(text)
    cleaned = _WHITESPACE_RE.sub("", cleaned).lower()
    return re.sub(r"[^\w\u4e00-\u9fff]", "", cleaned)


def _block_id(*, chapter_id: str, order_index: int) -> str:
    return f"{chapter_id}-block-{order_index}"


__all__ = ["build_structured_book", "build_structured_chapter"]
