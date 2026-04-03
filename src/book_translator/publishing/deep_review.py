from __future__ import annotations

from dataclasses import dataclass

from book_translator.models import Chapter, PublishingAuditFinding, PublishingChapterArtifact
from book_translator.publishing.editorial_revision import apply_editorial_repairs
from book_translator.publishing.layout_review import generate_layout_annotations
from book_translator.publishing.source_audit import audit_source_against_target

DEEP_REVIEW_STAGE_VERSION = "1"


@dataclass(slots=True)
class DeepReviewResult:
    findings: list[PublishingAuditFinding]
    revised_chapters: list[PublishingChapterArtifact]
    decisions: dict[str, object]
    revised_chapter_count: int


def run_deep_review(
    *,
    source_chapters: list[Chapter],
    final_artifacts: list[PublishingChapterArtifact],
) -> DeepReviewResult:
    source_by_chapter_id = {chapter.chapter_id: chapter for chapter in source_chapters}
    source_by_index = {chapter.chapter_index: chapter for chapter in source_chapters}

    findings: list[PublishingAuditFinding] = []
    revised_chapters: list[PublishingChapterArtifact] = []
    chapter_decisions: list[dict[str, object]] = []
    revised_count = 0
    annotation_count = 0

    for artifact in sorted(final_artifacts, key=lambda item: item.chapter_index):
        source_chapter = source_by_chapter_id.get(artifact.chapter_id) or source_by_index.get(
            artifact.chapter_index
        )
        if source_chapter is None:
            revised_chapters.append(artifact)
            chapter_decisions.append(
                {
                    "chapter_id": artifact.chapter_id,
                    "chapter_index": artifact.chapter_index,
                    "finding_count": 0,
                    "revised": False,
                    "annotations": [],
                    "status": "missing_source_chapter",
                }
            )
            continue

        chapter_findings = audit_source_against_target(
            chapter_id=artifact.chapter_id,
            source_text=source_chapter.text,
            target_text=artifact.text,
        )
        findings.extend(chapter_findings)

        revised_text = apply_editorial_repairs(
            chapter_text=artifact.text,
            source_text=source_chapter.text,
            findings=chapter_findings,
        )
        annotations = generate_layout_annotations(
            source_text=source_chapter.text,
            chapter_text=revised_text,
            findings=chapter_findings,
        )
        if revised_text != artifact.text:
            revised_count += 1
        annotation_count += len(annotations)

        revised_chapters.append(artifact.model_copy(update={"text": revised_text}))
        chapter_decisions.append(
            {
                "chapter_id": artifact.chapter_id,
                "chapter_index": artifact.chapter_index,
                "finding_count": len(chapter_findings),
                "revised": revised_text != artifact.text,
                "annotations": [annotation.model_dump() for annotation in annotations],
                "status": "reviewed",
            }
        )

    decisions = {
        "finding_count": len(findings),
        "revised_chapter_count": revised_count,
        "annotation_count": annotation_count,
        "chapters": chapter_decisions,
    }
    return DeepReviewResult(
        findings=findings,
        revised_chapters=revised_chapters,
        decisions=decisions,
        revised_chapter_count=revised_count,
    )
