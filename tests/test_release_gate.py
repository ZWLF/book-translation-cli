from __future__ import annotations

from book_translator.models import PublishingGateInputs
from book_translator.publishing.release_gate import (
    compute_quality_score,
    evaluate_release_gate,
)


def test_release_gate_fails_when_unresolved_findings_remain() -> None:
    inputs = PublishingGateInputs(
        unresolved_count=1,
        high_severity_count=0,
        structural_issue_count=0,
        citation_issue_count=0,
        image_or_caption_issue_count=0,
        visual_blocker_count=0,
        primary_output_validation_passed=True,
        cross_output_validation_passed=True,
        fidelity_score=9.4,
        structure_score=9.2,
        terminology_score=9.1,
        layout_score=9.0,
        source_style_alignment_score=9.0,
        epub_integrity_score=9.0,
    )

    report = evaluate_release_gate(inputs)

    assert report["release_status"] == "failed"
    assert report["promotion_performed"] is False


def test_release_gate_passes_only_when_score_and_gate_both_pass() -> None:
    inputs = PublishingGateInputs(
        unresolved_count=0,
        high_severity_count=0,
        structural_issue_count=0,
        citation_issue_count=0,
        image_or_caption_issue_count=0,
        visual_blocker_count=0,
        primary_output_validation_passed=True,
        cross_output_validation_passed=True,
        fidelity_score=9.3,
        structure_score=9.2,
        terminology_score=9.1,
        layout_score=9.0,
        source_style_alignment_score=9.0,
        epub_integrity_score=9.0,
    )

    report = evaluate_release_gate(inputs)
    quality_score = compute_quality_score(inputs)

    assert report["release_status"] == "passed"
    assert report["hard_gate_passed"] is True
    assert report["promotion_performed"] is True
    assert report["quality_score"]["overall"] >= 9.0
    assert report["quality_score"] == quality_score


def test_release_gate_fails_when_quality_score_is_below_threshold() -> None:
    inputs = PublishingGateInputs(
        unresolved_count=0,
        high_severity_count=0,
        structural_issue_count=0,
        citation_issue_count=0,
        image_or_caption_issue_count=0,
        visual_blocker_count=0,
        primary_output_validation_passed=True,
        cross_output_validation_passed=True,
        fidelity_score=8.9,
        structure_score=8.9,
        terminology_score=8.9,
        layout_score=8.9,
        source_style_alignment_score=8.9,
        epub_integrity_score=8.9,
    )

    report = evaluate_release_gate(inputs)

    assert report["hard_gate_passed"] is True
    assert report["release_status"] == "failed"
    assert report["promotion_performed"] is False
    assert report["quality_score"]["overall"] < 9.0


def test_release_gate_fails_when_primary_output_validation_is_false() -> None:
    inputs = PublishingGateInputs(
        unresolved_count=0,
        high_severity_count=0,
        structural_issue_count=0,
        citation_issue_count=0,
        image_or_caption_issue_count=0,
        visual_blocker_count=0,
        primary_output_validation_passed=False,
        cross_output_validation_passed=True,
        fidelity_score=9.4,
        structure_score=9.2,
        terminology_score=9.1,
        layout_score=9.0,
        source_style_alignment_score=9.0,
        epub_integrity_score=9.0,
    )

    report = evaluate_release_gate(inputs)

    assert report["hard_gate_passed"] is False
    assert report["release_status"] == "failed"
    assert report["promotion_performed"] is False
