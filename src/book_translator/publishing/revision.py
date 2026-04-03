from __future__ import annotations

from book_translator.models import PublishingChapterArtifact


def revise_chapter(
    *,
    chapter_id: str,
    chapter_index: int,
    title: str,
    draft_text: str,
    style_name: str,
    glossary: dict[str, str],
    names: dict[str, str],
) -> PublishingChapterArtifact:
    revised_text = draft_text
    for mapping in (glossary, names):
        for source, translation in mapping.items():
            revised_text = revised_text.replace(source, translation)

    return PublishingChapterArtifact(
        chapter_id=chapter_id,
        chapter_index=chapter_index,
        title=title,
        text=revised_text,
    )
