from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from book_translator.models import Chunk, Manifest, TranslationResult


@dataclass(slots=True)
class PrintableBlock:
    kind: str
    text: str


@dataclass(slots=True)
class PrintableChapter:
    chapter_id: str
    chapter_index: int
    source_title: str
    display_title: str
    blocks: list[PrintableBlock] = field(default_factory=list)


@dataclass(slots=True)
class PrintableBook:
    book_id: str
    title_en: str
    title_zh: str | None
    author: str | None
    source_path: str
    provider: str
    model: str
    estimated_cost_usd: float | None
    chapters: list[PrintableChapter] = field(default_factory=list)


def build_printable_book(
    *,
    manifest: Manifest,
    summary: dict[str, Any],
    chunks: list[Chunk],
    translations: dict[str, TranslationResult],
) -> PrintableBook:
    title_en, author = _parse_title_and_author(Path(manifest.source_path).stem)
    grouped: dict[str, dict[str, Any]] = {}

    for chunk in sorted(chunks, key=lambda item: (item.chapter_index, item.chunk_index)):
        translated = translations.get(chunk.chunk_id)
        if translated is None or not translated.translated_text.strip():
            continue
        entry = grouped.setdefault(
            chunk.chapter_id,
            {
                "chapter_id": chunk.chapter_id,
                "chapter_index": chunk.chapter_index,
                "source_title": chunk.chapter_title,
                "texts": [],
            },
        )
        entry["texts"].append(translated.translated_text)

    title_zh: str | None = None
    chapters: list[PrintableChapter] = []
    for entry in sorted(grouped.values(), key=lambda item: item["chapter_index"]):
        combined_text = "\n\n".join(entry["texts"]).strip()
        if not combined_text:
            continue

        raw_blocks = _split_raw_blocks(combined_text)
        display_title = entry["source_title"]
        printable_blocks: list[PrintableBlock] = []

        for lines in raw_blocks:
            cleaned_lines = _clean_block_lines(lines)
            if not cleaned_lines:
                continue

            if title_zh is None and _is_book_title(cleaned_lines[0]):
                title_zh = cleaned_lines[0]
                cleaned_lines = cleaned_lines[1:]
                if not cleaned_lines:
                    continue

            if (
                _looks_like_chapter_heading(cleaned_lines[0])
                and display_title == entry["source_title"]
            ):
                display_title = cleaned_lines[0]
                cleaned_lines = cleaned_lines[1:]
                if not cleaned_lines:
                    continue

            if len(cleaned_lines) == 1 and _looks_like_section_heading(cleaned_lines[0]):
                printable_blocks.append(
                    PrintableBlock(kind="section_heading", text=cleaned_lines[0])
                )
                continue

            printable_blocks.append(PrintableBlock(kind="paragraph", text="".join(cleaned_lines)))

        if not printable_blocks:
            continue

        chapters.append(
            PrintableChapter(
                chapter_id=entry["chapter_id"],
                chapter_index=entry["chapter_index"],
                source_title=entry["source_title"],
                display_title=display_title,
                blocks=printable_blocks,
            )
        )

    return PrintableBook(
        book_id=manifest.book_id,
        title_en=title_en,
        title_zh=title_zh,
        author=author,
        source_path=manifest.source_path,
        provider=manifest.provider,
        model=manifest.model,
        estimated_cost_usd=_as_float(summary.get("estimated_cost_usd")),
        chapters=chapters,
    )


