from pathlib import Path

import pytest
from typer.testing import CliRunner

from book_translator.cli import _supports_spinner, app

runner = CliRunner()


def test_cli_shows_help() -> None:
    result = runner.invoke(app, ["--help"], prog_name="book-translator")

    assert result.exit_code == 0
    assert "book-translator" in result.stdout
    assert "Translate text-based PDF and EPUB books" in result.stdout
    assert "engineering" in result.stdout
    assert "publishing" in result.stdout
    assert "render-pdf" in result.stdout
    assert "render-pages" in result.stdout
    assert "qa-pdf" in result.stdout


def test_publishing_command_shows_help() -> None:
    result = runner.invoke(app, ["publishing"], prog_name="book-translator")

    assert result.exit_code == 0
    assert "Publishing workflows" in result.stdout


def test_supports_spinner_rejects_gbk_console() -> None:
    class DummyConsole:
        encoding = "gbk"

    assert _supports_spinner(DummyConsole()) is False


def test_supports_spinner_accepts_utf8_console() -> None:
    class DummyConsole:
        encoding = "utf-8"

    assert _supports_spinner(DummyConsole()) is True


def test_cli_empty_input_translates_to_bad_parameter_without_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_input = tmp_path / "empty"
    empty_input.mkdir()
    output_path = tmp_path / "out"
    progress_started = False

    def fail_if_progress_is_created(*args, **kwargs):
        nonlocal progress_started
        progress_started = True
        raise AssertionError("progress should not be created for empty input")

    monkeypatch.setattr("book_translator.cli._build_progress", fail_if_progress_is_created)

    result = runner.invoke(
        app,
        [
            "--input",
            str(empty_input),
            "--output",
            str(output_path),
        ],
        prog_name="book-translator",
    )

    assert result.exit_code == 2
    assert "No supported .pdf or .epub files found under" in result.output
    assert progress_started is False
