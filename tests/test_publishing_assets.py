from __future__ import annotations

import base64
import json
from pathlib import Path

from ebooklib import epub
from reportlab.pdfgen import canvas

from book_translator.publishing.assets import extract_source_assets, write_asset_manifest

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0ioAAAAASUVORK5CYII="
)


def test_extract_source_assets_from_epub_writes_images_and_captions(tmp_path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("id-assets")
    book.set_title("Asset EPUB")
    chapter = epub.EpubHtml(title="Chapter 1", file_name="chapter1.xhtml", lang="en")
    chapter.content = """
    <h1>Chapter 1</h1>
    <figure>
      <img src="images/rocket.png" alt="Rocket alt" />
      <figcaption>Falcon launch</figcaption>
    </figure>
    """
    image = epub.EpubItem(
        uid="rocket-image",
        file_name="images/rocket.png",
        media_type="image/png",
        content=_PNG_1X1,
    )
    book.add_item(chapter)
    book.add_item(image)
    book.toc = (chapter,)
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    source_path = tmp_path / "sample.epub"
    epub.write_epub(str(source_path), book)

    assets = extract_source_assets(
        source_path=source_path,
        output_dir=tmp_path / "assets",
    )

    assert len(assets) == 1
    assert assets[0].status == "extracted"
    assert assets[0].caption == "Falcon launch"
    assert assets[0].extracted_path is not None
    assert Path(assets[0].extracted_path).exists()


def test_extract_source_assets_from_epub_preserves_caption_only_anchor(tmp_path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("id-caption-only")
    book.set_title("Caption Only EPUB")
    chapter = epub.EpubHtml(title="Chapter 1", file_name="chapter1.xhtml", lang="en")
    chapter.content = """
    <h1>Chapter 1</h1>
    <figure>
      <img src="images/missing.png" alt="Missing alt" />
      <figcaption>Missing launch</figcaption>
    </figure>
    """
    book.add_item(chapter)
    book.toc = (chapter,)
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    source_path = tmp_path / "caption-only.epub"
    epub.write_epub(str(source_path), book)

    assets = extract_source_assets(
        source_path=source_path,
        output_dir=tmp_path / "assets",
    )

    assert len(assets) == 1
    assert assets[0].status == "caption-only"
    assert assets[0].caption == "Missing launch"
    assert assets[0].extracted_path is None


def test_extract_source_assets_from_pdf_writes_image_files(tmp_path: Path) -> None:
    source_path = tmp_path / "sample.pdf"
    image_path = tmp_path / "inline.png"
    image_path.write_bytes(_PNG_1X1)

    c = canvas.Canvas(str(source_path))
    c.drawImage(str(image_path), 72, 700, width=48, height=48)
    c.showPage()
    c.save()

    assets = extract_source_assets(
        source_path=source_path,
        output_dir=tmp_path / "assets",
    )

    assert len(assets) == 1
    assert assets[0].status == "extracted"
    assert assets[0].source_location_hint == "page:1"
    assert assets[0].extracted_path is not None
    assert Path(assets[0].extracted_path).exists()


def test_write_asset_manifest_records_counts(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    assets = extract_source_assets(
        source_path=_build_minimal_epub_with_missing_image(tmp_path),
        output_dir=tmp_path / "assets",
    )

    write_asset_manifest(assets=assets, manifest_path=manifest_path)

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["asset_count"] == 1
    assert payload["caption_only_count"] == 1
    assert payload["assets"][0]["caption"] == "Missing launch"


def _build_minimal_epub_with_missing_image(tmp_path: Path) -> Path:
    book = epub.EpubBook()
    book.set_identifier("id-manifest")
    book.set_title("Manifest EPUB")
    chapter = epub.EpubHtml(title="Chapter 1", file_name="chapter1.xhtml", lang="en")
    chapter.content = """
    <h1>Chapter 1</h1>
    <figure>
      <img src="images/missing.png" alt="Missing alt" />
      <figcaption>Missing launch</figcaption>
    </figure>
    """
    book.add_item(chapter)
    book.toc = (chapter,)
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    source_path = tmp_path / "manifest.epub"
    epub.write_epub(str(source_path), book)
    return source_path