def render_polished_pdf(book: PrintableBook, output_path: Path) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.lib.pagesizes import A5
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            BaseDocTemplate,
            Frame,
            NextPageTemplate,
            PageBreak,
            PageTemplate,
            Paragraph,
            Spacer,
        )
        from reportlab.platypus.tableofcontents import TableOfContents
    except ImportError as exc:
        raise RuntimeError(
            "reportlab is required for polished PDF output. Install project dependencies first."
        ) from exc

    fonts = _register_book_fonts(pdfmetrics, TTFont)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    page_width, page_height = A5
    margins = {
        "left": 18 * mm,
        "right": 18 * mm,
        "top": 18 * mm,
        "bottom": 18 * mm,
    }

    palette = {
        "ink": colors.HexColor("#222222"),
        "muted": colors.HexColor("#6B6259"),
        "accent": colors.HexColor("#8C5A2B"),
        "line": colors.HexColor("#D8CCBF"),
    }

    story: list[Any] = []

    cover_title_zh = book.title_zh or f"{book.title_en} 简体中文版"
    cover_title_en = book.title_en
    cover_author = book.author or "未知作者"

    cover_title_style = ParagraphStyle(
        "CoverTitleZh",
        parent=styles["Title"],
        fontName=fonts["title"],
        fontSize=24,
        leading=32,
        alignment=TA_CENTER,
        textColor=palette["ink"],
        spaceAfter=10,
    )
    cover_subtitle_style = ParagraphStyle(
        "CoverTitleEn",
        parent=styles["BodyText"],
        fontName=fonts["sans"],
        fontSize=10.5,
        leading=15,
        alignment=TA_CENTER,
        textColor=palette["muted"],
        spaceAfter=18,
    )
    cover_meta_style = ParagraphStyle(
        "CoverMeta",
        parent=styles["BodyText"],
        fontName=fonts["body"],
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        textColor=palette["accent"],
    )
    note_heading_style = ParagraphStyle(
        "NoteHeading",
        parent=styles["Heading2"],
        fontName=fonts["title"],
        fontSize=15,
        leading=22,
        textColor=palette["ink"],
        alignment=TA_LEFT,
        spaceAfter=10,
    )
    note_body_style = ParagraphStyle(
        "NoteBody",
        parent=styles["BodyText"],
        fontName=fonts["body"],
        fontSize=9.5,
        leading=15,
        textColor=palette["ink"],
        alignment=TA_JUSTIFY,
        firstLineIndent=18,
        spaceAfter=8,
    )
    toc_heading_style = ParagraphStyle(
        "TocHeading",
        parent=styles["Heading1"],
        fontName=fonts["title"],
        fontSize=18,
        leading=26,
        alignment=TA_CENTER,
        textColor=palette["ink"],
        spaceAfter=16,
    )
    chapter_title_style = ParagraphStyle(
        "ChapterTitleZh",
        parent=styles["Heading1"],
        fontName=fonts["title"],
        fontSize=18,
        leading=26,
        alignment=TA_CENTER,
        textColor=palette["ink"],
        spaceAfter=8,
    )
    chapter_source_style = ParagraphStyle(
        "ChapterTitleEn",
        parent=styles["BodyText"],
        fontName=fonts["sans"],
        fontSize=9.5,
        leading=14,
        alignment=TA_CENTER,
        textColor=palette["muted"],
        spaceAfter=12,
    )
    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading3"],
        fontName=fonts["title"],
        fontSize=12.5,
        leading=18,
        textColor=palette["accent"],
        alignment=TA_LEFT,
        spaceBefore=6,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyZh",
        parent=styles["BodyText"],
        fontName=fonts["body"],
        fontSize=10.5,
        leading=18,
        textColor=palette["ink"],
        alignment=TA_JUSTIFY,
        firstLineIndent=21,
        spaceAfter=10,
    )
    toc_level_style = ParagraphStyle(
        "TOCLevel0",
        parent=styles["BodyText"],
        fontName=fonts["body"],
        fontSize=10.5,
        leading=16,
        textColor=palette["ink"],
        leftIndent=0,
        firstLineIndent=0,
    )

    story.append(Spacer(1, 42 * mm))
    story.append(Paragraph(cover_title_zh, cover_title_style))
    story.append(Paragraph(cover_title_en, cover_subtitle_style))
    story.append(Spacer(1, 28 * mm))
    story.append(Paragraph(f"{cover_author}", cover_meta_style))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("工程化翻译精排版", cover_meta_style))
    story.append(PageBreak())

    story.append(Paragraph("版本说明", note_heading_style))
    story.append(
        Paragraph(
            "本 PDF 基于已完成的翻译工作区自动重排生成。"
            "正文内容来自工程化翻译结果，版式经过本地书籍化渲染，"
            "目标是获得稳定、清晰、适合连续阅读的中文版本，而不是逐页复刻原版英文 PDF 的视觉设计。",
            note_body_style,
        )
    )
    story.append(
        Paragraph(
            f"来源文件：{book.source_path}<br/>翻译模型：{book.model}<br/>提供方：{book.provider}",
            note_body_style,
        )
    )
    if book.estimated_cost_usd is not None:
        story.append(
            Paragraph(f"本次翻译估算成本：${book.estimated_cost_usd:.6f}", note_body_style)
        )
    story.append(PageBreak())

    story.append(NextPageTemplate("body"))
    story.append(Paragraph("目录", toc_heading_style))
    toc = TableOfContents()
    toc.levelStyles = [toc_level_style]
    story.append(toc)
    story.append(PageBreak())

    for index, chapter in enumerate(book.chapters):
        story.append(Paragraph(chapter.source_title, chapter_source_style))
        heading = Paragraph(chapter.display_title, chapter_title_style)
        heading._toc_level = 0
        heading._chapter_title = chapter.display_title
        story.append(heading)
        story.append(Spacer(1, 4 * mm))

        for block in chapter.blocks:
            if block.kind == "section_heading":
                story.append(Paragraph(block.text, section_heading_style))
            else:
                story.append(Paragraph(block.text, body_style))

        if index != len(book.chapters) - 1:
            story.append(PageBreak())

    class BookDocTemplate(BaseDocTemplate):
        def __init__(self, filename: str) -> None:
            super().__init__(
                filename,
                pagesize=A5,
                leftMargin=margins["left"],
                rightMargin=margins["right"],
                topMargin=margins["top"],
                bottomMargin=margins["bottom"],
                title=cover_title_zh,
                author=cover_author,
            )
            frame = Frame(
                self.leftMargin,
                self.bottomMargin,
                self.width,
                self.height,
                id="normal",
            )
            self.current_chapter_title = ""
            self.addPageTemplates(
                [
                    PageTemplate(id="front", frames=[frame], onPage=self._draw_front),
                    PageTemplate(id="body", frames=[frame], onPage=self._draw_body),
                ]
            )

        def afterFlowable(self, flowable: Any) -> None:
            if hasattr(flowable, "_chapter_title"):
                self.current_chapter_title = flowable._chapter_title
            if hasattr(flowable, "_toc_level"):
                self.notify("TOCEntry", (flowable._toc_level, flowable.getPlainText(), self.page))

        def _draw_front(self, canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setStrokeColor(palette["line"])
            canvas.line(
                self.leftMargin,
                page_height - 12 * mm,
                page_width - self.rightMargin,
                page_height - 12 * mm,
            )
            canvas.restoreState()

        def _draw_body(self, canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setStrokeColor(palette["line"])
            canvas.line(
                self.leftMargin,
                page_height - 12 * mm,
                page_width - self.rightMargin,
                page_height - 12 * mm,
            )
            canvas.setFont(fonts["sans"], 8.5)
            canvas.setFillColor(palette["muted"])
            canvas.drawString(self.leftMargin, page_height - 9 * mm, cover_title_en)
            canvas.drawRightString(
                page_width - self.rightMargin,
                page_height - 9 * mm,
                _truncate_for_header(self.current_chapter_title),
            )
            canvas.setFont(fonts["sans"], 8.5)
            canvas.drawCentredString(page_width / 2, 8 * mm, str(canvas.getPageNumber()))
            canvas.restoreState()

    doc = BookDocTemplate(str(output_path))
    doc.multiBuild(story)


def _split_raw_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    for raw_block in re.split(r"\n\s*\n+", text.replace("\r\n", "\n")):
        lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
        if lines:
            blocks.append(lines)
    return blocks


def _clean_block_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        value = re.sub(r"^#{1,6}\s*", "", line).strip()
        if not value:
            continue
        if re.fullmatch(r"\d+", value):
            continue
        cleaned.append(value)
    return cleaned


def _looks_like_chapter_heading(text: str) -> bool:
    if text.startswith(("第", "PART", "Part")) and any(
        token in text for token in ("章", "部分", "Chapter", "PART")
    ):
        return True
    return False


def _looks_like_section_heading(text: str) -> bool:
    if _is_book_title(text) or _looks_like_chapter_heading(text):
        return True
    if len(text) <= 24 and not re.search(r"[。！？；.!?;:]$", text):
        return True
    if text.isupper() and len(text) <= 80:
        return True
    return False


def _is_book_title(text: str) -> bool:
    return text.startswith("《") and text.endswith("》")


def _parse_title_and_author(stem: str) -> tuple[str, str | None]:
    match = re.match(r"^(?P<title>.+?)\s*\((?P<author>[^()]+)\)$", stem)
    if not match:
        return stem, None
    return match.group("title").strip(), match.group("author").strip()


def _truncate_for_header(text: str, max_length: int = 22) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _register_book_fonts(pdfmetrics: Any, TTFont: Any) -> dict[str, str]:
    font_candidates = {
        "title": [
            ("BookTitle", Path(r"C:\Windows\Fonts\STZHONGS.TTF")),
            ("BookTitle", Path(r"C:\Windows\Fonts\simsunb.ttf")),
        ],
        "body": [
            ("BookBody", Path(r"C:\Windows\Fonts\STSONG.TTF")),
            ("BookBody", Path(r"C:\Windows\Fonts\simsun.ttc")),
        ],
        "sans": [
            ("BookSans", Path(r"C:\Windows\Fonts\msyh.ttc")),
            ("BookSans", Path(r"C:\Windows\Fonts\msyhbd.ttc")),
        ],
    }
    registered: dict[str, str] = {}

    for role, candidates in font_candidates.items():
        for font_name, font_path in candidates:
            if not font_path.exists():
                continue
            try:
                if font_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                registered[role] = font_name
                break
            except Exception:
                continue
        if role not in registered:
            raise RuntimeError(f"Unable to register a usable font for {role}.")

    return registered
