from __future__ import annotations

import pytest

from booksmith.models import PublishingAuditFinding
from booksmith.publishing.consensus import (
    arbiter_fix_candidates,
    build_arbitration_queue,
    finding_consensus_key,
    merge_consensus_findings,
)


def _finding(
    *,
    chapter_id: str = "c1",
    finding_type: str = "structure_issue",
    block_id: str | None = None,
    source_signature: str | None = None,
    severity: str = "medium",
    source_excerpt: str = "source excerpt",
    target_excerpt: str = "target excerpt",
    reason: str = "reason",
    auto_fixable: bool = False,
    confidence: float = 0.9,
    agent_role: str = "audit",
) -> PublishingAuditFinding:
    return PublishingAuditFinding(
        chapter_id=chapter_id,
        block_id=block_id,
        source_signature=source_signature,
        finding_type=finding_type,
        severity=severity,
        source_excerpt=source_excerpt,
        target_excerpt=target_excerpt,
        reason=reason,
        auto_fixable=auto_fixable,
        confidence=confidence,
        agent_role=agent_role,
    )


def test_merge_consensus_groups_agreed_disputed_and_low_confidence_findings() -> None:
    audit_findings = [
        _finding(
            finding_type="ordered_list",
            block_id="b-1",
            source_signature="ordered_list:1-2-3",
            severity="high",
            auto_fixable=True,
            confidence=0.95,
        ),
        _finding(
            finding_type="possible_omission",
            block_id="b-2",
            source_signature="possible_omission:1:missing-unit",
            confidence=0.86,
        ),
        _finding(
            finding_type="quote_format",
            block_id="b-3",
            source_signature="quote_format:source-quote",
            confidence=0.55,
        ),
    ]
    review_findings = [
        _finding(
            finding_type="ordered_list",
            block_id="b-1",
            source_signature="ordered_list:1-2-3",
            severity="high",
            auto_fixable=True,
            confidence=0.91,
            agent_role="review",
        ),
        _finding(
            finding_type="possible_omission",
            block_id="b-2",
            source_signature="possible_omission:1:missing-unit",
            severity="low",
            confidence=0.87,
            agent_role="review",
        ),
    ]

    result = merge_consensus_findings(
        audit_findings=audit_findings,
        review_findings=review_findings,
    )

    assert [item.finding_key for item in result.agreed] == [
        finding_consensus_key(audit_findings[0])
    ]
    assert [item.finding_key for item in result.disputed] == [
        finding_consensus_key(audit_findings[1])
    ]
    assert [item.finding_key for item in result.low_confidence] == [
        finding_consensus_key(audit_findings[2])
    ]


def test_build_arbitration_queue_returns_disputed_items_in_deterministic_order() -> None:
    result = merge_consensus_findings(
        audit_findings=[
            _finding(
                chapter_id="c2",
                finding_type="beta_issue",
                block_id="b-2",
                source_signature="beta",
                confidence=0.9,
            ),
            _finding(
                chapter_id="c1",
                finding_type="alpha_issue",
                block_id="b-1",
                source_signature="alpha",
                confidence=0.9,
            ),
        ],
        review_findings=[
            _finding(
                chapter_id="c2",
                finding_type="beta_issue",
                block_id="b-2",
                source_signature="beta",
                severity="high",
                confidence=0.9,
                agent_role="review",
            ),
            _finding(
                chapter_id="c1",
                finding_type="alpha_issue",
                block_id="b-1",
                source_signature="alpha",
                severity="low",
                confidence=0.9,
                agent_role="review",
            ),
        ],
    )

    queue = build_arbitration_queue(result.disputed)

    assert [item.finding_key for item in queue] == [
        finding_consensus_key(result.disputed[0].audit_finding),
        finding_consensus_key(result.disputed[1].audit_finding),
    ]


def test_arbiter_fix_candidates_include_agreed_and_arbiter_autofixable_findings() -> None:
    consensus = merge_consensus_findings(
        audit_findings=[
            _finding(
                chapter_id="c1",
                finding_type="ordered_list",
                block_id="b-1",
                source_signature="ordered_list:1-2-3",
                severity="high",
                auto_fixable=True,
                confidence=0.95,
            ),
            _finding(
                chapter_id="c1",
                finding_type="possible_omission",
                block_id="b-2",
                source_signature="possible_omission:1:missing-unit",
                auto_fixable=False,
                confidence=0.9,
            ),
        ],
        review_findings=[
            _finding(
                chapter_id="c1",
                finding_type="ordered_list",
                block_id="b-1",
                source_signature="ordered_list:1-2-3",
                severity="high",
                auto_fixable=True,
                confidence=0.92,
                agent_role="review",
            ),
            _finding(
                chapter_id="c1",
                finding_type="possible_omission",
                block_id="b-2",
                source_signature="possible_omission:1:missing-unit",
                severity="low",
                auto_fixable=False,
                confidence=0.93,
                agent_role="review",
            ),
        ],
    )
    arbiter_findings = [
        _finding(
            chapter_id="c1",
            finding_type="possible_omission",
            block_id="b-2",
            source_signature="possible_omission:1:missing-unit",
            severity="medium",
            auto_fixable=True,
            confidence=0.96,
            agent_role="arbiter",
        ),
        _finding(
            chapter_id="c1",
            finding_type="quote_format",
            block_id="b-3",
            source_signature="quote_format:source-quote",
            severity="medium",
            auto_fixable=False,
            confidence=0.97,
            agent_role="arbiter",
        ),
    ]

    candidates = arbiter_fix_candidates(
        consensus=consensus,
        arbiter_findings=arbiter_findings,
    )

    assert [(item.finding_type, item.block_id) for item in candidates] == [
        ("ordered_list", "b-1"),
        ("possible_omission", "b-2"),
    ]


