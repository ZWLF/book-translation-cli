from pathlib import Path

from book_translator.models import (
    PublishingAuditFinding,
    PublishingChapterArtifact,
    PublishingLayoutAnnotation,
    PublishingStageState,
)
from book_translator.state.workspace import Workspace


def test_publishing_workspace_exposes_artifact_paths(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")

    assert workspace.publishing_root_path == workspace.root / "publishing"
    assert workspace.publishing_state_dir == workspace.publishing_root_path / "state"
    assert workspace.publishing_draft_text_path == (
        workspace.publishing_root_path / "draft" / "draft.txt"
    )
    assert workspace.publishing_final_pdf_path == (
        workspace.publishing_root_path / "final" / "translated.pdf"
    )
    assert workspace.publishing_deep_review_findings_path == (
        workspace.publishing_root_path / "deep_review" / "findings.jsonl"
    )
    assert workspace.publishing_deep_review_chapters_path == (
        workspace.publishing_root_path / "deep_review" / "revised_chapters.jsonl"
    )
    assert workspace.publishing_deep_review_decisions_path == (
        workspace.publishing_root_path / "deep_review" / "decisions.json"
    )

    artifact = PublishingChapterArtifact(
        chapter_id="chapter-1",
        chapter_index=1,
        title="Chapter 1",
        text="Hello world",
    )
    assert artifact.model_dump() == {
        "chapter_id": "chapter-1",
        "chapter_index": 1,
        "title": "Chapter 1",
        "text": "Hello world",
    }

    finding = PublishingAuditFinding(
        chapter_id="chapter-1",
        finding_type="terminology",
        severity="high",
        source_excerpt="Original term",
        target_excerpt="Translated term",
        reason="Terminology mismatch with glossary.",
        auto_fixable=True,
    )
    assert finding.model_dump() == {
        "chapter_id": "chapter-1",
        "finding_type": "terminology",
        "severity": "high",
        "source_excerpt": "Original term",
        "target_excerpt": "Translated term",
        "reason": "Terminology mismatch with glossary.",
        "auto_fixable": True,
    }

    annotation = PublishingLayoutAnnotation(
        kind="widow",
        payload={
            "page_number": 12,
            "block_id": "para-2",
            "note": "Last line should move to next page.",
            "auto_fixable": False,
        },
    )
    assert annotation.model_dump() == {
        "kind": "widow",
        "payload": {
            "page_number": 12,
            "block_id": "para-2",
            "note": "Last line should move to next page.",
            "auto_fixable": False,
        },
    }


def test_publishing_workspace_persists_stage_state(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    state = PublishingStageState(stage="draft", fingerprint="abc123", status="ready")

    workspace.write_publishing_stage_state("draft", state)

    assert workspace.publishing_state_dir.joinpath("draft.json").exists()
    assert workspace.read_publishing_stage_state("draft") == state


def test_publishing_workspace_normalizes_dict_stage_state_payload(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path / "book")

    workspace.write_publishing_stage_state(
        "draft",
        {
            "fingerprint": "abc123",
            "status": "ready",
        },
    )

    assert workspace.read_publishing_stage_state("draft") == PublishingStageState(
        stage="draft",
        fingerprint="abc123",
        status="ready",
    )


def test_publishing_workspace_uses_method_stage_over_dict_stage(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")

    workspace.write_publishing_stage_state(
        "draft",
        {
            "stage": "final",
            "fingerprint": "abc123",
            "status": "ready",
        },
    )

    assert workspace.read_publishing_stage_state("draft") == PublishingStageState(
        stage="draft",
        fingerprint="abc123",
        status="ready",
    )


def test_publishing_workspace_detects_stale_stage_fingerprint(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    workspace.write_publishing_stage_state(
        "revision",
        {
            "fingerprint": "old-fingerprint",
            "status": "complete",
        },
    )

    assert workspace.stage_is_stale("revision", upstream_fingerprint="new-fingerprint")
    assert not workspace.stage_is_stale("revision", upstream_fingerprint="old-fingerprint")


def test_publishing_workspace_clears_deep_review_stage_outputs(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")

    workspace.publishing_deep_review_findings_path.parent.mkdir(parents=True, exist_ok=True)
    workspace.publishing_deep_review_findings_path.write_text("{}", encoding="utf-8")
    workspace.publishing_deep_review_chapters_path.write_text("{}", encoding="utf-8")
    workspace.publishing_deep_review_decisions_path.write_text("{}", encoding="utf-8")
    workspace.publishing_final_text_path.parent.mkdir(parents=True, exist_ok=True)
    workspace.publishing_final_text_path.write_text("final text", encoding="utf-8")
    workspace.publishing_final_pdf_path.write_text("final pdf", encoding="utf-8")
    workspace.write_publishing_stage_state(
        "deep-review",
        {
            "fingerprint": "abc123",
            "status": "complete",
        },
    )

    workspace.clear_publishing_stage_outputs("deep-review")

    assert not workspace.publishing_deep_review_findings_path.exists()
    assert not workspace.publishing_deep_review_chapters_path.exists()
    assert not workspace.publishing_deep_review_decisions_path.exists()
    assert not workspace.publishing_final_text_path.exists()
    assert not workspace.publishing_final_pdf_path.exists()
    assert workspace.read_publishing_stage_state("deep-review") is None


def test_publishing_deep_review_model_defaults() -> None:
    finding = PublishingAuditFinding(
        chapter_id="chapter-1",
        finding_type="terminology",
        severity="high",
        source_excerpt="Original term",
        target_excerpt="Translated term",
        reason="Terminology mismatch with glossary.",
    )
    annotation = PublishingLayoutAnnotation(kind="widow")

    assert finding.auto_fixable is False
    assert annotation.payload == {}
