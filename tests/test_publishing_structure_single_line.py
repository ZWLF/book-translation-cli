from __future__ import annotations

from booksmith.models import PublishingChapterArtifact
from booksmith.publishing.structure import build_structured_chapter


def test_structure_builder_keeps_single_line_body_as_paragraph() -> None:
    chapter = build_structured_chapter(
        artifact=PublishingChapterArtifact(
            chapter_id="single-line",
            chapter_index=3,
            title="Chapter 1",
            text="璇戞枃::Hello world.",
        ),
        source_text="Hello world.",
        source_assets=[],
        source_title="Chapter 1",
    )

    assert chapter.translated_title == "Chapter 1"
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert chapter.blocks[0].text == "璇戞枃::Hello world."
