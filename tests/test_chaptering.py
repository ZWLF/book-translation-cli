from book_translator.chaptering.detect import detect_chapters
from book_translator.models import ExtractedBook, TocEntry


def test_detect_chapters_prefers_toc_titles() -> None:
    extracted = ExtractedBook(
        title="Sample Book",
        raw_text=(
            "Preface\n\n"
            "Chapter 1\n"
            "Alpha paragraph.\n\n"
            "Chapter 2\n"
            "Beta paragraph.\n"
        ),
        toc=[TocEntry(title="Chapter 1"), TocEntry(title="Chapter 2")],
    )

    chapters = detect_chapters(extracted, strategy="toc-first")

    assert [chapter.title for chapter in chapters] == ["Chapter 1", "Chapter 2"]
    assert "Alpha paragraph." in chapters[0].text
    assert "Beta paragraph." in chapters[1].text


def test_detect_chapters_falls_back_to_heading_rules() -> None:
    extracted = ExtractedBook(
        title="No TOC",
        raw_text=(
            "CHAPTER 1\n"
            "First body.\n\n"
            "CHAPTER 2\n"
            "Second body.\n"
        ),
        toc=[],
    )

    chapters = detect_chapters(extracted, strategy="toc-first")

    assert [chapter.title for chapter in chapters] == ["CHAPTER 1", "CHAPTER 2"]


def test_detect_chapters_uses_manual_toc_titles() -> None:
    extracted = ExtractedBook(
        title="Manual TOC",
        raw_text=(
            "Intro\n\n"
            "Part One\n"
            "First body.\n\n"
            "Part Two\n"
            "Second body.\n"
        ),
        toc=[],
    )

    chapters = detect_chapters(extracted, strategy="manual", manual_titles=["Part One", "Part Two"])

    assert [chapter.title for chapter in chapters] == ["Part One", "Part Two"]
