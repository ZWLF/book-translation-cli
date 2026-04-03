from pathlib import Path

from book_translator.models import PublishingChapterArtifact, PublishingStageState
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


def test_publishing_workspace_persists_stage_state(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    state = PublishingStageState(stage="draft", fingerprint="abc123", status="ready")

    workspace.write_publishing_stage_state("draft", state)

    assert workspace.publishing_state_dir.joinpath("draft.json").exists()
    assert workspace.read_publishing_stage_state("draft") == state
