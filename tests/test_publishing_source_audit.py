from __future__ import annotations

from book_translator.models import PublishingAuditFinding
from book_translator.publishing.source_audit import audit_source_against_target


def _finding_types(findings: list[PublishingAuditFinding]) -> list[str]:
    return [item.finding_type for item in findings]


def test_audit_detects_collapsed_numbered_list() -> None:
    findings = audit_source_against_target(
        chapter_id="c1",
        source_text="1. First idea.\n2. Second idea.\n3. Third idea.",
        target_text="1. 第一条。2. 第二条。3. 第三条。",
    )

    assert _finding_types(findings) == ["collapsed_numbered_list"]


def test_audit_detects_possible_omission_candidates() -> None:
    findings = audit_source_against_target(
        chapter_id="c2",
        source_text="Alpha.\nBeta.\nGamma.",
        target_text="Alpha.\nBeta.",
    )

    assert _finding_types(findings) == ["possible_omission"]


def test_audit_detects_callout_candidates() -> None:
    findings = audit_source_against_target(
        chapter_id="c3",
        source_text='Remember this:\n"Focus compounds over decades."',
        target_text="记住这一点：专注会在数十年里复利。",
    )

    assert _finding_types(findings) == ["callout_candidate"]


def test_audit_detects_question_answer_structure_issues() -> None:
    findings = audit_source_against_target(
        chapter_id="c4",
        source_text="Q: What matters most?\nA: Build useful things.",
        target_text="Q: 什么最重要？\n先做有用的事。",
    )

    assert _finding_types(findings) == ["question_answer_structure"]


def test_audit_keeps_heuristics_conservative_for_plain_paragraphs() -> None:
    findings = audit_source_against_target(
        chapter_id="c5",
        source_text="This is a plain narrative paragraph with no strong structural cues.",
        target_text="这是一个普通叙述段落，没有明显结构提示。",
    )

    assert _finding_types(findings) == []


def test_audit_does_not_flag_short_chinese_sentence_chain_as_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c6",
        source_text="甲。乙。丙。",
        target_text="甲。乙。",
    )

    assert _finding_types(findings) == []


def test_audit_does_not_flag_english_source_to_compact_cjk_target_as_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c6b",
        source_text="Alpha. Beta. Gamma.",
        target_text="甲。乙。丙。",
    )

    assert _finding_types(findings) == []


def test_audit_does_not_flag_hard_wrapped_paragraph_as_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c7",
        source_text=(
            "This paragraph is intentionally wrapped across lines\n"
            "to mimic source extraction wrapping while keeping\n"
            "the same semantic sentence and meaning."
        ),
        target_text=(
            "This paragraph is intentionally wrapped across lines to mimic source extraction "
            "wrapping while keeping the same semantic sentence and meaning."
        ),
    )

    assert _finding_types(findings) == []


def test_audit_does_not_misclassify_partially_preserved_block_list_as_collapsed() -> None:
    findings = audit_source_against_target(
        chapter_id="c8",
        source_text="1. One.\n2. Two.\n3. Three.\n4. Four.\n5. Five.",
        target_text="1. 一\n2. 二\n3. 三",
    )

    assert _finding_types(findings) == ["possible_omission"]
