import json
from pathlib import Path

import pytest
from ebooklib import epub
from typer.testing import CliRunner

from book_translator.cli import app
from book_translator.config import (
    PublishingOutputSelection,
    PublishingRunConfig,
    resolve_publishing_outputs,
)
from book_translator.models import PublishingChapterArtifact
from book_translator.providers.base import BaseProvider
from book_translator.publishing.final_review import apply_final_review
from book_translator.publishing.pipeline import process_book_publishing
from book_translator.publishing.proofread import proofread_chapter
from book_translator.publishing.revision import revise_chapter

runner = CliRunner()


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


def test_publishing_run_config_includes_new_defaults() -> None:
    config = PublishingRunConfig()

    assert config.also_pdf is False
    assert config.also_epub is False
    assert config.audit_depth == "consensus"
    assert config.enable_cross_review is True
    assert config.image_policy == "extract-or-preserve-caption"


def test_resolve_publishing_outputs_defaults_to_source_format() -> None:
    pdf_config = PublishingRunConfig()
    epub_config = PublishingRunConfig()

    assert resolve_publishing_outputs(Path("sample.pdf"), pdf_config) == PublishingOutputSelection(
        primary_output="pdf",
        additional_outputs=[],
    )
    assert resolve_publishing_outputs(
        Path("sample.epub"),
        epub_config,
    ) == PublishingOutputSelection(primary_output="epub", additional_outputs=[])


def test_resolve_publishing_outputs_adds_cross_format_extra() -> None:
    pdf_selection = resolve_publishing_outputs(
        Path("sample.pdf"),
        PublishingRunConfig(also_epub=True),
    )
    epub_selection = resolve_publishing_outputs(
        Path("sample.epub"),
        PublishingRunConfig(also_pdf=True),
    )

    assert pdf_selection == PublishingOutputSelection(
        primary_output="pdf",
        additional_outputs=["epub"],
    )
    assert epub_selection == PublishingOutputSelection(
        primary_output="epub",
        additional_outputs=["pdf"],
    )


def test_publishing_cli_passes_new_flags_into_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "sample.epub"
    output_path = tmp_path / "out"
    _build_sample_epub(input_path)
    captured: dict[str, object] = {}

    async def fake_run_publishing_cli(*, input_path, output_path, config):
        captured["input_path"] = input_path
        captured["output_path"] = output_path
        captured["config"] = config

    monkeypatch.setattr("book_translator.cli._run_publishing_cli", fake_run_publishing_cli)

    result = runner.invoke(
        app,
        [
            "publishing",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--also-pdf",
            "--audit-depth",
            "standard",
            "--no-cross-review",
            "--image-policy",
            "extract-or-preserve-caption",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["input_path"] == input_path
    assert captured["output_path"] == output_path
    config = captured["config"]
    assert isinstance(config, PublishingRunConfig)
    assert config.also_pdf is True
    assert config.also_epub is False
    assert config.audit_depth == "standard"
    assert config.enable_cross_review is False
    assert config.image_policy == "extract-or-preserve-caption"


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


def test_proofread_chapter_restores_numbered_methods_sections() -> None:
    chapter = PublishingChapterArtifact(
        chapter_id="chapter-69",
        chapter_index=0,
        title="The 69 Core Musk Methods",
        text=(
            "以下是《埃隆·马斯克传：目标与成功指南》中“69 条核心马斯克方法”的简体中文翻译："
            "这些方法被选为促使埃隆及其公司取得成功的根本理念。"
            "它们已被编辑或改写为简短且令人难忘的准则。"
            "1. 你拥有的能力远超你的想象。"
            "2. 普通人完全可以选择变得不普通。"
            "3. 你可以自学任何东西。"
        ),
    )

    final_artifact, notes = proofread_chapter(chapter)

    assert "以下是《" not in final_artifact.text
    assert "这些方法被选为促使埃隆及其公司取得成功的根本理念。" in final_artifact.text
    assert "\n\n1. 你拥有的能力远超你的想象。" in final_artifact.text
    assert "\n2. 普通人完全可以选择变得不普通。" in final_artifact.text
    assert "\n3. 你可以自学任何东西。" in final_artifact.text
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


class DeepReviewProvider(FakeProvider):
    async def translate(self, request):  # type: ignore[override]
        self.calls += 1
        if "First principle." in request.source_text:
            return self.make_result(
                chunk_id=request.chunk_id,
                translated_text=(
                    "译文::核心方法 1. 第一条原则。 2. 第二条原则。 3. 第三条原则。"
                ),
                input_tokens=10,
                output_tokens=12,
                estimated_cost_usd=0.001,
            )
        return await super().translate(request)


def _build_numbered_list_epub(path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("id-deep-review")
    book.set_title("Deep Review EPUB")
    chapter1 = epub.EpubHtml(title="Chapter 1", file_name="chapter1.xhtml", lang="en")
    chapter1.content = """
    <h1>Chapter 1</h1>
    <p>Core methods:</p>
    <p>1. First principle.</p>
    <p>2. Second principle.</p>
    <p>3. Third principle.</p>
    """
    book.add_item(chapter1)
    book.toc = (chapter1,)
    book.spine = ["nav", chapter1]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)


@pytest.mark.asyncio
async def test_process_book_publishing_runs_deep_review_and_rebuilds_final_text(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "deep-review.epub"
    _build_numbered_list_epub(input_path)

    summary = await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            to_stage="final-review",
            render_pdf=False,
        ),
        provider=DeepReviewProvider(),
    )

    summary = await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            from_stage="deep-review",
            to_stage="deep-review",
            render_pdf=False,
        ),
        provider=FailIfCalledProvider(),
    )

    book_dir = tmp_path / "out" / "deep-review" / "publishing"
    final_text = (book_dir / "final" / "translated.txt").read_text(encoding="utf-8")
    deep_review_rows = [
        json.loads(line)
        for line in (book_dir / "deep_review" / "revised_chapters.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    assert summary["completed_stage"] == "deep-review"
    assert (book_dir / "deep_review" / "findings.jsonl").exists()
    assert (book_dir / "deep_review" / "revised_chapters.jsonl").exists()
    assert (book_dir / "deep_review" / "decisions.json").exists()
    assert (book_dir / "audit" / "source_audit.jsonl").exists()
    assert (book_dir / "audit" / "review_audit.jsonl").exists()
    assert (book_dir / "audit" / "consensus.json").exists()
    assert (book_dir / "audit" / "final_audit_report.json").exists()
    assert "译文::核心方法" in final_text
    assert "1. 第一条原则。" in final_text
    assert "2. 第二条原则。" in final_text
    assert "3. 第三条原则。" in final_text
    assert "First principle." not in final_text
    assert deep_review_rows
    assert "blocks" in deep_review_rows[0]


@pytest.mark.asyncio
async def test_process_book_publishing_resume_from_revision_keeps_lexicon_decisions(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "sample.epub"
    glossary_path = tmp_path / "glossary.json"
    _build_sample_epub(input_path)
    glossary_path.write_text(json.dumps({"Mars": "火星"}, ensure_ascii=False), encoding="utf-8")

    await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            glossary_path=glossary_path,
            render_pdf=False,
        ),
        provider=FakeProvider(),
    )

    summary = await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            glossary_path=glossary_path,
            from_stage="revision",
            render_pdf=False,
        ),
        provider=FailIfCalledProvider(),
    )

    assert summary["decision_count"] == 1


