from pathlib import Path

import pytest
from ebooklib import epub

from book_translator.config import PublishingRunConfig
from book_translator.models import PublishingChapterArtifact
from book_translator.providers.base import BaseProvider
from book_translator.publishing.final_review import apply_final_review
from book_translator.publishing.pipeline import process_book_publishing
from book_translator.publishing.proofread import proofread_chapter
from book_translator.publishing.revision import revise_chapter


class FakeProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("openai", "gpt-4o-mini")
        self.calls = 0

    async def translate(self, request):  # type: ignore[override]
        self.calls += 1
        return self.make_result(
            chunk_id=request.chunk_id,
            translated_text=f"译文::{request.source_text}",
            input_tokens=10,
            output_tokens=12,
            estimated_cost_usd=0.001,
        )


class FailIfCalledProvider(FakeProvider):
    async def translate(self, request):  # type: ignore[override]
        raise AssertionError("draft stage should have been skipped")


def _build_sample_epub(path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("id-1")
    book.set_title("Publishing EPUB")
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


@pytest.mark.asyncio
async def test_process_book_publishing_writes_stage_artifacts(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.epub"
    _build_sample_epub(input_path)

    summary = await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(provider="openai", model="gpt-4o-mini"),
        provider=FakeProvider(),
    )

    book_dir = tmp_path / "out" / "sample" / "publishing"
    assert (book_dir / "draft" / "draft.txt").exists()
    assert (book_dir / "draft" / "chapters.jsonl").exists()
    assert (book_dir / "lexicon" / "glossary.json").exists()
    assert (book_dir / "final" / "translated.txt").exists()
    assert (book_dir / "final" / "translated.pdf").exists()
    assert (book_dir / "editorial_log.json").exists()
    assert summary["mode"] == "publishing"


@pytest.mark.asyncio
async def test_process_book_publishing_from_stage_revision_skips_draft_and_lexicon(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "sample.epub"
    _build_sample_epub(input_path)

    await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(provider="openai", model="gpt-4o-mini"),
        provider=FakeProvider(),
    )

    summary = await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            from_stage="revision",
        ),
        provider=FailIfCalledProvider(),
    )

    assert summary["started_stage"] == "revision"


def test_proofread_chapter_normalizes_spacing_and_emits_notes() -> None:
    chapter = PublishingChapterArtifact(
        chapter_id="chapter-1",
        chapter_index=0,
        title="Sample",
        text="我在  PayPal  工作。  2002 年，我们 达成了协议 。",
    )

    final_artifact, notes = proofread_chapter(chapter)

    assert final_artifact.text == "我在 PayPal 工作。2002 年，我们达成了协议。"
    assert notes
    assert any(note["type"] == "spacing_normalization" for note in notes)


def test_apply_final_review_sorts_and_emits_editorial_log() -> None:
    chapters = [
        PublishingChapterArtifact(chapter_id="b", chapter_index=1, title="B", text="Two  words 。"),
        PublishingChapterArtifact(chapter_id="a", chapter_index=0, title="A", text="One  words 。"),
    ]

    reviewed, editorial_log = apply_final_review(chapters)

    assert [item.chapter_id for item in reviewed] == ["a", "b"]
    assert reviewed[0].text == "One words。"
    assert reviewed[1].text == "Two words。"
    assert editorial_log
    assert any(entry["type"] == "whole_book_normalization" for entry in editorial_log)


@pytest.mark.asyncio
async def test_process_book_publishing_reports_proofread_and_editorial_counts(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "sample.epub"
    _build_sample_epub(input_path)

    summary = await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(provider="openai", model="gpt-4o-mini"),
        provider=FakeProvider(),
    )

    assert summary["mode"] == "publishing"
    assert summary["proofread_notes"] > 0
    assert summary["editorial_log_entries"] > 0
