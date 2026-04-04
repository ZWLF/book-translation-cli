from __future__ import annotations

from book_translator.models import (
    Chapter,
    PublishingAuditFinding,
    PublishingBlock,
    PublishingChapterArtifact,
    StructuredPublishingBook,
    StructuredPublishingChapter,
)
from book_translator.output.assembler import assemble_structured_publishing_output_text
from book_translator.publishing.deep_review import run_deep_review
from book_translator.publishing.editorial_revision import apply_editorial_repairs
from book_translator.publishing.layout_review import generate_layout_annotations


def test_apply_editorial_repairs_restores_numbered_list_blocks() -> None:
    findings = [
        PublishingAuditFinding(
            chapter_id="c1",
            finding_type="collapsed_numbered_list",
            severity="high",
            source_excerpt="1. One.\n2. Two.\n3. Three.",
            target_excerpt="1. One 2. Two 3. Three",
            reason="list collapsed",
            auto_fixable=True,
        )
    ]

    repaired = apply_editorial_repairs(
        chapter_text="1. One 2. Two 3. Three",
        source_text="1. One.\n2. Two.\n3. Three.",
        findings=findings,
    )

    assert repaired.startswith("1. One")
    assert "\n2. Two" in repaired
    assert "\n3. Three" in repaired


def test_apply_editorial_repairs_normalizes_editorial_spacing() -> None:
    repaired = apply_editorial_repairs(
        chapter_text="你好  世界 。This  is   a test 。",
        source_text="",
        findings=[],
    )

    assert repaired == "你好世界。This is a test。"


def test_apply_editorial_repairs_keeps_non_fixable_findings_bounded() -> None:
    findings = [
        PublishingAuditFinding(
            chapter_id="c2",
            finding_type="possible_omission",
            severity="medium",
            source_excerpt="Gamma.",
            target_excerpt="Alpha. Beta.",
            reason="not enough units",
            auto_fixable=False,
        )
    ]

    repaired = apply_editorial_repairs(
        chapter_text="Alpha.  Beta.",
        source_text="Alpha. Beta. Gamma.",
        findings=findings,
    )

    assert repaired == "Alpha. Beta."


def test_generate_layout_annotations_prefers_chapter_quote_for_callout_text() -> None:
    findings = [
        PublishingAuditFinding(
            chapter_id="c3",
            finding_type="callout_candidate",
            severity="medium",
            source_excerpt='Remember this: "Life is too short for long-term grudges."',
            target_excerpt=(
                "This broader excerpt includes setup context and should not become the "
                "callout payload directly."
            ),
            reason="short emphasized quotation",
            auto_fixable=True,
        )
    ]

    chapter_text = (
        "A broad paragraph introduces context.\n"
        '"Life is too short for long-term grudges."\n'
        "A closing sentence follows."
    )
    annotations = generate_layout_annotations(
        source_text='Remember this: "Life is too short for long-term grudges."',
        chapter_text=chapter_text,
        findings=findings,
    )

    assert len(annotations) == 1
    assert annotations[0].kind == "callout"
    assert annotations[0].payload["text"] == "Life is too short for long-term grudges."


def test_generate_layout_annotations_selects_quote_aligned_with_finding() -> None:
    findings = [
        PublishingAuditFinding(
            chapter_id="c3b",
            finding_type="callout_candidate",
            severity="medium",
            source_excerpt='Remember this: "Build systems, not goals."',
            target_excerpt=(
                "The chapter contrasts slogans and then stresses that "
                '"Build systems, not goals." is the durable principle.'
            ),
            reason="short emphasized quotation",
            auto_fixable=True,
        )
    ]

    chapter_text = (
        '"Move fast and break things."\n'
        'Some context in between.\n'
        '"Build systems, not goals."\n'
        "Closing line."
    )
    annotations = generate_layout_annotations(
        source_text='Remember this: "Build systems, not goals."',
        chapter_text=chapter_text,
        findings=findings,
    )

    assert len(annotations) == 1
    assert annotations[0].kind == "callout"
    assert annotations[0].payload["text"] == "Build systems, not goals."


