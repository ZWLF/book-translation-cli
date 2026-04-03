from typer.testing import CliRunner

from book_translator.cli import _supports_spinner, app


def test_cli_shows_help() -> None:
    runner = CliRunner()

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
    runner = CliRunner()

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
