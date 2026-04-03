from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path

from book_translator.models import PublishingAsset, PublishingBlock, StructuredPublishingBook


@dataclass(slots=True)
class _RenderedAsset:
    asset: PublishingAsset
    file_name: str


def render_structured_epub(
    book: StructuredPublishingBook,
    output_path: Path,
    *,
    book_title: str | None = None,
    author: str | None = None,
    language: str = "zh-CN",
) -> None:
    try:
        from ebooklib import epub
    except ImportError as exc:
        raise RuntimeError(
            "ebooklib is required for EPUB output. Install project dependencies first."
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    epub_book = epub.EpubBook()
    title = (book_title or book.title or "Translated Edition").strip()
    epub_book.set_identifier(_identifier_from_title(title))
    epub_book.set_title(title)
    epub_book.set_language(language)
    if author:
        epub_book.add_metadata("DC", "creator", author)

    epub_book.add_item(
        epub.EpubItem(
            uid="style_nav",
            file_name="styles/style.css",
            media_type="text/css",
            content=_build_stylesheet().encode("utf-8"),
        )
    )

    rendered_assets = _add_assets(epub_book, book)
    sorted_chapters = sorted(book.chapters, key=lambda item: item.chapter_index)
    chapter_items = []
    for index, chapter in enumerate(sorted_chapters, start=1):
        file_name = f"chapter-{index:03d}.xhtml"
        chapter_item = epub.EpubHtml(
            title=_toc_label(chapter),
            file_name=file_name,
            lang=language,
        )
        chapter_item.content = _render_chapter_html(
            chapter=chapter,
            rendered_assets=rendered_assets,
        ).encode("utf-8")
        epub_book.add_item(chapter_item)
        chapter_items.append(chapter_item)

    epub_book.toc = tuple(
        epub.Link(item.file_name, _toc_label(chapter), chapter.chapter_id)
        for item, chapter in zip(chapter_items, sorted_chapters, strict=True)
    )
    epub_book.spine = ["nav", *chapter_items]
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())

    epub.write_epub(str(output_path), epub_book, options={"epub3_pages": False})


def _add_assets(
    epub_book,
    book: StructuredPublishingBook,
) -> dict[str, _RenderedAsset]:
    from ebooklib import epub

    rendered_assets: dict[str, _RenderedAsset] = {}
    used_file_names: set[str] = set()
    for chapter in sorted(book.chapters, key=lambda item: item.chapter_index):
        for asset in chapter.assets:
            if not asset.extracted_path:
                continue
            path = Path(asset.extracted_path)
            if not path.exists():
                continue
            file_name = _asset_file_name(
                chapter_id=chapter.chapter_id,
                asset=asset,
                existing=used_file_names,
                source_path=path,
            )
            media_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
            epub_book.add_item(
                epub.EpubItem(
                    uid=f"{chapter.chapter_id}-{asset.source_asset_id}",
                    file_name=file_name,
                    media_type=media_type,
                    content=path.read_bytes(),
                )
            )
            used_file_names.add(file_name)
            rendered_assets[asset.source_asset_id] = _RenderedAsset(
                asset=asset,
                file_name=file_name,
            )
            if asset.block_anchor_id:
                rendered_assets[asset.block_anchor_id] = _RenderedAsset(
                    asset=asset,
                    file_name=file_name,
                )
    return rendered_assets


def _asset_file_name(
    *,
    chapter_id: str,
    asset: PublishingAsset,
    existing: set[str],
    source_path: Path,
) -> str:
    suffix = source_path.suffix.lower() or ".bin"
    base = f"images/{chapter_id}-{asset.source_asset_id}{suffix}"
    if base not in existing:
        return base
    index = 2
    while True:
        candidate = f"images/{chapter_id}-{asset.source_asset_id}-{index}{suffix}"
        if candidate not in existing:
            return candidate
        index += 1


