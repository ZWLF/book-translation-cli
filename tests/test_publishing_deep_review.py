from __future__ import annotations

from book_translator.models import PublishingAuditFinding, PublishingChapterArtifact
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


def test_task3_does_not_expand_publishing_chapter_artifact_schema() -> None:
    assert "layout_annotations" not in PublishingChapterArtifact.model_fields