@pytest.mark.asyncio
async def test_final_review_cache_hit_survives_rebuild_written_title_translations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "sample.epub"
    _build_sample_epub(input_path)

    async def fake_enrich_missing_titles(**kwargs):
        workspace = kwargs["workspace"]
        workspace.write_title_translations({"chapter-1-0": "第一章"})
        return kwargs["book"]

    def fake_render_polished_pdf(book, path, edition_label):
        _ = book, edition_label
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pdf", encoding="utf-8")

    def fail_if_final_review_called(_proofread_artifacts):
        raise AssertionError("final-review should have been skipped on cache hit")

    monkeypatch.setattr(
        "book_translator.publishing.pipeline.enrich_missing_titles",
        fake_enrich_missing_titles,
    )
    monkeypatch.setattr(
        "book_translator.publishing.pipeline.render_polished_pdf",
        fake_render_polished_pdf,
    )

    await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            to_stage="final-review",
        ),
        provider=FakeProvider(),
    )

    monkeypatch.setattr(
        "book_translator.publishing.pipeline.apply_final_review",
        fail_if_final_review_called,
    )

    summary = await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            from_stage="final-review",
            to_stage="final-review",
        ),
        provider=FailIfCalledProvider(),
    )

    assert summary["completed_stage"] == "final-review"


