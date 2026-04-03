from book_translator.models import PublishingChapterArtifact
from book_translator.publishing.final_review import apply_final_review
from book_translator.publishing.proofread import proofread_chapter
from book_translator.publishing.revision import revise_chapter


def test_revise_chapter_returns_artifact_and_applies_lexicon() -> None:
    result = revise_chapter(
        chapter_id="c1",
        chapter_index=0,
        title="Chapter 1",
        draft_text="Mars and Musk built Tesla on Mars.",
        style_name="non-fiction-publishing",
        glossary={"Mars": "火星"},
        names={"Musk": "马斯克", "Tesla": "特斯拉"},
    )

    assert isinstance(result, PublishingChapterArtifact)
    assert result.chapter_id == "c1"
    assert result.chapter_index == 0
    assert result.title == "Chapter 1"
    assert "火星" in result.text
    assert "马斯克" in result.text
    assert "特斯拉" in result.text


def test_proofread_chapter_returns_notes_and_artifact() -> None:
    revised = PublishingChapterArtifact(
        chapter_id="c1",
        chapter_index=0,
        title="Chapter 1",
        text="Revised text",
    )

    final_artifact, notes = proofread_chapter(revised)

    assert isinstance(final_artifact, PublishingChapterArtifact)
    assert final_artifact.text == "Revised text"
    assert isinstance(notes, list)


def test_apply_final_review_sorts_chapters_and_returns_editorial_log() -> None:
    artifacts = [
        PublishingChapterArtifact(chapter_id="c2", chapter_index=1, title="B", text="Two"),
        PublishingChapterArtifact(chapter_id="c1", chapter_index=0, title="A", text="One"),
    ]

    reviewed, editorial_log = apply_final_review(artifacts)

    assert [item.chapter_id for item in reviewed] == ["c1", "c2"]
    assert isinstance(editorial_log, list)