def test_merge_consensus_preserves_same_type_findings_with_distinct_excerpts() -> None:
    audit_findings = [
        _finding(
            chapter_id="c7",
            finding_type="possible_omission",
            block_id="b-9",
            source_signature="possible_omission:1:sentence-a",
            source_excerpt="Missing sentence A.",
            target_excerpt="Target for A.",
            reason="Reason A",
            confidence=0.9,
        ),
        _finding(
            chapter_id="c7",
            finding_type="possible_omission",
            block_id="b-9",
            source_signature="possible_omission:1:sentence-b",
            source_excerpt="Missing sentence B.",
            target_excerpt="Target for B.",
            reason="Reason B",
            confidence=0.88,
        ),
    ]
    review_findings = [
        _finding(
            chapter_id="c7",
            finding_type="possible_omission",
            block_id="b-9",
            source_signature="possible_omission:1:sentence-a",
            source_excerpt="Missing sentence A.",
            target_excerpt="Target for A.",
            reason="Reason A",
            confidence=0.91,
            agent_role="review",
        ),
        _finding(
            chapter_id="c7",
            finding_type="possible_omission",
            block_id="b-9",
            source_signature="possible_omission:1:sentence-b",
            source_excerpt="Missing sentence B.",
            target_excerpt="Target for B.",
            reason="Reason B",
            confidence=0.92,
            agent_role="review",
        ),
    ]

    result = merge_consensus_findings(
        audit_findings=audit_findings,
        review_findings=review_findings,
    )

    assert len(result.agreed) == 2
    assert result.disputed == []
    assert result.low_confidence == []
    assert sorted(item.finding_key for item in result.agreed) == sorted([
        finding_consensus_key(audit_findings[0]),
        finding_consensus_key(audit_findings[1]),
    ])
    assert sorted(item.audit_finding.source_excerpt for item in result.agreed) == [
        "Missing sentence A.",
        "Missing sentence B.",
    ]


def test_merge_consensus_raises_for_duplicate_keys_from_same_role() -> None:
    duplicate_audit_findings = [
        _finding(
            chapter_id="c8",
            finding_type="possible_omission",
            block_id="b-4",
            source_signature="possible_omission:1:shared-source",
            source_excerpt="Same source excerpt.",
            target_excerpt="Target one.",
            reason="Reason one.",
            confidence=0.9,
        ),
        _finding(
            chapter_id="c8",
            finding_type="possible_omission",
            block_id="b-4",
            source_signature="possible_omission:1:shared-source",
            source_excerpt="Same source excerpt.",
            target_excerpt="Target two.",
            reason="Reason two.",
            confidence=0.91,
        ),
    ]

    with pytest.raises(ValueError, match="Duplicate audit finding for consensus key"):
        merge_consensus_findings(
            audit_findings=duplicate_audit_findings,
            review_findings=[],
        )


def test_merge_consensus_agrees_when_only_prose_fields_differ() -> None:
    audit_finding = _finding(
        chapter_id="c9",
        finding_type="possible_omission",
        block_id="b-7",
        source_signature="possible_omission:1:missing-sentence",
        severity="medium",
        source_excerpt="Missing sentence.",
        target_excerpt="Audit target prose.",
        reason="Audit prose explanation.",
        auto_fixable=False,
        confidence=0.9,
    )
    review_finding = _finding(
        chapter_id="c9",
        finding_type="possible_omission",
        block_id="b-7",
        source_signature="possible_omission:1:missing-sentence",
        severity="medium",
        source_excerpt="Missing sentence.",
        target_excerpt="Review target prose is phrased differently.",
        reason="Review explanation uses different wording.",
        auto_fixable=False,
        confidence=0.92,
        agent_role="review",
    )

    result = merge_consensus_findings(
        audit_findings=[audit_finding],
        review_findings=[review_finding],
    )

    assert [item.finding_key for item in result.agreed] == [
        finding_consensus_key(audit_finding)
    ]
    assert result.disputed == []
    assert result.low_confidence == []


def test_merge_consensus_agrees_when_excerpts_differ_but_source_signature_matches() -> None:
    audit_finding = _finding(
        chapter_id="c10",
        finding_type="callout_candidate",
        block_id="b-10",
        source_signature="callout_candidate:key-point-line",
        source_excerpt="Important quoted line from source.",
        target_excerpt="Audit target prose.",
        reason="Audit explanation.",
        auto_fixable=True,
        confidence=0.9,
    )
    review_finding = _finding(
        chapter_id="c10",
        finding_type="callout_candidate",
        block_id="b-10",
        source_signature="callout_candidate:key-point-line",
        source_excerpt="Same source line paraphrased by review agent.",
        target_excerpt="Review target prose differs.",
        reason="Review explanation differs too.",
        auto_fixable=True,
        confidence=0.91,
        agent_role="review",
    )

    result = merge_consensus_findings(
        audit_findings=[audit_finding],
        review_findings=[review_finding],
    )

    assert [item.finding_key for item in result.agreed] == [
        finding_consensus_key(audit_finding)
    ]
    assert result.disputed == []
    assert result.low_confidence == []
