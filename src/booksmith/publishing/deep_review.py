from __future__ import annotations

from dataclasses import dataclass

from booksmith.models import (
    Chapter,
    PublishingAuditFinding,
    PublishingBlock,
    PublishingChapterArtifact,
    StructuredPublishingBook,
    StructuredPublishingChapter,
)
from booksmith.output.assembler import (
    assemble_structured_chapter_text,
)
from booksmith.publishing.consensus import (
    PublishingFindingConsensusResult,
    arbiter_fix_candidates,
    build_arbitration_queue,
    finding_consensus_key,
    merge_consensus_findings,
)
from booksmith.publishing.editorial_revision import (
    apply_structured_editorial_repairs,
)
from booksmith.publishing.layout_review import generate_layout_annotations
from booksmith.publishing.source_audit import audit_source_against_target
from booksmith.publishing.structure import build_structured_book, build_structured_chapter

DEEP_REVIEW_STAGE_VERSION = "3"


@dataclass(slots=True)
class DeepReviewResult:
    findings: list[PublishingAuditFinding]
    review_findings: list[PublishingAuditFinding]
    arbiter_findings: list[PublishingAuditFinding]
    release_blocking_findings: list[PublishingAuditFinding]
    revised_chapters: list[PublishingChapterArtifact]
    structured_book: StructuredPublishingBook
    consensus: PublishingFindingConsensusResult
    decisions: dict[str, object]
    final_report: dict[str, object]
    revised_chapter_count: int
    repair_passes: int
    confirmation_passes: int


