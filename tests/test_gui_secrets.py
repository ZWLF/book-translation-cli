from __future__ import annotations

from pathlib import Path

import pytest

from booksmith.gui.secrets import save_provider_api_key


def test_save_provider_api_key_replaces_existing_provider_line_and_preserves_other_lines(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# comment",
                "OPENAI_API_KEY=old-openai-key",
                "OTHER_SETTING=keep-me",
                "GEMINI_API_KEY=old-gemini-key",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    save_provider_api_key(env_path, provider="openai", api_key="new-openai-key")

    assert env_path.read_text(encoding="utf-8") == "\n".join(
        [
            "# comment",
            "OPENAI_API_KEY=new-openai-key",
            "OTHER_SETTING=keep-me",
            "GEMINI_API_KEY=old-gemini-key",
        ]
    ) + "\n"


def test_save_provider_api_key_appends_missing_provider_line(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OTHER_SETTING=keep-me\n", encoding="utf-8")

    save_provider_api_key(env_path, provider="gemini", api_key="new-gemini-key")

    assert env_path.read_text(encoding="utf-8") == "\n".join(
        [
            "OTHER_SETTING=keep-me",
            "GEMINI_API_KEY=new-gemini-key",
        ]
    ) + "\n"


def test_save_provider_api_key_rejects_multiline_key_without_modifying_file(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    original = "OTHER_SETTING=keep-me\n"
    env_path.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="single line"):
        save_provider_api_key(
            env_path,
            provider="openai",
            api_key="first-line\nsecond-line",
        )

    assert env_path.read_text(encoding="utf-8") == original
