from __future__ import annotations

from zipfile import ZIP_DEFLATED, ZipFile

from book_translator.publishing.validation import (
    summarize_visual_blockers,
    validate_epub_output,
    validate_primary_output,
)


def test_validate_epub_output_reports_missing_navigation(tmp_path) -> None:
    broken_epub = tmp_path / "broken.epub"
    with ZipFile(broken_epub, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_DEFLATED)
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        )
        archive.writestr("OEBPS/content.opf", "<package></package>")

    output = validate_epub_output(broken_epub)

    assert output["passed"] is False
    assert "OEBPS/nav.xhtml" in output["missing"]


def test_validate_primary_output_accepts_nonempty_pdf(tmp_path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    output = validate_primary_output(pdf_path, "pdf")

    assert output["passed"] is True
    assert output["kind"] == "pdf"


def test_summarize_visual_blockers_defaults_to_zero_when_no_blockers() -> None:
    summary = summarize_visual_blockers([])
    assert summary["visual_blocker_count"] == 0
    assert summary["blockers"] == []
