from __future__ import annotations

from dataclasses import dataclass

from book_translator.models import (
    Chapter,
    PublishingAuditFinding,
    PublishingBlock,
    PublishingChapterArtifact,
    StructuredPublishingBook,
    StructuredPublishingChapter,
)
from book_translator.output.assembler import (
    assemble_structured_chapter_text,
)
from book_translator.publishing.consensus import (
    PublishingFindingConsensusResult,
    arbiter_fix_candidates,
    build_arbitration_queue,
    merge_consensus_findings,
)
from book_translator.publishing.editorial_revision import (
    apply_editorial_repairs,
    apply_structured_editorial_repairs,
)
from book_translator.publishing.layout_review import generate_layout_annotations
from book_translator.publishing.source_audit import audit_source_against_target
from book_translator.publishing.structure import build_structured_book

DEEP_REVIEW_STAGE_VERSION = "2"


@dataclass(slots=True)
class DeepReviewResult:
    findings: list[PublishingAuditFinding]
    review_findings: list[PublishingAuditFinding]
    arbiter_findings: list[PublishingAuditFinding]
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
            structured_chapter = _build_passthrough_structured_chapter(artifact)
            structured_chapters.append(structured_chapter)
            final_text = assemble_structured_chapter_text(structured_chapter)
            revised_artifact = artifact.model_copy(update={"text": final_text})
            revised_chapters.append(revised_artifact)
            chapter_decisions.append(
                {
                    "chapter_id": artifact.chapter_id,
                    "chapter_index": artifact.chapter_index,
                    "source_finding_count": 0,
                    "review_finding_count": 0,
                    "disputed_count": 0,
                    "confirmation_finding_count": 1,
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
        )
        source_findings.extend(chapter_source_findings)

        source_repaired_text = apply_editorial_repairs(
            chapter_text=artifact.text,
            source_text=source_chapter.text,
            findings=chapter_source_findings,
        )
        structured_chapter = apply_structured_editorial_repairs(
            chapter=artifact.model_copy(update={"text": source_repaired_text}),
            source_text=source_chapter.text,
            findings=chapter_source_findings,
        )
        structured_chapter_body = assemble_structured_chapter_text(structured_chapter)

        if use_consensus_review:
            chapter_review_findings = audit_source_against_target(
                chapter_id=artifact.chapter_id,
                source_text=source_chapter.text,
                target_text=structured_chapter_body,
            )
        else:
            chapter_review_findings = []
        review_findings.extend(chapter_review_findings)

        if use_consensus_review:
            consensus = merge_consensus_findings(
                audit_findings=chapter_source_findings,
                review_findings=chapter_review_findings,
            )
            chapter_arbiter_findings = _resolve_arbitration_findings(consensus)
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
        final_text = structured_chapter_body
        if repair_candidates:
            repaired_text = apply_editorial_repairs(
                chapter_text=structured_chapter_body,
                source_text=source_chapter.text,
                findings=repair_candidates,
            )
            if repaired_text != structured_chapter_body:
                final_text = repaired_text
                structured_chapter = apply_structured_editorial_repairs(
                    chapter=artifact.model_copy(update={"text": final_text}),
                    source_text=source_chapter.text,
                    findings=repair_candidates,
                )
                final_text = assemble_structured_chapter_text(structured_chapter)

        chapter_confirmation_findings = audit_source_against_target(
            chapter_id=artifact.chapter_id,
            source_text=source_chapter.text,
            target_text=final_text,
        )
        confirmation_findings.extend(chapter_confirmation_findings)

        chapter_was_revised = final_text != artifact.text
        if chapter_was_revised:
            revised_count += 1

        annotations = generate_layout_annotations(
            source_text=source_chapter.text,
            chapter_text=final_text,
            findings=repair_candidates or chapter_source_findings,
        )
        annotation_count += len(annotations)

        structured_chapters.append(structured_chapter)
        revised_chapters.append(artifact.model_copy(update={"text": final_text}))
        chapter_decisions.append(
            {
                "chapter_id": artifact.chapter_id,
                "chapter_index": artifact.chapter_index,
                "source_finding_count": len(chapter_source_findings),
                "review_finding_count": len(chapter_review_findings),
                "disputed_count": len(consensus.disputed),
                "confirmation_finding_count": len(chapter_confirmation_findings),
                "revised": chapter_was_revised,
                "annotations": [annotation.model_dump() for annotation in annotations],
                "status": "reviewed",
            }
        )

    if use_consensus_review:
        consensus = merge_consensus_findings(
            audit_findings=source_findings,
            review_findings=review_findings,
        )
        arbiter_findings = _resolve_arbitration_findings(consensus)
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
        "unresolved_count": len(confirmation_findings) + missing_source_count,
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
        "final_report": final_report,
        "chapters": chapter_decisions,
    }
    return DeepReviewResult(
        findings=source_findings,
        review_findings=review_findings,
        arbiter_findings=arbiter_findings,
        revised_chapters=revised_chapters,
        structured_book=structured_book,
        consensus=consensus,
        decisions=decisions,
        final_report=final_report,
        revised_chapter_count=revised_count,
        repair_passes=1,
        confirmation_passes=1,
    )


def _resolve_arbitration_findings(
    consensus: PublishingFindingConsensusResult,
) -> list[PublishingAuditFinding]:
    findings: list[PublishingAuditFinding] = []
    for item in build_arbitration_queue(consensus.disputed):
        preferred = _arbiter_decide(item)
        if preferred is None or not preferred.auto_fixable:
            continue
        findings.append(preferred.model_copy(update={"agent_role": "arbiter"}))
    return findings


def _arbiter_decide(item: object) -> PublishingAuditFinding | None:
    audit_finding = getattr(item, "audit_finding", None)
    review_finding = getattr(item, "review_finding", None)
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
        if review_finding.auto_fixable and review_finding.confidence >= audit_finding.confidence:
            return review_finding
        return audit_finding
    return None


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