def _render_chapter_html(
    *,
    chapter,
    rendered_assets: dict[str, _RenderedAsset],
) -> str:
    title_primary, title_secondary = _chapter_titles(chapter)
    title_lines = [f"<h1 class=\"chapter-title\">{html_escape(title_primary)}</h1>"]
    if title_secondary:
        title_lines.append(
            f"<p class=\"chapter-source-title\">{html_escape(title_secondary)}</p>"
        )

    body_parts: list[str] = []
    index = 0
    blocks = sorted(chapter.blocks, key=lambda item: item.order_index)
    while index < len(blocks):
        block = blocks[index]
        if block.kind == "ordered_item":
            run, index = _collect_run(blocks, index, "ordered_item")
            body_parts.append(_render_ordered_run(run))
            continue
        if block.kind == "unordered_item":
            run, index = _collect_run(blocks, index, "unordered_item")
            body_parts.append(_render_unordered_run(run))
            continue
        body_parts.append(_render_block(block, rendered_assets=rendered_assets))
        index += 1

    body = "\n".join(part for part in body_parts if part)
    return _html_document(
        title=title_primary,
        body="\n".join(title_lines + ([body] if body else [])),
        body_class="chapter",
    )


def _render_block(
    block: PublishingBlock,
    *,
    rendered_assets: dict[str, _RenderedAsset],
) -> str:
    if block.kind == "paragraph":
        return f"<p>{_render_inline(block.text)}</p>"
    if block.kind == "heading":
        return f"<h2>{_render_inline(block.text)}</h2>"
    if block.kind == "callout":
        return f"<aside class=\"callout\">{_render_paragraph_group(block.text)}</aside>"
    if block.kind == "qa_question":
        return f"<p class=\"qa-question\">{_render_inline(block.text)}</p>"
    if block.kind == "qa_answer":
        return f"<p class=\"qa-answer\">{_render_inline(block.text)}</p>"
    if block.kind == "quote":
        return f"<blockquote>{_render_paragraph_group(block.text)}</blockquote>"
    if block.kind == "reference_entry":
        return f"<p class=\"reference\">{_render_inline(block.text)}</p>"
    if block.kind == "caption":
        return _render_caption_block(block, rendered_assets=rendered_assets)
    if block.kind == "image":
        return _render_image_block(block, rendered_assets=rendered_assets)
    return f"<p>{_render_inline(block.text)}</p>" if block.text.strip() else ""


def _render_image_block(
    block: PublishingBlock,
    *,
    rendered_assets: dict[str, _RenderedAsset],
) -> str:
    asset = _pick_render_asset(block, rendered_assets)
    if asset is None:
        if block.text.strip():
            return (
                "<figure class=\"image-placeholder\">"
                f"<figcaption>{_render_inline(block.text)}</figcaption>"
                "</figure>"
            )
        return ""
    return (
        "<figure class=\"image\">"
        f"<img src=\"{html_escape(asset.file_name)}\" "
        f"alt=\"{html_escape(block.text.strip() or asset.asset.caption or '')}\" />"
        "</figure>"
    )


def _render_caption_block(
    block: PublishingBlock,
    *,
    rendered_assets: dict[str, _RenderedAsset],
) -> str:
    asset = _pick_render_asset(block, rendered_assets, prefer_caption=True)
    caption = block.text.strip() or (asset.asset.caption if asset else "")
    if asset is not None and asset.asset.status == "extracted":
        return (
            "<figure class=\"image\">"
            f"<img src=\"{html_escape(asset.file_name)}\" alt=\"{html_escape(caption)}\" />"
            f"<figcaption>{_render_inline(caption)}</figcaption>"
            "</figure>"
        )
    if caption:
        return (
            "<figure class=\"image-placeholder\">"
            f"<figcaption>{_render_inline(caption)}</figcaption>"
            "</figure>"
        )
    return ""


def _pick_render_asset(
    block: PublishingBlock,
    rendered_assets: dict[str, _RenderedAsset],
    *,
    prefer_caption: bool = False,
) -> _RenderedAsset | None:
    if block.block_id in rendered_assets:
        return rendered_assets[block.block_id]
    if block.source_anchor and block.source_anchor in rendered_assets:
        return rendered_assets[block.source_anchor]
    if prefer_caption:
        normalized = _normalize_key(block.text)
        for rendered in rendered_assets.values():
            caption = rendered.asset.caption or ""
            if caption and _normalize_key(caption) == normalized:
                return rendered
    for rendered in rendered_assets.values():
        if rendered.asset.status == "extracted":
            return rendered
    return None


def _collect_run(
    blocks: list[PublishingBlock],
    start_index: int,
    kind: str,
) -> tuple[list[PublishingBlock], int]:
    run: list[PublishingBlock] = []
    index = start_index
    while index < len(blocks) and blocks[index].kind == kind:
        run.append(blocks[index])
        index += 1
    return run, index


