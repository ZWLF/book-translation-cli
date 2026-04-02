from pathlib import Path

from pypdf import PdfReader

from book_translator.models import Chunk, Manifest, TranslationResult
from book_translator.output.polished_pdf import (
    PrintableBlock,
    PrintableBook,
    PrintableChapter,
    build_printable_book,
    render_polished_pdf,
    running_header_texts,
)


def _chunk(
    *,
    chunk_id: str,
    chapter_id: str,
    chapter_index: int,
    chunk_index: int,
    title: str,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        chapter_id=chapter_id,
        chapter_index=chapter_index,
        chunk_index=chunk_index,
        chapter_title=title,
        source_text="source",
        source_token_estimate=1,
    )


def _translation(chunk_id: str, text: str) -> TranslationResult:
    return TranslationResult(
        chunk_id=chunk_id,
        translated_text=text,
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        attempt_count=1,
        latency_ms=10,
        input_tokens=1,
        output_tokens=1,
        estimated_cost_usd=0.0,
    )


def _manifest() -> Manifest:
    return Manifest(
        book_id="sample-book",
        source_path=r"H:\books\Sample Book (Author Name).pdf",
        source_fingerprint="fingerprint",
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        config_fingerprint="config",
    )


def test_build_printable_book_normalizes_wrapped_lines_and_headings() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        ),
        _chunk(
            chunk_id="chapter-2-0",
            chapter_id="chapter-2",
            chapter_index=1,
            chunk_index=0,
            title="Chapter Two",
        ),
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "《示例图书》",
                    "",
                    "### 第一章：中文标题",
                    "",
                    "这是第一行",
                    "继续一段。",
                    "",
                    "42",
                    "",
                    "小节标题",
                    "",
                    "这里有正文。",
                ]
            ),
        ),
        "chapter-2-0": _translation("chapter-2-0", "   "),
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.123456},
        chunks=chunks,
        translations=translations,
    )

    assert book.title_en == "Sample Book"
    assert book.title_zh == "《示例图书》"
    assert book.author == "Author Name"
    assert len(book.chapters) == 1

    chapter = book.chapters[0]
    assert chapter.source_title == "Chapter One"
    assert chapter.display_title == "第一章：中文标题"
    assert [block.kind for block in chapter.blocks] == ["paragraph", "section_heading", "paragraph"]
    assert chapter.blocks[0].text == "这是第一行继续一段。"
    assert chapter.blocks[1].text == "小节标题"
    assert chapter.blocks[2].text == "这里有正文。"


def test_build_printable_book_converts_reference_entries_and_strips_markdown() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "以下是该文本的简体中文翻译：",
                    "",
                    "35",
                    "“第一条参考资料”。",
                    "36",
                    "“第二条参考资料”。",
                    "",
                    "***",
                    "",
                    "**反馈重于感受**",
                    "",
                    "这是正文第一行",
                    "这是正文第二行。",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == [
        "reference",
        "reference",
        "section_heading",
        "paragraph",
    ]
    assert chapter.blocks[0].text == "35 “第一条参考资料”。"
    assert chapter.blocks[1].text == "36 “第二条参考资料”。"
    assert chapter.blocks[2].text == "反馈重于感受"
    assert chapter.blocks[3].text == "这是正文第一行这是正文第二行。"


def test_running_header_texts_avoids_left_right_overlap() -> None:
    left_even, right_even = running_header_texts(
        page_number=120,
        book_title="The Book of Elon A Guide to Purpose and Success",
        chapter_title="第一章：成为多行星物种是一场进化层级的事件",
    )
    left_odd, right_odd = running_header_texts(
        page_number=121,
        book_title="The Book of Elon A Guide to Purpose and Success",
        chapter_title="第一章：成为多行星物种是一场进化层级的事件",
    )

    assert left_even == "The Book of Elon"
    assert right_even == ""
    assert left_odd == ""
    assert right_odd == "第一章：成为多行星物种是一场进化层级的事件"


def test_render_polished_pdf_writes_pdf_file(tmp_path: Path) -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "《示例图书》",
                    "",
                    "### 第一章：中文标题",
                    "",
                    "这里是排版后的正文。",
                ]
            ),
        )
    }
    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    output_path = tmp_path / "translated.pdf"
    render_polished_pdf(book, output_path)

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF")
    assert output_path.stat().st_size > 0


def test_render_polished_pdf_hides_running_headers_on_toc_pages(tmp_path: Path) -> None:
    chapters = [
        PrintableChapter(
            chapter_id=f"chapter-{index}",
            chapter_index=index,
            source_title=f"Chapter {index}",
            display_title=f"Chapter {index}",
            blocks=[PrintableBlock(kind="paragraph", text="Body text for testing.")],
        )
        for index in range(1, 80)
    ]
    book = PrintableBook(
        book_id="sample-book",
        title_en="Sample Book",
        title_zh="示例图书",
        author="Author Name",
        source_path=r"H:\books\Sample Book (Author Name).pdf",
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        estimated_cost_usd=0.0,
        chapters=chapters,
    )

    output_path = tmp_path / "toc.pdf"
    render_polished_pdf(book, output_path)

    reader = PdfReader(str(output_path))
    toc_page_text = " ".join((reader.pages[3].extract_text() or "").split())

    assert "Chapter 13" in toc_page_text
    assert not toc_page_text.startswith("Sample Book 4")
