from __future__ import annotations

from book_translator.models import PublishingAuditFinding
from book_translator.publishing.source_audit import audit_source_against_target


def _finding_types(findings: list[PublishingAuditFinding]) -> list[str]:
    return [item.finding_type for item in findings]


def test_audit_detects_collapsed_numbered_list() -> None:
    findings = audit_source_against_target(
        chapter_id="c1",
        source_text="1. First idea.\n2. Second idea.\n3. Third idea.",
        target_text="1. First idea. 2. Second idea. 3. Third idea.",
    )

    assert _finding_types(findings) == ["collapsed_numbered_list"]
    finding = findings[0]
    assert finding.block_id is None
    assert finding.severity == "high"
    assert finding.confidence == 0.95
    assert finding.agent_role == "audit"
    assert finding.auto_fixable is True
    assert finding.source_signature == "collapsed_numbered_list:1-2-3"


def test_audit_detects_possible_omission_candidates() -> None:
    findings = audit_source_against_target(
        chapter_id="c2",
        source_text="Alpha.\nBeta.\nGamma.",
        target_text="Alpha.\nBeta.",
    )

    assert _finding_types(findings) == ["possible_omission"]
    assert findings[0].source_signature == "possible_omission:2:beta-gamma"


def test_audit_detects_callout_candidates() -> None:
    findings = audit_source_against_target(
        chapter_id="c3",
        source_text='Remember this:\n"Focus compounds over decades."',
        target_text="Remember this point because focus compounds over decades.",
    )

    assert _finding_types(findings) == ["callout_candidate"]
    assert findings[0].source_signature == "callout_candidate:focus-compounds-over-decades"


def test_audit_detects_question_answer_structure_issues() -> None:
    findings = audit_source_against_target(
        chapter_id="c4",
        source_text="Q: What matters most?\nA: Build useful things.",
        target_text="What matters most?\nBuild useful things.",
    )

    assert _finding_types(findings) == ["question_answer_structure"]
    assert findings[0].source_signature == "question_answer_structure:q1:a1"


def test_audit_keeps_heuristics_conservative_for_plain_paragraphs() -> None:
    findings = audit_source_against_target(
        chapter_id="c5",
        source_text="This is a plain narrative paragraph with no strong structural cues.",
        target_text="This is a plain narrative paragraph with no strong structural cues.",
    )

    assert _finding_types(findings) == []


def test_audit_does_not_flag_short_cjk_sentence_chain_as_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c6",
        source_text="\u7532\u3002\u4e59\u3002\u4e19\u3002",
        target_text="\u7532\u3002\u4e59\u3002",
    )

    assert _finding_types(findings) == []


def test_audit_does_not_flag_english_source_to_compact_cjk_target_as_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c6b",
        source_text="Alpha. Beta. Gamma.",
        target_text="\u7532\u3002\u4e59\u3002\u4e19\u3002",
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
        target_text="1. One.\n2. Two.\n3. Three.",
    )

    assert _finding_types(findings) == ["possible_omission"]
    assert findings[0].source_signature == "possible_omission:2:4-four-5-five"


def test_audit_populates_richer_finding_shape_for_non_autofixable_results() -> None:
    findings = audit_source_against_target(
        chapter_id="c9",
        source_text="Q: What matters most?\nA: Build useful things.",
        target_text="Only the answer remains.",
    )

    assert _finding_types(findings) == ["question_answer_structure"]
    finding = findings[0]
    assert finding.block_id is None
    assert finding.confidence == 0.7
    assert finding.agent_role == "audit"
    assert finding.auto_fixable is False
    assert finding.source_signature == "question_answer_structure:q1:a1"
