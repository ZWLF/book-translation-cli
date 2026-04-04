from pathlib import Path

import pytest
from ebooklib import epub
from typer.testing import CliRunner

from booksmith.cli import app
from booksmith.config import RunConfig
from booksmith.pipeline import process_book
from booksmith.providers.base import BaseProvider


class FakeProvider(BaseProvider):
    async def translate(self, request):  # type: ignore[override]
        return self.make_result(
            chunk_id=request.chunk_id,
            translated_text=f"译文::{request.source_text}",
            input_tokens=10,
            output_tokens=12,
            estimated_cost_usd=0.001,
        )

    async def aclose(self) -> None:
        return None


def _build_sample_epub(path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("id-1")
    book.set_title("Pipeline EPUB")
    chapter1 = epub.EpubHtml(title="Chapter 1", file_name="chapter1.xhtml", lang="en")
    chapter1.content = "<h1>Chapter 1</h1><p>Hello world.</p>"
    chapter2 = epub.EpubHtml(title="Chapter 2", file_name="chapter2.xhtml", lang="en")
    chapter2.content = "<h1>Chapter 2</h1><p>Goodbye world.</p>"
    book.add_item(chapter1)
    book.add_item(chapter2)
    book.toc = (chapter1, chapter2)
    book.spine = ["nav", chapter1, chapter2]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)


@pytest.mark.asyncio
async def test_process_book_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.epub"
    output_dir = tmp_path / "out"
    _build_sample_epub(input_path)

    summary = await process_book(
        input_path=input_path,
        output_root=output_dir,
        config=RunConfig(provider="openai", model="gpt-4o-mini", render_pdf=True),
        provider=FakeProvider("openai", "gpt-4o-mini"),
    )

    book_dir = output_dir / "sample"
    assert summary.successful_chunks == 2
    assert (book_dir / "translated.txt").exists()
    assert (book_dir / "translated.pdf").exists()
    output_text = (book_dir / "translated.txt").read_text(encoding="utf-8")
    assert "Chapter 1" in output_text
    assert "译文::Hello world." in output_text


@pytest.mark.asyncio
async def test_render_pdf_command_uses_existing_workspace(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.epub"
    output_dir = tmp_path / "out"
    _build_sample_epub(input_path)

    await process_book(
        input_path=input_path,
        output_root=output_dir,
        config=RunConfig(provider="openai", model="gpt-4o-mini", render_pdf=False),
        provider=FakeProvider("openai", "gpt-4o-mini"),
    )

    book_dir = output_dir / "sample"
    runner = CliRunner()
    result = runner.invoke(app, ["render-pdf", "--workspace", str(book_dir)])

    assert result.exit_code == 0
    assert (book_dir / "translated.pdf").exists()
