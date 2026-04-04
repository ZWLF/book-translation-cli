from __future__ import annotations

import json
from pathlib import Path

import fitz
from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, ITEM_IMAGE, epub

from booksmith.models import PublishingAsset
from booksmith.utils import slugify


def extract_source_assets(
    *,
    source_path: Path,
    output_dir: Path,
) -> list[PublishingAsset]:
    suffix = source_path.suffix.lower()
    if suffix == ".epub":
        return _extract_epub_assets(source_path=source_path, output_dir=output_dir)
    if suffix == ".pdf":
        return _extract_pdf_assets(source_path=source_path, output_dir=output_dir)
    return []


def write_asset_manifest(*, assets: list[PublishingAsset], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "asset_count": len(assets),
        "extracted_count": sum(asset.status == "extracted" for asset in assets),
        "caption_only_count": sum(asset.status == "caption-only" for asset in assets),
        "missing_count": sum(asset.status == "missing" for asset in assets),
        "assets": [asset.model_dump() for asset in assets],
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _extract_epub_assets(*, source_path: Path, output_dir: Path) -> list[PublishingAsset]:
    book = epub.read_epub(str(source_path))
    caption_map = _build_epub_caption_map(book)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets: list[PublishingAsset] = []
    seen_hrefs: set[str] = set()
    seen_names: set[str] = set()
    emitted_caption_keys: set[str] = set()

    for index, item in enumerate(book.get_items_of_type(ITEM_IMAGE), start=1):
        href = getattr(item, "file_name", "") or ""
        seen_hrefs.add(href)
        seen_names.add(Path(href).name)
        stem = slugify(Path(href).stem or item.get_id() or f"image-{index}")
        ext = Path(href).suffix or ".bin"
        output_path = output_dir / f"{stem}-{index}{ext}"
        output_path.write_bytes(item.get_content())

        assets.append(
            PublishingAsset(
                source_asset_id=str(item.get_id() or href or f"image-{index}"),
                source_location_hint=href or None,
                extracted_path=str(output_path),
                caption=caption_map.get(href) or caption_map.get(Path(href).name),
                status="extracted",
            )
        )

    for href, caption in sorted(caption_map.items()):
        canonical_key = Path(href).name or href
        if (
            href in seen_hrefs
            or canonical_key in seen_names
            or canonical_key in emitted_caption_keys
        ):
            continue
        emitted_caption_keys.add(canonical_key)
        assets.append(
            PublishingAsset(
                source_asset_id=f"caption-only:{href}",
                source_location_hint=href,
                caption=caption,
                status="caption-only",
            )
        )

    return assets


def _extract_pdf_assets(*, source_path: Path, output_dir: Path) -> list[PublishingAsset]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets: list[PublishingAsset] = []
    seen_xrefs: set[int] = set()

    with fitz.open(source_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            for image_index, image in enumerate(page.get_images(full=True), start=1):
                xref = int(image[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                extracted = document.extract_image(xref)
                ext = f".{extracted.get('ext', 'bin')}"
                output_path = output_dir / f"page-{page_index + 1:03d}-image-{image_index}{ext}"
                output_path.write_bytes(extracted["image"])
                assets.append(
                    PublishingAsset(
                        source_asset_id=f"pdf-xref-{xref}",
                        source_location_hint=f"page:{page_index + 1}",
                        extracted_path=str(output_path),
                        status="extracted",
                    )
                )

    return assets


def _build_epub_caption_map(book: epub.EpubBook) -> dict[str, str]:
    captions: dict[str, str] = {}
    for document in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(document.get_content(), "html.parser")
        for image in soup.find_all("img"):
            href = (image.get("src") or "").strip()
            if not href:
                continue
            caption = _resolve_epub_image_caption(image)
            if not caption:
                continue
            captions[href] = caption
            captions.setdefault(Path(href).name, caption)
    return captions


def _resolve_epub_image_caption(image: object) -> str | None:
    tag = image
    figcaption = getattr(getattr(tag, "parent", None), "find", lambda *_args, **_kwargs: None)(
        "figcaption"
    )
    if figcaption is not None:
        text = figcaption.get_text(" ", strip=True)
        if text:
            return text

    for attribute in ("alt", "title"):
        value = getattr(tag, "get", lambda *_args, **_kwargs: None)(attribute)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