def test_generate_layout_annotations_qa_flags_come_from_translated_text_only() -> None:
    findings = [
        PublishingAuditFinding(
            chapter_id="c4",
            finding_type="question_answer_structure",
            severity="medium",
            source_excerpt="Q: Why now?\nA: Because the window is open.",
            target_excerpt="Q: 为什么是现在？\n因为窗口已打开。",
            reason="missing answer marker",
            auto_fixable=False,
        )
    ]

    annotations = generate_layout_annotations(
        source_text="Q: Why now?\nA: Because the window is open.",
        chapter_text="Q: 为什么是现在？\n因为窗口已打开。",
        findings=findings,
    )

    assert len(annotations) == 1
    assert annotations[0].kind == "qa_block"
    assert annotations[0].payload["anchor"] == "Q: 为什么是现在？\n因为窗口已打开。"
    assert annotations[0].payload["has_question_marker"] is True
    assert annotations[0].payload["has_answer_marker"] is False


def test_generate_layout_annotations_qa_flags_false_when_both_markers_dropped() -> None:
    findings = [
        PublishingAuditFinding(
            chapter_id="c5",
            finding_type="question_answer_structure",
            severity="medium",
            source_excerpt="Q: Why now?\nA: Because the window is open.",
            target_excerpt="为什么是现在？\n因为窗口已打开。",
            reason="missing both markers",
            auto_fixable=False,
        )
    ]

    annotations = generate_layout_annotations(
        source_text="Q: Why now?\nA: Because the window is open.",
        chapter_text="为什么是现在？\n因为窗口已打开。",
        findings=findings,
    )

    assert len(annotations) == 1
    assert annotations[0].kind == "qa_block"
    assert annotations[0].payload["has_question_marker"] is False
    assert annotations[0].payload["has_answer_marker"] is False


def test_generate_layout_annotations_qa_anchor_stops_before_follow_up_paragraph() -> None:
    findings = [
        PublishingAuditFinding(
            chapter_id="c6",
            finding_type="question_answer_structure",
            severity="medium",
            source_excerpt="Why now?\nBecause the window is open.",
            target_excerpt=(
                "Why now?\nBecause the window is open.\n\n"
                "This follow-up paragraph should stay separate."
            ),
            reason="verify question and answer layout",
            auto_fixable=False,
        )
    ]

    annotations = generate_layout_annotations(
        source_text="Why now?\nBecause the window is open.",
        chapter_text=(
            "Why now?\nBecause the window is open.\n\n"
            "This follow-up paragraph should stay separate."
        ),
        findings=findings,
    )

    assert len(annotations) == 1
    assert annotations[0].kind == "qa_block"
    assert annotations[0].payload["anchor"] == "Why now?\nBecause the window is open."
    assert annotations[0].payload["has_question_marker"] is False
    assert annotations[0].payload["has_answer_marker"] is False


def test_task3_does_not_expand_publishing_chapter_artifact_schema() -> None:
    assert "layout_annotations" not in PublishingChapterArtifact.model_fields


def test_run_deep_review_builds_structured_book_and_audit_report() -> None:
    source_chapters = [
        Chapter(
            chapter_id="chapter-1",
            chapter_index=0,
            title="Chapter 1",
            text="Core methods:\n1. First principle.\n2. Second principle.\n3. Third principle.",
        )
    ]
    final_artifacts = [
        PublishingChapterArtifact(
            chapter_id="chapter-1",
            chapter_index=0,
            title="Chapter 1",
            text=(
                "核心方法：\n\n"
                "1. 第一条原则。 2. 第二条原则。 3. 第三条原则。"
            ),
        )
    ]

    result = run_deep_review(source_chapters=source_chapters, final_artifacts=final_artifacts)

    assert isinstance(result.structured_book, StructuredPublishingBook)
    assert result.findings
    assert result.repair_passes == 1
    assert result.confirmation_passes == 1
    assert result.final_report["source_finding_count"] >= 1
    assert result.final_report["confirmation_finding_count"] >= 0
    assert any(
        block.kind == "ordered_item"
        for block in result.structured_book.chapters[0].blocks
    )
    assert "1. 第一条原则。" in result.revised_chapters[0].text
    assert "2. 第二条原则。" in result.revised_chapters[0].text


    chapter_gate = result.decisions["chapters"][0]
    assert chapter_gate["audit_finding_count"] >= 1
    assert chapter_gate["unresolved_count"] >= 0
    assert chapter_gate["rollback_level_required"] in {
        "none",
        "chapter_repair",
        "chapter_redraft",
        "chapter_retranslate",
    }


