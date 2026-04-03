import json
from pathlib import Path

from reportlab.pdfgen import canvas
from typer.testing import CliRunner

from book_translator.cli import app
from book_translator.output.pdf_raster import choose_sample_pages, parse_page_spec, render_pdf_pages
from book_translator.state.workspace import Workspace


def _build_sample_pdf(path: Path, total_pages: int = 4) -> None:
    sheet = canvas.Canvas(str(path))
    for page_number in range(1, total_pages + 1):
        sheet.drawString(72, 720, f"Sample page {page_number}")
        sheet.showPage()
    sheet.save()


def test_parse_page_spec_supports_ranges() -> None:
    assert parse_page_spec("1, 3-4, 6", total_pages=8) == [1, 3, 4, 6]


def test_choose_sample_pages_focuses_on_front_middle_and_back() -> None:
    assert choose_sample_pages(20) == [1, 2, 3, 4, 5, 10, 11, 18, 19, 20]


def test_render_pdf_pages_writes_pngs(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    output_dir = tmp_path / "pages"
    _build_sample_pdf(pdf_path, total_pages=3)

    rendered = render_pdf_pages(
        pdf_path=pdf_path,
        output_dir=output_dir,
        pages=[1, 3],
        dpi=72,
    )

    assert [item.page_number for item in rendered] == [1, 3]
    assert output_dir.joinpath("page-001.png").exists()
    assert output_dir.joinpath("page-003.png").exists()
    assert output_dir.joinpath("page-001.png").read_bytes().startswith(b"\x89PNG")


def test_render_pages_command_rasterizes_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    output_dir = tmp_path / "pages"
    _build_sample_pdf(pdf_path, total_pages=3)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "render-pages",
            "--pdf",
            str(pdf_path),
            "--output-dir",
            str(output_dir),
            "--pages",
            "1,3",
        ],
    )

    assert result.exit_code == 0
    assert output_dir.joinpath("page-001.png").exists()
    assert output_dir.joinpath("page-003.png").exists()


def test_qa_pdf_command_writes_workspace_artifacts(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace = Workspace(workspace_root)
    workspace.root.mkdir(parents=True, exist_ok=True)
    _build_sample_pdf(workspace.pdf_output_path, total_pages=4)

    runner = CliRunner()
    result = runner.invoke(app, ["qa-pdf", "--workspace", str(workspace_root), "--pages", "1-2"])

    assert result.exit_code == 0
    assert workspace.qa_pages_path.joinpath("page-001.png").exists()
    assert workspace.qa_pages_path.joinpath("page-002.png").exists()
    summary = json.loads(workspace.qa_summary_path.read_text(encoding="utf-8"))
    assert summary["rendered_pages"] == [1, 2]
    assert summary["pdf_path"] == str(workspace.pdf_output_path)


def test_qa_pdf_command_prefers_publishing_pdf_when_engineering_pdf_missing(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace = Workspace(workspace_root)
    workspace.root.mkdir(parents=True, exist_ok=True)
    workspace.publishing_final_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    _build_sample_pdf(workspace.publishing_final_pdf_path, total_pages=3)

    runner = CliRunner()
    result = runner.invoke(app, ["qa-pdf", "--workspace", str(workspace_root), "--pages", "1"])

    assert result.exit_code == 0
    assert workspace.publishing_qa_pages_path.joinpath("page-001.png").exists()
    summary = json.loads(workspace.publishing_qa_summary_path.read_text(encoding="utf-8"))
    assert summary["rendered_pages"] == [1]
    assert summary["pdf_path"] == str(workspace.publishing_final_pdf_path)
