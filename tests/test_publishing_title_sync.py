from pathlib import Path

import pytest

from booksmith.config import PublishingRunConfig
from booksmith.models import (
    Manifest,
    PublishingBlock,
    StructuredPublishingBook,
    StructuredPublishingChapter,
)
from booksmith.output.title_enrichment import apply_title_overrides_to_structured_book
from booksmith.publishing.pipeline import _rebuild_stable_publishing_outputs
from booksmith.state.workspace import Workspace


def test_apply_title_overrides_to_structured_book_updates_translated_titles() -> None:
    book = StructuredPublishingBook(
        title="Sample Book",
        chapters=[
            StructuredPublishingChapter(
                chapter_id="chapter-1",
                chapter_index=0,
                source_title="Obsess for Success",
                translated_title="Obsess for Success",
                blocks=[
                    PublishingBlock(
                        block_id="chapter-1-block-1",
                        kind="paragraph",
                        text="正文",
                        order_index=1,
                    )
                ],
            )
        ],
    )

    enriched = apply_title_overrides_to_structured_book(
        book,
        {"chapter-1": "痴迷于成功"},
    )

    assert enriched.chapters[0].translated_title == "痴迷于成功"
    assert enriched.chapters[0].source_title == "Obsess for Success"
    assert book.chapters[0].translated_title == "Obsess for Success"


@pytest.mark.asyncio
async def test_rebuild_stable_publishing_outputs_syncs_title_overrides_to_structured_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace(tmp_path / "book")
    source_path = tmp_path / "sample.epub"
    source_path.write_text("stub", encoding="utf-8")

    manifest = Manifest(
        book_id="book",
        source_path=str(source_path),
        source_fingerprint="fingerprint",
        provider="openai",
        model="gpt-4o-mini",
        config_fingerprint="config",
    )
    config = PublishingRunConfig(
        provider="openai",
        model="gpt-4o-mini",
        also_pdf=True,
    )
    structured_book = StructuredPublishingBook(
        title="Sample Book",
        chapters=[
            StructuredPublishingChapter(
                chapter_id="chapter-1",
                chapter_index=0,
                source_title="Obsess for Success",
                translated_title="Obsess for Success",
                blocks=[
                    PublishingBlock(
                        block_id="chapter-1-block-1",
                        kind="paragraph",
                        text="正文第一段。",
                        order_index=1,
                    )
                ],
            )
        ],
    )
    rendered: dict[str, object] = {}

    async def fake_enrich_missing_titles(*, book, workspace, **kwargs):
        workspace.write_title_translations({"chapter-1": "痴迷于成功"})
        return book

    def fake_render_polished_pdf(book, path, *, edition_label):
        rendered["pdf_titles"] = [chapter.title_zh for chapter in book.chapters]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(edition_label, encoding="utf-8")

    def fake_render_structured_epub(book, path, **kwargs):
        rendered["epub_titles"] = [chapter.translated_title for chapter in book.chapters]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("epub", encoding="utf-8")

    monkeypatch.setattr(
        "booksmith.publishing.pipeline.enrich_missing_titles",
        fake_enrich_missing_titles,
    )
    monkeypatch.setattr(
        "booksmith.publishing.pipeline.render_polished_pdf",
        fake_render_polished_pdf,
    )
    monkeypatch.setattr(
        "booksmith.publishing.pipeline.render_structured_epub",
        fake_render_structured_epub,
    )

    await _rebuild_stable_publishing_outputs(
        workspace=workspace,
        manifest=manifest,
        chapters=[],
        config=config,
        provider=None,
        summary_metrics={"estimated_cost_usd": 0.0},
        deep_review_book=structured_book,
        deep_review_chapters=[],
        deep_review_decisions={},
    )

    assert rendered["pdf_titles"] == ["痴迷于成功"]
    assert rendered["epub_titles"] == ["痴迷于成功"]
    assert workspace.publishing_final_text_path.read_text(encoding="utf-8").startswith(
        "痴迷于成功"
    )

    deep_review_rows = workspace.read_publishing_jsonl(
        workspace.publishing_deep_review_chapters_path
    )
    assert deep_review_rows == [
        {
            "chapter_id": "chapter-1",
            "chapter_index": 0,
            "source_title": "Obsess for Success",
            "translated_title": "痴迷于成功",
            "blocks": [
                {
                    "block_id": "chapter-1-block-1",
                    "kind": "paragraph",
                    "text": "正文第一段。",
                    "order_index": 1,
                    "source_anchor": None,
                    "citations": [],
                    "issue_tags": [],
                }
            ],
            "assets": [],
        }
    ]
