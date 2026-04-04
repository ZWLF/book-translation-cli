from booksmith.chunking.splitter import split_chapter_into_chunks
from booksmith.models import Chapter


def test_split_chapter_into_chunks_preserves_order() -> None:
    chapter = Chapter(
        chapter_id="c1",
        chapter_index=0,
        title="Chapter 1",
        text=(
            "Paragraph one has four words.\n\n"
            "Paragraph two has four words.\n\n"
            "Paragraph three has four words."
        ),
    )

    chunks = split_chapter_into_chunks(chapter, max_words=10)

    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert chunks[0].chapter_title == "Chapter 1"
    assert "Paragraph one" in chunks[0].source_text
    assert "Paragraph three" in chunks[1].source_text


def test_splitter_breaks_oversized_paragraph_by_sentence() -> None:
    chapter = Chapter(
        chapter_id="c1",
        chapter_index=0,
        title="Chapter 1",
        text="One two three four five. Six seven eight nine ten. Eleven twelve.",
    )

    chunks = split_chapter_into_chunks(chapter, max_words=5)

    assert len(chunks) == 3
    assert chunks[0].source_text.endswith("five.")


def test_splitter_skips_empty_chapter_text() -> None:
    chapter = Chapter(
        chapter_id="c1",
        chapter_index=0,
        title="Chapter 1",
        text="   \n\n   ",
    )

    chunks = split_chapter_into_chunks(chapter, max_words=5)

    assert chunks == []
