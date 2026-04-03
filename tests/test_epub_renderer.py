from __future__ import annotations

import base64
import zipfile
from pathlib import Path

from book_translator.models import (
    PublishingAsset,
    PublishingBlock,
    StructuredPublishingBook,
    StructuredPublishingChapter,
)
from book_translator.output.epub_renderer import render_structured_epub

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0ioAAAAASUVORK5CYII="
)


def test_render_structured_epub_preserves_lists_callouts_and_image_fallbacks(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "rocket.png"
    image_path.write_bytes(_PNG_1X1)
    output_path = tmp_path / "translated.epub"

    book = StructuredPublishingBook(
        title="Publishing EPUB",
        chapters=[
            StructuredPublishingChapter(
                chapter_id="chapter-1",
                chapter_index=0,
                source_title="Chapter 1",
                translated_title="第一章：开始",
                blocks=[
                    PublishingBlock(
                        block_id="chapter-1-block-1",
                        kind="paragraph",
                        text="Opening paragraph.",
                        order_index=1,
                    ),
                    PublishingBlock(
                        block_id="chapter-1-block-2",
                        kind="ordered_item",
                        text="第一条原则。",
                        order_index=2,
                        source_anchor="1. First principle.",
                    ),
                    PublishingBlock(
                        block_id="chapter-1-block-3",
                        kind="ordered_item",
                        text="第二条原则。",
                        order_index=3,
                        source_anchor="2. Second principle.",
                    ),
                    PublishingBlock(
                        block_id="chapter-1-block-4",
                        kind="callout",
                        text="Life is too short for long-term grudges.",
                        order_index=4,
                    ),
                    PublishingBlock(
                        block_id="chapter-1-block-5",
                        kind="image",
                        text="Falcon launch",
                        order_index=5,
                    ),
                ],
                assets=[
                    PublishingAsset(
                        source_asset_id="asset-1",
                        extracted_path=str(image_path),
                        caption="Falcon launch",
                        block_anchor_id="chapter-1-block-5",
                        status="extracted",
                    )
                ],
            ),
            StructuredPublishingChapter(
                chapter_id="chapter-2",
                chapter_index=1,
                source_title="Chapter 2",
                translated_title="第二章：收尾",
                blocks=[
                    PublishingBlock(
                        block_id="chapter-2-block-1",
                        kind="caption",
                        text="Missing launch",
                        order_index=1,
                    ),
                ],
                assets=[
                    PublishingAsset(
                        source_asset_id="asset-2",
                        caption="Missing launch",
                        block_anchor_id="chapter-2-block-1",
                        status="caption-only",
                    )
                ],
            ),
        ],
    )

    render_structured_epub(
        book,
        output_path,
        book_title="Publishing EPUB",
        author="ZWLF",
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    with zipfile.ZipFile(output_path) as archive:
        names = archive.namelist()
        assert any(name.endswith("nav.xhtml") for name in names)
        assert any(name.endswith("chapter-001.xhtml") for name in names)
        assert any(name.endswith("chapter-002.xhtml") for name in names)
        assert any("images/" in name and name.endswith(".png") for name in names)

        xhtml_docs = {
            name: archive.read(name).decode("utf-8")
            for name in names
            if name.endswith(".xhtml")
        }

    chapter_one = xhtml_docs[
        next(name for name in xhtml_docs if name.endswith("chapter-001.xhtml"))
    ]
    chapter_two = xhtml_docs[
        next(name for name in xhtml_docs if name.endswith("chapter-002.xhtml"))
    ]
    nav_doc = xhtml_docs[next(name for name in xhtml_docs if name.endswith("nav.xhtml"))]

    assert "第一章：开始 / Chapter 1" in nav_doc
    assert "第二章：收尾 / Chapter 2" in nav_doc
    assert "<ol class=\"ordered-list\">" in chapter_one
    assert "<aside class=\"callout\">" in chapter_one
    assert "<img src=\"images/chapter-1-asset-1.png\"" in chapter_one
    assert "<figcaption>Missing launch</figcaption>" in chapter_two