def run_deep_review(
    *,
    source_chapters: list[Chapter],
    final_artifacts: list[PublishingChapterArtifact],
    enable_cross_review: bool = True,
    audit_depth: str = "consensus",
) -> DeepReviewResult:
    source_by_chapter_id = {chapter.chapter_id: chapter for chapter in source_chapters}
    source_by_index = {chapter.chapter_index: chapter for chapter in source_chapters}

    source_findings: list[PublishingAuditFinding] = []
    review_findings: list[PublishingAuditFinding] = []
    arbiter_findings: list[PublishingAuditFinding] = []
    revised_chapters: list[PublishingChapterArtifact] = []
    structured_chapters: list[StructuredPublishingChapter] = []
    chapter_decisions: list[dict[str, object]] = []
    annotation_count = 0
    revised_count = 0
    confirmation_findings: list[PublishingAuditFinding] = []
    release_blocking_findings: list[PublishingAuditFinding] = []
    use_consensus_review = audit_depth == "consensus" and enable_cross_review

    for artifact in sorted(final_artifacts, key=lambda item: item.chapter_index):
        source_chapter = source_by_chapter_id.get(artifact.chapter_id) or source_by_index.get(
            artifact.chapter_index
        )
        if source_chapter is None:
            missing_source_finding = PublishingAuditFinding(
                chapter_id=artifact.chapter_id,
                finding_type="missing_source_chapter",
                severity="high",
                source_excerpt="",
                target_excerpt=artifact.text[:180],
                reason="Source chapter could not be matched during deep review.",
                auto_fixable=False,
                agent_role="audit",
            )
            source_findings.append(missing_source_finding)
            release_blocking_findings.append(missing_source_finding)
            structured_chapter = _build_passthrough_structured_chapter(artifact)
            structured_chapters.append(structured_chapter)
            final_text = assemble_structured_chapter_text(structured_chapter)
            revised_artifact = artifact.model_copy(update={"text": final_text})
            revised_chapters.append(revised_artifact)
            chapter_decisions.append(
                {
                    "chapter_id": artifact.chapter_id,
                    "chapter_index": artifact.chapter_index,
                    "source_anchor": artifact.chapter_id,
                    "audit_finding_count": 1,
                    "source_finding_count": 1,
                    "review_finding_count": 0,
                    "agreed_count": 0,
                    "disputed_count": 0,
                    "repaired_count": 0,
                    "confirmation_finding_count": 1,
                    "unresolved_count": 1,
                    "rollback_level_required": "book_retranslate",
                    "revised": False,
                    "annotations": [],
                    "status": "missing_source_chapter",
                }
            )
            continue

        chapter_source_findings = audit_source_against_target(
            chapter_id=artifact.chapter_id,
            source_text=source_chapter.text,
            target_text=artifact.text,
            source_title=source_chapter.title,
        )
        source_findings.extend(chapter_source_findings)

        structured_chapter = build_structured_chapter(
            artifact=artifact,
            source_text=source_chapter.text,
            source_assets=[],
            source_title=source_chapter.title,
        )
        structured_chapter_body = assemble_structured_chapter_text(structured_chapter)

        if use_consensus_review:
            chapter_review_findings = audit_source_against_target(
                chapter_id=artifact.chapter_id,
                source_text=source_chapter.text,
                target_text=structured_chapter_body,
                source_title=source_chapter.title,
            )
        else:
            chapter_review_findings = []
        review_findings.extend(chapter_review_findings)

        if use_consensus_review:
            consensus = merge_consensus_findings(
                audit_findings=chapter_source_findings,
                review_findings=chapter_review_findings,
            )
            chapter_arbiter_findings = _run_arbiter_review(
                chapter_id=artifact.chapter_id,
                source_text=source_chapter.text,
                target_text=structured_chapter_body,
                source_title=source_chapter.title,
                consensus=consensus,
            )
            arbiter_findings.extend(chapter_arbiter_findings)
            repair_candidates = arbiter_fix_candidates(
                consensus=consensus,
                arbiter_findings=chapter_arbiter_findings,
            )
        else:
            consensus = PublishingFindingConsensusResult()
            chapter_arbiter_findings = []
            repair_candidates = [
                finding
                for finding in chapter_source_findings
                if finding.auto_fixable
            ]
        structured_chapter = apply_structured_editorial_repairs(
            chapter=structured_chapter,
            findings=repair_candidates,
        )
        final_text = assemble_structured_chapter_text(structured_chapter)

        chapter_confirmation_findings = audit_source_against_target(
            chapter_id=artifact.chapter_id,
            source_text=source_chapter.text,
            target_text=final_text,
            source_title=source_chapter.title,
        )
        confirmation_findings.extend(chapter_confirmation_findings)
        release_blocking_findings.extend(chapter_confirmation_findings)

        chapter_was_revised = final_text != artifact.text
        if chapter_was_revised:
            revised_count += 1

        annotations = generate_layout_annotations(
            source_text=source_chapter.text,
            chapter_text=final_text,
            findings=repair_candidates or chapter_source_findings,
        )
        annotation_count += len(annotations)
        chapter_unresolved_count = len(chapter_confirmation_findings)
        rollback_level_required = _classify_rollback_level(
            unresolved_count=chapter_unresolved_count,
            findings=chapter_confirmation_findings,
        )

        structured_chapters.append(structured_chapter)
        revised_chapters.append(artifact.model_copy(update={"text": final_text}))
        chapter_decisions.append(
            {
                "chapter_id": artifact.chapter_id,
                "chapter_index": artifact.chapter_index,
                "source_anchor": source_chapter.chapter_id,
                "audit_finding_count": len(chapter_source_findings),
                "source_finding_count": len(chapter_source_findings),
                "review_finding_count": len(chapter_review_findings),
                "agreed_count": len(consensus.agreed),
                "disputed_count": len(consensus.disputed),
                "repaired_count": len(repair_candidates),
                "confirmation_finding_count": chapter_unresolved_count,
                "unresolved_count": chapter_unresolved_count,
                "rollback_level_required": rollback_level_required,
                "revised": chapter_was_revised,
                "annotations": [annotation.model_dump() for annotation in annotations],
                "status": "reviewed" if chapter_unresolved_count == 0 else "rollback_required",
            }
        )

    if use_consensus_review:
        consensus = merge_consensus_findings(
            audit_findings=source_findings,
            review_findings=review_findings,
        )
    else:
        consensus = PublishingFindingConsensusResult()
        review_findings = []
        arbiter_findings = []

    structured_book = build_structured_book(title="", chapters=structured_chapters)
    missing_source_count = sum(
        1
        for finding in source_findings
        if finding.finding_type == "missing_source_chapter"
    )
    high_severity_count = sum(
        1 for finding in release_blocking_findings if finding.severity == "high"
    )
    structural_issue_count = sum(
        1 for finding in release_blocking_findings if _is_structural_finding(finding)
    )
    citation_issue_count = sum(
        1 for finding in release_blocking_findings if _is_citation_finding(finding)
    )
    image_or_caption_issue_count = sum(
        1
        for finding in release_blocking_findings
        if _is_image_or_caption_finding(finding)
    )
    final_report = {
        "stage": "deep-review",
        "stage_version": DEEP_REVIEW_STAGE_VERSION,
        "audit_depth": audit_depth,
        "cross_review_enabled": use_consensus_review,
        "source_finding_count": len(source_findings),
        "review_finding_count": len(review_findings),
        "arbiter_finding_count": len(arbiter_findings),
        "agreed_count": len(consensus.agreed),
        "disputed_count": len(consensus.disputed),
        "low_confidence_count": len(consensus.low_confidence),
        "repair_passes": 1,
        "confirmation_passes": 1,
        "confirmation_finding_count": len(confirmation_findings),
        "unresolved_count": len(release_blocking_findings),
        "missing_source_count": missing_source_count,
        "high_severity_count": high_severity_count,
        "structural_issue_count": structural_issue_count,
        "citation_issue_count": citation_issue_count,
        "image_or_caption_issue_count": image_or_caption_issue_count,
        "revised_chapter_count": revised_count,
        "annotation_count": annotation_count,
    }

    decisions = {
        "finding_count": len(source_findings),
        "revised_chapter_count": revised_count,
        "annotation_count": annotation_count,
        "consensus": {
            "agreed_count": len(consensus.agreed),
            "disputed_count": len(consensus.disputed),
            "low_confidence_count": len(consensus.low_confidence),
        },
        "confirmation_finding_count": len(confirmation_findings),
        "release_blocking_finding_count": len(release_blocking_findings),
        "final_report": final_report,
        "chapters": chapter_decisions,
    }
    return DeepReviewResult(
        findings=source_findings,
        review_findings=review_findings,
        arbiter_findings=arbiter_findings,
        release_blocking_findings=release_blocking_findings,
        revised_chapters=revised_chapters,
        structured_book=structured_book,
        consensus=consensus,
        decisions=decisions,
        final_report=final_report,
        revised_chapter_count=revised_count,
        repair_passes=1,
        confirmation_passes=1,
    )


