from __future__ import annotations

from book_translator.models import PublishingChapterArtifact
from book_translator.publishing.structure import build_structured_chapter


def test_structure_builder_splits_numbered_items_into_ordered_blocks() -> None:
    artifact = PublishingChapterArtifact(
        chapter_id="c1",
        chapter_index=1,
        title="Rules",
        text="1. 第一条\n2. 第二条\n3. 第三条",
    )

    chapter = build_structured_chapter(
        artifact=artifact,
        source_text="1. First\n2. Second\n3. Third",
        source_assets=[],
        source_title="Principles",
    )

    assert [block.kind for block in chapter.blocks][:3] == [
        "ordered_item",
        "ordered_item",
        "ordered_item",
    ]
    assert [block.text for block in chapter.blocks][:3] == [
        "第一条",
        "第二条",
        "第三条",
    ]
    assert [block.source_anchor for block in chapter.blocks][:3] == [
        "1. First",
        "2. Second",
        "3. Third",
    ]
    assert chapter.source_title == "Principles"
    assert chapter.translated_title == "Rules"


def test_structure_builder_preserves_source_anchor_order_when_numbering_restarts() -> None:
    chapter = build_structured_chapter(
        artifact=PublishingChapterArtifact(
            chapter_id="c1b",
            chapter_index=3,
            title="Restarted Lists",
            text="1. 第一组一\n2. 第一组二\n\n1. 第二组一\n2. 第二组二",
        ),
        source_text=(
            "1. First group one\n2. First group two\n\n"
            "1. Second group one\n2. Second group two"
        ),
        source_assets=[],
    )

    ordered_blocks = [block for block in chapter.blocks if block.kind == "ordered_item"]
    assert [block.source_anchor for block in ordered_blocks] == [
        "1. First group one",
        "2. First group two",
        "1. Second group one",
        "2. Second group two",
    ]


def test_structure_builder_splits_inline_numbered_items_into_ordered_blocks() -> None:
    chapter = build_structured_chapter(
        artifact=PublishingChapterArtifact(
            chapter_id="c1c",
            chapter_index=4,
            title="Inline Rules",
            text="1. 第一条 2. 第二条 3. 第三条",
        ),
        source_text="1. First\n2. Second\n3. Third",
        source_assets=[],
    )

    ordered_blocks = [block for block in chapter.blocks if block.kind == "ordered_item"]
    assert [block.text for block in ordered_blocks] == [
        "第一条",
        "第二条",
        "第三条",
    ]
    assert [block.source_anchor for block in ordered_blocks] == [
        "1. First",
        "2. Second",
        "3. Third",
    ]


def test_structure_builder_preserves_caption_only_asset_anchor() -> None:
    chapter = build_structured_chapter(
        artifact=PublishingChapterArtifact(
            chapter_id="c2",
            chapter_index=2,
            title="Images",
            text="[图] Falcon launch",
        ),
        source_text="Rocket image. Figure 1. Falcon launch.",
        source_assets=[
            {
                "source_asset_id": "img-1",
                "caption": "Falcon launch",
                "status": "caption-only",
            }
        ],
    )

    caption_block = next(block for block in chapter.blocks if block.kind == "caption")
    assert caption_block.text == "Falcon launch"
    assert chapter.assets[0].status == "caption-only"
    assert chapter.assets[0].block_anchor_id == caption_block.block_id
    assert chapter.source_title is None
    assert chapter.translated_title == "Images"
