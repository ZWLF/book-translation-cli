from pathlib import Path

import pytest

from book_translator.output.polished_pdf import PrintableBlock, PrintableBook, PrintableChapter
from book_translator.output.title_enrichment import enrich_missing_titles
from book_translator.state.workspace import Workspace


def _book() -> PrintableBook:
    return PrintableBook(
        book_id="sample-book",
        title_en="Sample Book",
        title_zh="示例图书",
        author="Author Name",
        source_path=r"H:\books\Sample Book (Author Name).pdf",
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        estimated_cost_usd=0.0,
        chapters=[
            PrintableChapter(
                chapter_id="chapter-1",
                chapter_index=0,
                source_title="Obsess for Success",
                title_kind="chapter",
                title_en="Obsess for Success",
                title_zh=None,
                header_title="Obsess for Success",
                toc_label_html="Obsess for Success",
                blocks=[PrintableBlock(kind="paragraph", text="正文。")],
            ),
            PrintableChapter(
                chapter_id="chapter-2",
                chapter_index=1,
                source_title="Think like a Physicist",
                title_kind="chapter",
                title_en="Think like a Physicist",
                title_zh="像物理学家一样思考",
                header_title="像物理学家一样思考",
                toc_label_html="像物理学家一样思考",
                blocks=[PrintableBlock(kind="paragraph", text="正文。")],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_enrich_missing_titles_uses_cache_and_updates_workspace(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    workspace.root.mkdir(parents=True, exist_ok=True)
    workspace.write_title_translations({"chapter-1": "缓存标题"})

    calls: list[str] = []

    async def fake_translator(title_en: str, book_title: str) -> str:
        calls.append(f"{book_title}::{title_en}")
        return "新标题"

    enriched = await enrich_missing_titles(
        book=_book(),
        workspace=workspace,
        translator=fake_translator,
    )

    assert calls == []
    assert enriched.chapters[0].title_zh == "缓存标题"
    assert enriched.chapters[0].header_title == "缓存标题"
    assert "缓存标题" in enriched.chapters[0].toc_label_html


@pytest.mark.asyncio
async def test_enrich_missing_titles_translates_only_missing_entries(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    workspace.root.mkdir(parents=True, exist_ok=True)

    calls: list[str] = []

    async def fake_translator(title_en: str, book_title: str) -> str:
        calls.append(f"{book_title}::{title_en}")
        return "痴迷于成功"

    enriched = await enrich_missing_titles(
        book=_book(),
        workspace=workspace,
        translator=fake_translator,
    )

    assert calls == ["Sample Book::Obsess for Success"]
    assert enriched.chapters[0].title_zh == "痴迷于成功"
    assert enriched.chapters[1].title_zh == "像物理学家一样思考"
    assert workspace.read_title_translations() == {"chapter-1": "痴迷于成功"}


@pytest.mark.asyncio
async def test_enrich_missing_titles_normalizes_cached_method_titles(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    workspace.root.mkdir(parents=True, exist_ok=True)
    workspace.write_title_translations({"chapter-1": "马斯克核心法则69条"})

    book = PrintableBook(
        book_id="sample-book",
        title_en="Sample Book",
        title_zh="示例图书",
        author="Author Name",
        source_path=r"H:\books\Sample Book (Author Name).pdf",
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        estimated_cost_usd=0.0,
        chapters=[
            PrintableChapter(
                chapter_id="chapter-1",
                chapter_index=0,
                source_title="The 69 Core Musk Methods",
                title_kind="chapter",
                title_en="The 69 Core Musk Methods",
                title_zh=None,
                header_title="The 69 Core Musk Methods",
                toc_label_html="The 69 Core Musk Methods",
                blocks=[PrintableBlock(kind="paragraph", text="正文")],
            )
        ],
    )

    enriched = await enrich_missing_titles(
        book=book,
        workspace=workspace,
        translator=None,
    )

    assert enriched.chapters[0].title_zh == "马斯克的 69 条核心法则"
