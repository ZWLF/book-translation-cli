from pathlib import Path

from book_translator.publishing.lexicon import (
    merge_lexicon_overrides,
    normalize_lexicon_records,
)
from book_translator.state.workspace import Workspace


def test_normalize_lexicon_records_deduplicates_terms() -> None:
    records = [
        {"source": "Mars", "translation": "火星"},
        {"source": " Mars ", "translation": "火星 "},
        {"source": "Tesla", "translation": "特斯拉"},
    ]

    normalized = normalize_lexicon_records(records)

    assert normalized == [
        {"source": "Mars", "translation": "火星"},
        {"source": "Tesla", "translation": "特斯拉"},
    ]


def test_merge_lexicon_overrides_prefers_user_mapping() -> None:
    generated = {"Tesla": "特斯拉", "Mars": "火星"}
    user_map = {"Tesla": "特斯拉公司"}

    assert merge_lexicon_overrides(generated, user_map) == {
        "Tesla": "特斯拉公司",
        "Mars": "火星",
    }


def test_workspace_persists_publishing_lexicon_files(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")

    workspace.write_publishing_glossary({"Mars": "火星"})
    workspace.write_publishing_names({"Musk": "马斯克"})
    workspace.write_publishing_decisions([{"source": "Tesla", "translation": "特斯拉公司"}])

    assert workspace.publishing_glossary_path.read_text(encoding="utf-8")
    assert workspace.publishing_names_path.read_text(encoding="utf-8")
    assert workspace.publishing_decisions_path.read_text(encoding="utf-8")
