from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from booksmith.publishing.validation import (
    summarize_visual_blockers,
    validate_epub_output,
    validate_primary_output,
    validate_publishing_redlines,
)


def _write_epub(
    path: Path,
    *,
    rootfile_path: str,
    include_nav: bool,
) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_DEFLATED)
        archive.writestr(
            "META-INF/container.xml",
            f"""<?xml version="1.0" encoding="utf-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile media-type="application/oebps-package+xml" full-path="{rootfile_path}"/>
  </rootfiles>
</container>
""",
        )
        archive.writestr(
            rootfile_path,
            """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest>
    <item id="chapter-1" href="chapter-001.xhtml" media-type="application/xhtml+xml"/>
    {nav_item}
  </manifest>
  <spine>
    <itemref idref="chapter-1"/>
  </spine>
</package>
""".format(
                nav_item=(
                    '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                    'properties="nav"/>'
                    if include_nav
                    else ""
                )
            ),
        )
        if include_nav:
            archive.writestr(
                str(Path(rootfile_path).parent / "nav.xhtml"),
                """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <body>
    <nav epub:type="toc">
      <ol><li><a href="chapter-001.xhtml">Chapter 1</a></li></ol>
    </nav>
  </body>
</html>
""",
            )
        archive.writestr(
            str(Path(rootfile_path).parent / "chapter-001.xhtml"),
            """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <body><p>Sample chapter.</p></body>
</html>
""",
        )


def test_validate_epub_output_accepts_epub_root_path(tmp_path: Path) -> None:
    epub_path = tmp_path / "sample.epub"
    _write_epub(epub_path, rootfile_path="EPUB/content.opf", include_nav=True)

    output = validate_epub_output(epub_path)

    assert output["passed"] is True
    assert output["missing"] == []


def test_validate_epub_output_reports_missing_navigation(tmp_path: Path) -> None:
    broken_epub = tmp_path / "broken.epub"
    _write_epub(broken_epub, rootfile_path="EPUB/content.opf", include_nav=False)

    output = validate_epub_output(broken_epub)

    assert output["passed"] is False
    assert "EPUB/nav.xhtml" in output["missing"]


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


def test_validate_publishing_redlines_reports_blocking_text_and_title_artifacts(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "translated.txt"
    chapters_path = tmp_path / "final_chapters.jsonl"
    text_path.write_text(
        "\n".join(
            [
                "第一章：中文标题",
                "",
                "**重点句**",
                "",
                "***",
                "",
                "42",
                "",
                "This should have been translated.",
                "",
                "239 Musk (@elonmusk), X account.",
            ]
        ),
        encoding="utf-8",
    )
    chapters_path.write_text(
        '{"chapter_id":"c1","chapter_index":0,"title":"Obsess for Success","text":"正文"}\n',
        encoding="utf-8",
    )

    report = validate_publishing_redlines(
        text_path=text_path,
        chapters_path=chapters_path,
    )

    assert report["passed"] is False
    assert report["markdown_artifact_count"] == 2
    assert report["orphan_numeric_line_count"] == 1
    assert report["english_body_line_count"] == 1
    assert report["english_title_line_count"] == 1
    assert report["blocker_count"] == 5


def test_validate_publishing_redlines_allows_reference_lines_and_clean_titles(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "translated.txt"
    chapters_path = tmp_path / "final_chapters.jsonl"
    text_path.write_text(
        "\n".join(
            [
                "第一章：中文标题",
                "",
                "这是一段已经翻译好的正文。",
                "",
                "239 Musk (@elonmusk), X account.",
            ]
        ),
        encoding="utf-8",
    )
    chapters_path.write_text(
        '{"chapter_id":"c1","chapter_index":0,"title":"第一章：中文标题","text":"正文"}\n',
        encoding="utf-8",
    )

    report = validate_publishing_redlines(
        text_path=text_path,
        chapters_path=chapters_path,
    )

    assert report["passed"] is True
    assert report["blocker_count"] == 0


def test_validate_publishing_redlines_prefers_translated_title_fields(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "translated.txt"
    chapters_path = tmp_path / "revised_chapters.jsonl"
    text_path.write_text("痴迷于成功\n\n正文已翻译。\n", encoding="utf-8")
    chapters_path.write_text(
        (
            '{"chapter_id":"c1","chapter_index":0,'
            '"source_title":"Obsess for Success",'
            '"translated_title":"痴迷于成功","blocks":[],"assets":[]}\n'
        ),
        encoding="utf-8",
    )

    report = validate_publishing_redlines(
        text_path=text_path,
        chapters_path=chapters_path,
    )

    assert report["passed"] is True
    assert report["english_title_line_count"] == 0