def test_run_deep_review_forwards_source_title_to_source_audit(monkeypatch) -> None:
    seen_titles: list[str | None] = []

    def fake_audit_source_against_target(
        *,
        chapter_id: str,
        source_text: str,
        target_text: str,
        source_title: str | None = None,
    ) -> list[PublishingAuditFinding]:
        seen_titles.append(source_title)
        return []

    monkeypatch.setattr(
        "book_translator.publishing.deep_review.audit_source_against_target",
        fake_audit_source_against_target,
    )

    source_chapters = [
        Chapter(
            chapter_id="chapter-1",
            chapter_index=0,
            title="Create more than you consume.",
            text=(
                "Create more than you consume.\n\n"
                "Build things.\n"
                "Serve people."
            ),
        )
    ]
    final_artifacts = [
        PublishingChapterArtifact(
            chapter_id="chapter-1",
            chapter_index=0,
            title="Create more than you consume.",
            text=(
                "创造的多于消费。\n\n"
                "打造产品。\n"
                "服务他人。"
            ),
        )
    ]

    result = run_deep_review(source_chapters=source_chapters, final_artifacts=final_artifacts)

    assert seen_titles
    assert seen_titles == ["Create more than you consume."] * len(seen_titles)
    assert result.final_report["source_finding_count"] == 0


def test_assemble_structured_publishing_output_text_preserves_ordered_items() -> None:
    book = StructuredPublishingBook(
        title="Sample Book",
        chapters=[
            StructuredPublishingChapter(
                chapter_id="chapter-1",
                chapter_index=0,
                source_title="Chapter 1",
                translated_title="Chapter 1",
                blocks=[
                    PublishingBlock(
                        block_id="chapter-1-block-1",
                        kind="paragraph",
                        text="Intro paragraph.",
                        order_index=1,
                    ),
                    PublishingBlock(
                        block_id="chapter-1-block-2",
                        kind="ordered_item",
                        text="第一条原则。",
                        order_index=2,
                        source_anchor="1. First principle.",
                    ),
                    PublishingBlock(
                        block_id="chapter-1-block-3",
                        kind="ordered_item",
                        text="第二条原则。",
                        order_index=3,
                        source_anchor="2. Second principle.",
                    ),
                ],
            )
        ],
    )

    output = assemble_structured_publishing_output_text(book)

    assert "Chapter 1" in output
    assert "Intro paragraph." in output
    assert "1. 第一条原则。" in output
    assert "2. 第二条原则。" in output


def test_assemble_structured_publishing_output_text_uses_translated_ordered_item_text() -> None:
    book = StructuredPublishingBook(
        title="Sample Book",
        chapters=[
            StructuredPublishingChapter(
                chapter_id="chapter-1",
                chapter_index=0,
                source_title="Chapter 1",
                translated_title="第一章",
                blocks=[
                    PublishingBlock(
                        block_id="chapter-1-block-1",
                        kind="ordered_item",
                        text="第一条原则。",
                        order_index=1,
                        source_anchor="1. First principle.",
                    ),
                ],
            )
        ],
    )

    output = assemble_structured_publishing_output_text(book)

    assert "1. 第一条原则。" in output
    assert "First principle" not in output


