from booksmith.chaptering.detect import detect_chapters
from booksmith.models import ExtractedBook, TocEntry


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


def test_detect_chapters_ignores_toc_page_occurrences() -> None:
    extracted = ExtractedBook(
        title="TOC Duplicate",
        raw_text=(
            "Contents\n"
            "Chapter 1\n"
            "Chapter 2\n\n"
            "Chapter 1\n"
            "Actual first body.\n\n"
            "Chapter 2\n"
            "Actual second body.\n"
        ),
        toc=[TocEntry(title="Chapter 1"), TocEntry(title="Chapter 2")],
    )

    chapters = detect_chapters(extracted, strategy="toc-first")

    assert [chapter.title for chapter in chapters] == ["Chapter 1", "Chapter 2"]
    assert chapters[0].text == "Actual first body."
    assert chapters[1].text == "Actual second body."


def test_detect_chapters_prefers_page_aware_pdf_toc() -> None:
    extracted = ExtractedBook(
        title="Page Aware",
        raw_text=(
            "Contents\n"
            "Notes on This Book\n"
            "Foreword\n"
            "Chapter 1\n\n"
            "Notes body.\n\n"
            "Foreword body.\n\n"
            "Chapter 1\n"
            "Actual second body.\n"
        ),
        toc=[
            TocEntry(title="Notes on This Book", page_index=1),
            TocEntry(title="Foreword", page_index=2),
            TocEntry(title="Chapter 1", page_index=3),
        ],
        pages=[
            "Contents\nNotes on This Book\nForeword\nChapter 1",
            "Notes body.",
            "Foreword body.",
            "Chapter 1\nActual second body.",
        ],
    )

    chapters = detect_chapters(extracted, strategy="toc-first")

    assert [chapter.title for chapter in chapters] == [
        "Notes on This Book",
        "Foreword",
        "Chapter 1",
    ]
    assert chapters[0].text == "Notes body."
    assert chapters[1].text == "Foreword body."
    assert chapters[2].text == "Actual second body."
