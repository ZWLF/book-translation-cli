from __future__ import annotations

import re

from book_translator.models import (
    PublishingAsset,
    PublishingBlock,
    PublishingChapterArtifact,
    StructuredPublishingBook,
    StructuredPublishingChapter,
)

_NUMBERED_ITEM_RE = re.compile(r"^\s*(\d{1,3})[.)]\s*(.+?)\s*$")
_INLINE_NUMBERED_MARKER_RE = re.compile(r"(?<!\d)(\d{1,3})[.)]\s*")
_WHITESPACE_RE = re.compile(r"\s+")


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
    blocks = _build_blocks_from_text(
        chapter_id=artifact.chapter_id,
        translated_text=artifact.text,
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
        translated_title=artifact.title,
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
        numbered_items = _extract_numbered_items(paragraph)
        if numbered_items:
            for _, item_text in numbered_items:
                blocks.append(
                    PublishingBlock(
                        block_id=_block_id(chapter_id=chapter_id, order_index=block_index),
                        kind="ordered_item",
                        text=item_text,
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