def test_run_deep_review_flags_missing_source_chapter() -> None:
    result = run_deep_review(
        source_chapters=[],
        final_artifacts=[
            PublishingChapterArtifact(
                chapter_id="chapter-missing",
                chapter_index=0,
                title="Missing",
                text="Unmapped translated content.",
            )
        ],
    )

    assert result.findings
    assert result.findings[0].finding_type == "missing_source_chapter"
    assert result.final_report["unresolved_count"] >= 1
    assert result.final_report["high_severity_count"] >= 1
    assert result.decisions["chapters"][0]["rollback_level_required"] == "book_retranslate"


def test_run_deep_review_standard_mode_skips_review_findings() -> None:
    result = run_deep_review(
        source_chapters=[
            Chapter(
                chapter_id="chapter-1",
                chapter_index=0,
                title="Chapter 1",
                text="1. First.\n2. Second.\n3. Third.",
            )
        ],
        final_artifacts=[
            PublishingChapterArtifact(
                chapter_id="chapter-1",
                chapter_index=0,
                title="Chapter 1",
                text="1. First. 2. Second. 3. Third.",
            )
        ],
        audit_depth="standard",
    )

    assert result.review_findings == []
    assert result.final_report["audit_depth"] == "standard"
    assert result.final_report["review_finding_count"] == 0


def test_run_deep_review_disables_cross_review_when_requested() -> None:
    result = run_deep_review(
        source_chapters=[
            Chapter(
                chapter_id="chapter-1",
                chapter_index=0,
                title="Chapter 1",
                text="1. First.\n2. Second.\n3. Third.",
            )
        ],
        final_artifacts=[
            PublishingChapterArtifact(
                chapter_id="chapter-1",
                chapter_index=0,
                title="Chapter 1",
                text="1. First. 2. Second. 3. Third.",
            )
        ],
        enable_cross_review=False,
    )

    assert result.review_findings == []
    assert result.final_report["cross_review_enabled"] is False


def test_deep_review_assigns_chapter_redraft_when_confirmation_findings_remain() -> None:
    result = run_deep_review(
        source_chapters=[
            Chapter(
                chapter_id="c1",
                chapter_index=0,
                title="Chapter 1",
                text="Alpha.\nBeta.\nGamma.\nDelta.\nEpsilon.",
            )
        ],
        final_artifacts=[
            PublishingChapterArtifact(
                chapter_id="c1",
                chapter_index=0,
                title="Chapter 1",
                text="Alpha.",
            )
        ],
        enable_cross_review=True,
    )

    chapter = result.decisions["chapters"][0]

    assert chapter["unresolved_count"] > 0
    assert chapter["rollback_level_required"] in {"chapter_redraft", "chapter_retranslate"}


def test_deep_review_counts_structure_findings_separately() -> None:
    result = run_deep_review(
        source_chapters=[
            Chapter(
                chapter_id="c-struct",
                chapter_index=0,
                title="Chapter 1",
                text="1. Alpha.\n2. Beta.\n3. Gamma.",
            )
        ],
        final_artifacts=[
            PublishingChapterArtifact(
                chapter_id="c-struct",
                chapter_index=0,
                title="Chapter 1",
                text="Alpha Beta Gamma",
            )
        ],
    )

    assert result.final_report["structural_issue_count"] >= 1


def test_assemble_structured_publishing_output_text_keeps_qa_blocks_tight() -> None:
    book = StructuredPublishingBook(
        title="Sample Book",
        chapters=[
            StructuredPublishingChapter(
                chapter_id="chapter-qa",
                chapter_index=0,
                source_title="Q&A",
                translated_title="闂€佺瓟",
                blocks=[
                    PublishingBlock(
                        block_id="chapter-qa-block-1",
                        kind="qa_question",
                        text="Q: Why now?",
                        order_index=1,
                    ),
                    PublishingBlock(
                        block_id="chapter-qa-block-2",
                        kind="qa_answer",
                        text="A: Because the window is open.",
                        order_index=2,
                    ),
                ],
            )
        ],
    )

    output = assemble_structured_publishing_output_text(book)

    assert "Q: Why now?\nA: Because the window is open." in output
