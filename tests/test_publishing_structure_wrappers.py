from __future__ import annotations

from booksmith.models import PublishingChapterArtifact
from booksmith.publishing.structure import build_structured_chapter


def test_structure_builder_strips_actual_chinese_wrapper_lines() -> None:
    chapter = build_structured_chapter(
        artifact=PublishingChapterArtifact(
            chapter_id="wrapper",
            chapter_index=0,
            title="Seek the Nature of the Universe",
            text=(
                "本书：《示例图书》\n"
                "章节：探寻宇宙本质\n"
                "原文片段索引：0\n"
                "翻译如下：\n"
                "探寻宇宙本质\n\n"
                "我们要扩展意识。"
            ),
        ),
        source_text="Seek the Nature of the Universe\nExpand consciousness.",
        source_assets=[],
        source_title="Seek the Nature of the Universe",
    )

    assert chapter.translated_title == "探寻宇宙本质"
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert chapter.blocks[0].text == "我们要扩展意识。"
