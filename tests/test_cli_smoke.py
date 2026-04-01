from typer.testing import CliRunner

from book_translator.cli import app


def test_cli_shows_help() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"], prog_name="book-translator")

    assert result.exit_code == 0
    assert "book-translator" in result.stdout
    assert "Translate text-based PDF and EPUB books" in result.stdout
