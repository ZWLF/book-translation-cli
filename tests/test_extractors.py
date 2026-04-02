from pathlib import Path

from ebooklib import epub
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from book_translator.extractors.epub import extract_epub
from book_translator.extractors.pdf import extract_pdf


def _write_text_pdf(path: Path, lines: list[str]) -> None:
    content_lines = ["BT", "/F1 18 Tf", "72 720 Td"]
    first = True
    for line in lines:
        if not first:
            content_lines.append("0 -24 Td")
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"({escaped}) Tj")
        first = False
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode()
    )
    path.write_bytes(bytes(pdf))


def _write_text_pdf_with_outline(
    path: Path,
    pages: list[list[str]],
    outline: list[tuple[str, int]],
) -> None:
    plain_path = path.with_name(f"{path.stem}-plain.pdf")
    c = canvas.Canvas(str(plain_path))
    for page_lines in pages:
        y = 760
        for line in page_lines:
            c.drawString(72, y, line)
            y -= 24
        c.showPage()
    c.save()

    reader = PdfReader(str(plain_path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for title, page_index in outline:
        writer.add_outline_item(title, page_index)
    with path.open("wb") as handle:
        writer.write(handle)
    plain_path.unlink()


def test_extract_epub_reads_text_and_toc(tmp_path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("id-1")
    book.set_title("Sample EPUB")
    chapter1 = epub.EpubHtml(title="Chapter 1", file_name="chapter1.xhtml", lang="en")
    chapter1.content = "<h1>Chapter 1</h1><p>Hello world.</p>"
    chapter2 = epub.EpubHtml(title="Chapter 2", file_name="chapter2.xhtml", lang="en")
    chapter2.content = "<h1>Chapter 2</h1><p>Goodbye world.</p>"
    book.add_item(chapter1)
    book.add_item(chapter2)
    book.toc = (chapter1, chapter2)
    book.spine = ["nav", chapter1, chapter2]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    file_path = tmp_path / "sample.epub"
    epub.write_epub(str(file_path), book)

    extracted = extract_epub(file_path)

    assert extracted.title == "Sample EPUB"
    assert [entry.title for entry in extracted.toc] == ["Chapter 1", "Chapter 2"]
    assert "Hello world." in extracted.raw_text


def test_extract_pdf_reads_text(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.pdf"
    _write_text_pdf(file_path, ["Chapter 1", "Hello PDF world."])

    extracted = extract_pdf(file_path)

    assert extracted.title == "sample"
    assert "Hello PDF world." in extracted.raw_text


def test_extract_pdf_reads_outline_page_numbers(tmp_path: Path) -> None:
    file_path = tmp_path / "outlined.pdf"
    _write_text_pdf_with_outline(
        file_path,
        pages=[
            ["Contents", "Chapter 1", "Chapter 2"],
            ["Chapter 1", "Actual first body."],
            ["Chapter 2", "Actual second body."],
        ],
        outline=[("Chapter 1", 1), ("Chapter 2", 2)],
    )

    extracted = extract_pdf(file_path)

    assert extracted.pages == [
        "Contents\nChapter 1\nChapter 2",
        "Chapter 1\nActual first body.",
        "Chapter 2\nActual second body.",
    ]
    assert [(entry.title, entry.page_index) for entry in extracted.toc] == [
        ("Chapter 1", 1),
        ("Chapter 2", 2),
    ]
