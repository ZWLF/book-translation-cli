from booksmith.models import PublishingBlock, StructuredPublishingChapter
from booksmith.output.assembler import assemble_structured_chapter_text


def test_assemble_structured_chapter_text_numbers_ordered_items_locally() -> None:
    chapter = StructuredPublishingChapter(
        chapter_id="chapter-1",
        chapter_index=0,
        translated_title="章节",
        blocks=[
            PublishingBlock(
                block_id="chapter-1-block-1",
                kind="paragraph",
                text="本书分为四个部分：",
                order_index=19,
            ),
            PublishingBlock(
                block_id="chapter-1-block-2",
                kind="ordered_item",
                text="第一部分",
                order_index=20,
            ),
            PublishingBlock(
                block_id="chapter-1-block-3",
                kind="ordered_item",
                text="第二部分",
                order_index=21,
            ),
        ],
    )

    text = assemble_structured_chapter_text(chapter)

    assert "1. 第一部分" in text
    assert "2. 第二部分" in text
    assert "20. 第一部分" not in text
