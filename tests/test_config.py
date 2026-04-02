from pathlib import Path

import pytest

from book_translator.config import RunConfig


def test_resolved_api_key_falls_back_to_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("GEMINI_API_KEY=test-dotenv-key\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = RunConfig(provider="gemini", model="gemini-3.1-flash-lite-preview")

    assert config.resolved_api_key() == "test-dotenv-key"
