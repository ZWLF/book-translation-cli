from pathlib import Path

from book_translator.models import Chunk, Manifest, TranslationResult
from book_translator.output.polished_pdf import build_printable_book, render_polished_pdf


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