@pytest.mark.asyncio
async def test_process_book_publishing_rebuilds_pdf_when_title_translations_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "sample.epub"
    _build_sample_epub(input_path)

    async def fake_enrich_missing_titles(**kwargs):
        return kwargs["book"]

    def fake_render_polished_pdf(book, path, edition_label):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "edition_label": edition_label,
                    "chapters": [
                        {
                            "chapter_id": chapter.chapter_id,
                            "title_en": chapter.title_en,
                            "title_zh": chapter.title_zh,
                        }
                        for chapter in book.chapters
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "book_translator.publishing.pipeline.enrich_missing_titles",
        fake_enrich_missing_titles,
    )
    monkeypatch.setattr(
        "book_translator.publishing.pipeline.render_polished_pdf",
        fake_render_polished_pdf,
    )

    await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            to_stage="deep-review",
        ),
        provider=FakeProvider(),
    )

    workspace_dir = tmp_path / "out" / "sample"
    title_translations_path = workspace_dir / "title_translations.json"
    pdf_path = workspace_dir / "publishing" / "final" / "translated.pdf"
    original_pdf_payload = pdf_path.read_text(encoding="utf-8")

    title_translations_path.write_text(
        json.dumps({"chapter-1-0": "第一章"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            from_stage="final-review",
            to_stage="deep-review",
        ),
        provider=FailIfCalledProvider(),
    )

    rebuilt_pdf_payload = pdf_path.read_text(encoding="utf-8")

    assert original_pdf_payload != rebuilt_pdf_payload
    assert '"chapter_id": "chapter-1-0"' in rebuilt_pdf_payload
    assert '"title_zh": "第一章"' in rebuilt_pdf_payload


class PartialDeepReviewProvider(FakeProvider):
    async def translate(self, request):  # type: ignore[override]
        self.calls += 1
        if "Needs cleanup." in request.source_text:
            return self.make_result(
                chunk_id=request.chunk_id,
                translated_text="Draft  text with double spaces.",
                input_tokens=10,
                output_tokens=12,
                estimated_cost_usd=0.001,
            )
        if "Already clean." in request.source_text:
            return self.make_result(
                chunk_id=request.chunk_id,
                translated_text="Already clean.",
                input_tokens=10,
                output_tokens=12,
                estimated_cost_usd=0.001,
            )
        return await super().translate(request)


def _build_mixed_deep_review_epub(path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("id-mixed-deep-review")
    book.set_title("Mixed Deep Review EPUB")
    chapter1 = epub.EpubHtml(title="Chapter 1", file_name="chapter1.xhtml", lang="en")
    chapter1.content = """
    <h1>Chapter 1</h1>
    <p>Needs cleanup.</p>
    """
    chapter2 = epub.EpubHtml(title="Chapter 2", file_name="chapter2.xhtml", lang="en")
    chapter2.content = """
    <h1>Chapter 2</h1>
    <p>Already clean.</p>
    """
    book.add_item(chapter1)
    book.add_item(chapter2)
    book.toc = (chapter1, chapter2)
    book.spine = ["nav", chapter1, chapter2]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)


@pytest.mark.asyncio
async def test_process_book_publishing_reports_only_changed_deep_review_chapters(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "sample.epub"
    _build_sample_epub(input_path)

    await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            to_stage="final-review",
            render_pdf=False,
        ),
        provider=FakeProvider(),
    )

    final_chapters_path = (
        tmp_path / "out" / "sample" / "publishing" / "final" / "final_chapters.jsonl"
    )
    final_chapters_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "chapter_id": "chapter-1-0",
                        "chapter_index": 0,
                        "title": "Chapter 1",
                        "text": "Draft  text with double spaces.",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "chapter_id": "chapter-2-1",
                        "chapter_index": 1,
                        "title": "Chapter 2",
                        "text": "Already clean.",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            from_stage="deep-review",
            to_stage="deep-review",
            render_pdf=False,
        ),
        provider=FailIfCalledProvider(),
    )

    final_chapters_rows = final_chapters_path.read_text(encoding="utf-8")

    assert summary["deep_review_revised_chapters"] == 1
    assert "Draft  text with double spaces." not in final_chapters_rows
    assert "Draft text with double spaces." in final_chapters_rows


@pytest.mark.asyncio
async def test_deep_review_rerun_preserves_last_good_final_outputs_on_render_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "sample.epub"
    _build_sample_epub(input_path)

    async def fake_enrich_missing_titles(**kwargs):
        return kwargs["book"]

    def fake_render_polished_pdf(book, path, edition_label):
        _ = book, edition_label
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stable pdf", encoding="utf-8")

    monkeypatch.setattr(
        "book_translator.publishing.pipeline.enrich_missing_titles",
        fake_enrich_missing_titles,
    )
    monkeypatch.setattr(
        "book_translator.publishing.pipeline.render_polished_pdf",
        fake_render_polished_pdf,
    )

    await process_book_publishing(
        input_path=input_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(
            provider="openai",
            model="gpt-4o-mini",
            to_stage="deep-review",
        ),
        provider=FakeProvider(),
    )

    workspace_dir = tmp_path / "out" / "sample"
    title_translations_path = workspace_dir / "title_translations.json"
    final_text_path = workspace_dir / "publishing" / "final" / "translated.txt"
    final_pdf_path = workspace_dir / "publishing" / "final" / "translated.pdf"
    original_text = final_text_path.read_text(encoding="utf-8")
    original_pdf = final_pdf_path.read_text(encoding="utf-8")

    title_translations_path.write_text(
        json.dumps({"chapter-1-0": "第一章"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    def raising_render_polished_pdf(book, path, edition_label):
        _ = book, path, edition_label
        raise RuntimeError("render failed")

    monkeypatch.setattr(
        "book_translator.publishing.pipeline.render_polished_pdf",
        raising_render_polished_pdf,
    )

    with pytest.raises(RuntimeError, match="render failed"):
        await process_book_publishing(
            input_path=input_path,
            output_root=tmp_path / "out",
            config=PublishingRunConfig(
                provider="openai",
                model="gpt-4o-mini",
                from_stage="deep-review",
                to_stage="deep-review",
            ),
            provider=FailIfCalledProvider(),
        )

    assert final_text_path.read_text(encoding="utf-8") == original_text
    assert final_pdf_path.read_text(encoding="utf-8") == original_pdf