def _run_arbiter_review(
    *,
    chapter_id: str,
    source_text: str,
    target_text: str,
    source_title: str | None,
    consensus: PublishingFindingConsensusResult,
) -> list[PublishingAuditFinding]:
    disputed_items = build_arbitration_queue(consensus.disputed)
    if not disputed_items:
        return []

    arbiter_candidates = audit_source_against_target(
        chapter_id=chapter_id,
        source_text=source_text,
        target_text=target_text,
        source_title=source_title,
    )
    findings: list[PublishingAuditFinding] = []
    for candidate in arbiter_candidates:
        preferred = _arbiter_decide(candidate, consensus=consensus)
        if preferred is None or not preferred.auto_fixable:
            continue
        findings.append(preferred.model_copy(update={"agent_role": "arbiter"}))
    resolved_keys = {finding_consensus_key(finding) for finding in findings}
    for item in disputed_items:
        if item.finding_key in resolved_keys:
            continue
        fallback = _arbiter_fallback_decision(item)
        if fallback is None or not fallback.auto_fixable:
            continue
        findings.append(fallback.model_copy(update={"agent_role": "arbiter"}))
    return findings


def _arbiter_decide(
    candidate: PublishingAuditFinding,
    *,
    consensus: PublishingFindingConsensusResult,
) -> PublishingAuditFinding | None:
    for item in consensus.disputed:
        if item.finding_key != finding_consensus_key(candidate):
            continue
        audit_finding = item.audit_finding
        review_finding = item.review_finding
        if audit_finding is None and review_finding is None:
            return None
        if audit_finding is None:
            return review_finding
        if review_finding is None:
            return audit_finding

        if (
            audit_finding.finding_type == review_finding.finding_type
            and audit_finding.chapter_id == review_finding.chapter_id
            and audit_finding.block_id == review_finding.block_id
            and audit_finding.source_signature == review_finding.source_signature
        ):
            if (
                review_finding.auto_fixable
                and review_finding.confidence >= audit_finding.confidence
            ):
                return review_finding
            return audit_finding
        return None
    return None


def _arbiter_fallback_decision(item: object) -> PublishingAuditFinding | None:
    review_finding = getattr(item, "review_finding", None)
    audit_finding = getattr(item, "audit_finding", None)
    if review_finding is not None and review_finding.auto_fixable:
        return review_finding
    if audit_finding is not None and audit_finding.auto_fixable:
        return audit_finding
    return None


def _classify_rollback_level(
    *,
    unresolved_count: int,
    findings: list[PublishingAuditFinding],
) -> str:
    if unresolved_count == 0:
        return "none"
    if any(
        finding.finding_type in {"possible_omission", "missing_caption", "missing_image"}
        for finding in findings
    ):
        return "chapter_redraft" if unresolved_count <= 8 else "chapter_retranslate"
    if any(finding.severity == "high" and not finding.auto_fixable for finding in findings):
        return "chapter_redraft" if unresolved_count <= 8 else "chapter_retranslate"
    if unresolved_count <= 3:
        return "chapter_repair"
    if unresolved_count <= 8:
        return "chapter_redraft"
    return "chapter_retranslate"


def _is_structural_finding(finding: PublishingAuditFinding) -> bool:
    return finding.finding_type in {
        "list_structure_loss",
        "question_answer_structure",
        "missing_source_chapter",
    } or "structure" in finding.finding_type


def _is_citation_finding(finding: PublishingAuditFinding) -> bool:
    return "citation" in finding.finding_type


def _is_image_or_caption_finding(finding: PublishingAuditFinding) -> bool:
    return finding.finding_type in {"missing_image", "missing_caption", "image_anchor_loss"}


def _build_passthrough_structured_chapter(
    artifact: PublishingChapterArtifact,
) -> StructuredPublishingChapter:
    return StructuredPublishingChapter(
        chapter_id=artifact.chapter_id,
        chapter_index=artifact.chapter_index,
        source_title=artifact.title,
        translated_title=artifact.title,
        blocks=[
            PublishingBlock(
                block_id=f"{artifact.chapter_id}-block-1",
                kind="paragraph",
                text=artifact.text.strip(),
                order_index=1,
            )
        ],
    )
