from __future__ import annotations

from book_translator.models import PublishingGateInputs


def compute_quality_score(inputs: PublishingGateInputs) -> dict[str, float]:
    overall = round(
        (
            inputs.fidelity_score * 0.28
            + inputs.structure_score * 0.2
            + inputs.terminology_score * 0.14
            + inputs.layout_score * 0.16
            + inputs.source_style_alignment_score * 0.12
            + inputs.epub_integrity_score * 0.1
        ),
        3,
    )
    return {
        "fidelity_score": inputs.fidelity_score,
        "structure_score": inputs.structure_score,
        "terminology_score": inputs.terminology_score,
        "layout_score": inputs.layout_score,
        "source_style_alignment_score": inputs.source_style_alignment_score,
        "epub_integrity_score": inputs.epub_integrity_score,
        "overall": overall,
    }


def evaluate_release_gate(inputs: PublishingGateInputs) -> dict[str, object]:
    quality_score = compute_quality_score(inputs)
    hard_gate_passed = all(
        [
            inputs.unresolved_count == 0,
            inputs.high_severity_count == 0,
            inputs.structural_issue_count == 0,
            inputs.citation_issue_count == 0,
            inputs.image_or_caption_issue_count == 0,
            inputs.visual_blocker_count == 0,
            inputs.primary_output_validation_passed,
            inputs.cross_output_validation_passed,
        ]
    )
    passed = hard_gate_passed and quality_score["overall"] >= 9.0
    return {
        "release_status": "passed" if passed else "failed",
        "hard_gate_passed": hard_gate_passed,
        "promotion_performed": passed,
        "quality_score": quality_score,
    }
