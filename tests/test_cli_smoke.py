from pathlib import Path

import pytest
from typer.testing import CliRunner

from booksmith.cli import _supports_spinner, app
from booksmith.provider_catalog import list_enabled_provider_options

runner = CliRunner()


def test_cli_shows_help() -> None:
    result = runner.invoke(app, ["--help"], prog_name="booksmith")
    help_text = " ".join(result.stdout.split())

    assert result.exit_code == 0
    assert "booksmith" in help_text
    assert "Booksmith translates text-based PDF and EPUB books" in help_text
    assert "--output" in help_text
    assert "workspace root" in help_text
    assert "--input" in help_text
    assert "source file" in help_text
    assert "directory scan" in help_text
    assert "--provider" in help_text
    for option in list_enabled_provider_options():
        assert option.provider_id in help_text
    assert "--model" in help_text
    assert "--api-key-env" in help_text
    assert "engineering" in help_text
    assert "publishing" in help_text
    assert "render-pdf" in help_text
    assert "render-pages" in help_text
    assert "qa-pdf" in help_text


def test_publishing_command_shows_help() -> None:
    result = runner.invoke(app, ["publishing"], prog_name="booksmith")

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

    monkeypatch.setattr("booksmith.cli._build_progress", fail_if_progress_is_created)

    result = runner.invoke(
        app,
        [
            "--input",
            str(empty_input),
            "--output",
            str(output_path),
        ],
        prog_name="booksmith",
    )

    assert result.exit_code == 2
    assert "No supported .pdf or .epub files found under" in result.output
    assert progress_started is False


def test_invalid_provider_fails_before_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_path = tmp_path / "out"
    progress_started = False

    def fail_if_progress_is_created(*args, **kwargs):
        nonlocal progress_started
        progress_started = True
        raise AssertionError("progress should not be created for invalid provider")

    monkeypatch.setattr("booksmith.cli._build_progress", fail_if_progress_is_created)

    result = runner.invoke(
        app,
        [
            "--input",
            str(input_root),
            "--output",
            str(output_path),
            "--provider",
            "anthropic",
        ],
        prog_name="booksmith",
    )

    assert result.exit_code == 2
    assert "Unsupported provider: anthropic" in result.output
    assert progress_started is False


def test_invalid_provider_model_combination_fails_before_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_path = tmp_path / "out"
    progress_started = False

    def fail_if_progress_is_created(*args, **kwargs):
        nonlocal progress_started
        progress_started = True
        raise AssertionError("progress should not be created for invalid model")

    monkeypatch.setattr("booksmith.cli._build_progress", fail_if_progress_is_created)

    result = runner.invoke(
        app,
        [
            "--input",
            str(input_root),
            "--output",
            str(output_path),
            "--provider",
            "openai",
            "--model",
            "gemini-3.1-flash-lite-preview",
        ],
        prog_name="booksmith",
    )

    assert result.exit_code == 2
    assert "Unsupported model for provider openai" in result.output
    assert "gemini-3.1-flash-lite-preview" in result.output
    assert progress_started is False