def _render_ordered_run(blocks: list[PublishingBlock]) -> str:
    if not blocks:
        return ""
    items = [
        f"<li>{_render_inline(block.text)}</li>"
        for block in blocks
        if block.text.strip()
    ]
    if not items:
        return ""
    start = _ordered_start(blocks[0].source_anchor)
    start_attr = f' start="{start}"' if start not in (None, 1) else ""
    return f"<ol class=\"ordered-list\"{start_attr}>" + "".join(items) + "</ol>"


def _render_unordered_run(blocks: list[PublishingBlock]) -> str:
    items = [
        f"<li>{_render_inline(block.text)}</li>"
        for block in blocks
        if block.text.strip()
    ]
    if not items:
        return ""
    return "<ul class=\"unordered-list\">" + "".join(items) + "</ul>"


def _ordered_start(source_anchor: str | None) -> int | None:
    if not source_anchor:
        return None
    match = re.match(r"^\s*(\d{1,3})[.)]\s+", source_anchor)
    if match is None:
        return None
    start = int(match.group(1))
    return start if start > 1 else None


def _render_inline(text: str) -> str:
    normalized = html_escape(text.strip())
    return normalized.replace("\n", "<br />")


def _render_paragraph_group(text: str) -> str:
    parts = [
        f"<p>{_render_inline(part)}</p>"
        for part in (segment.strip() for segment in text.split("\n\n"))
        if part
    ]
    return "".join(parts) if parts else f"<p>{_render_inline(text)}</p>"


def _html_document(*, title: str, body: str, body_class: str) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
        "<!DOCTYPE html>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" lang=\"zh-CN\">"
        "<head>"
        "<meta charset=\"utf-8\" />"
        f"<title>{html_escape(title)}</title>"
        "<link rel=\"stylesheet\" type=\"text/css\" href=\"styles/style.css\" />"
        "</head>"
        f"<body class=\"{html_escape(body_class)}\">"
        f"{body}"
        "</body>"
        "</html>"
    )


def _build_stylesheet() -> str:
    return """
body {
  font-family: serif;
  line-height: 1.6;
  margin: 0;
  padding: 0;
  color: #222;
}

body.chapter {
  padding: 1.6em 1.1em;
}

h1.chapter-title {
  font-size: 1.7em;
  text-align: center;
  margin: 0 0 0.25em 0;
}

p.chapter-source-title {
  text-align: center;
  color: #6b6259;
  margin: 0 0 1.1em 0;
  font-size: 0.92em;
}

p,
li {
  margin: 0 0 0.7em 0;
}

ol.ordered-list {
  margin: 0.4em 0 0.8em 1.4em;
  padding: 0;
}

ul.unordered-list {
  margin: 0.4em 0 0.8em 1.4em;
  padding: 0;
}

aside.callout {
  background: #ece9e4;
  padding: 0.8em 0.9em;
  margin: 0.8em 0;
}

aside.callout p {
  margin: 0 0 0.55em 0;
}

blockquote {
  margin: 0.8em 0;
  padding-left: 1em;
  border-left: 0.22em solid #d8ccbf;
  color: #444;
}

p.qa-question {
  font-weight: bold;
  margin-top: 0.6em;
}

p.qa-answer {
  margin-left: 0;
}

p.reference {
  font-size: 0.85em;
  color: #6b6259;
}

figure.image,
figure.image-placeholder {
  margin: 0.9em 0;
}

figure.image img {
  max-width: 100%;
  height: auto;
}

figcaption {
  font-size: 0.9em;
  color: #6b6259;
  margin-top: 0.35em;
}
""".strip()


def _toc_label(chapter) -> str:
    title_primary, title_secondary = _chapter_titles(chapter)
    if title_primary and title_secondary and title_primary != title_secondary:
        return f"{title_primary} / {title_secondary}"
    return title_primary or title_secondary or ""


def _chapter_titles(chapter) -> tuple[str, str]:
    title_primary = getattr(chapter, "translated_title", "") or getattr(
        chapter, "source_title", ""
    )
    title_secondary = getattr(chapter, "source_title", "") or ""
    if title_secondary == title_primary:
        title_secondary = ""
    return title_primary.strip(), title_secondary.strip()


def _normalize_key(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _identifier_from_title(title: str) -> str:
    slug = _normalize_key(title)[:32]
    return f"epub-{slug}" if slug else "epub-book"
