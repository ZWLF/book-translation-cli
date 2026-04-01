import json
from pathlib import Path

import pytest

from book_translator.models import Chunk, Manifest, TranslationResult
from book_translator.state.workspace import Workspace


def test_workspace_persists_translations_and_errors(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    manifest = Manifest(
        book_id="book-1",
        source_path="sample.epub",
        source_fingerprint="abc123",
        provider="openai",
        model="gpt-4o-mini",
        config_fingerprint="cfg-1",
    )
    workspace.initialize(manifest)

    chunk = Chunk(
        chunk_id="chunk-1",
        chapter_id="chapter-1",
        chapter_index=0,
        chunk_index=0,
        chapter_title="Chapter 1",
        source_text="Hello world",
        source_token_estimate=3,
    )
    workspace.write_chunks([chunk])
    workspace.append_translation(
        TranslationResult(
            chunk_id="chunk-1",
            translated_text="你好，世界",
            provider="openai",
            model="gpt-4o-mini",
            attempt_count=1,
            latency_ms=123,
            input_tokens=10,
            output_tokens=8,
            estimated_cost_usd=0.001,
        )
    )
    workspace.write_errors(
        [
            {
                "chunk_id": "chunk-2",
                "chapter_title": "Chapter 1",
                "chunk_index": 1,
                "error_type": "timeout",
            }
        ]
    )

    assert workspace.completed_chunk_ids() == {"chunk-1"}
    error_data = json.loads(workspace.error_log_path.read_text(encoding="utf-8"))
    assert error_data[0]["chunk_id"] == "chunk-2"


def test_workspace_rejects_resume_when_config_changes(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    workspace.initialize(
        Manifest(
            book_id="book-1",
            source_path="sample.epub",
            source_fingerprint="abc123",
            provider="openai",
            model="gpt-4o-mini",
            config_fingerprint="cfg-1",
        )
    )

    with pytest.raises(ValueError):
        workspace.assert_resume_compatible(
            source_fingerprint="abc123",
            provider="openai",
            model="gpt-4o-mini",
            config_fingerprint="cfg-2",
        )
