from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from book_translator.models import Chunk, Manifest, PublishingChapterArtifact, TranslationResult


@dataclass(slots=True)
class PrintableBlock:
    kind: str
    text: str


@dataclass(slots=True)
class PrintableChapter:
    chapter_id: str
    chapter_index: int
    source_title: str
    title_kind: str
    title_en: str
    title_zh: str | None
    header_title: str
    toc_label_html: str
    blocks: list[PrintableBlock] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        return self.title_zh or self.title_en or self.source_title


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
    title_overrides: dict[str, str] | None = None,
) -> PrintableBook:
    title_en, author = _parse_title_and_author(_source_stem(manifest.source_path))
    title_overrides = title_overrides or {}
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

    return _build_printable_book_from_entries(
        manifest=manifest,
        summary=summary,
        grouped_entries=grouped,
        title_en=title_en,
        author=author,
        title_overrides=title_overrides,
    )


def build_printable_book_from_artifacts(
    *,
    manifest: Manifest,
    summary: dict[str, Any],
    chapters: list[PublishingChapterArtifact],
    title_overrides: dict[str, str] | None = None,
) -> PrintableBook:
    title_en, author = _parse_title_and_author(_source_stem(manifest.source_path))
    grouped = {
        chapter.chapter_id: {
            "chapter_id": chapter.chapter_id,
            "chapter_index": chapter.chapter_index,
            "source_title": chapter.title,
            "texts": [chapter.text],
        }
        for chapter in chapters
    }
    return _build_printable_book_from_entries(
        manifest=manifest,
        summary=summary,
        grouped_entries=grouped,
        title_en=title_en,
        author=author,
        title_overrides=title_overrides or {},
    )


def _build_printable_book_from_entries(
    *,
    manifest: Manifest,
    summary: dict[str, Any],
    grouped_entries: dict[str, dict[str, Any]],
    title_en: str,
    author: str | None,
    title_overrides: dict[str, str],
) -> PrintableBook:
    title_zh: str | None = None
    chapters: list[PrintableChapter] = []
    for entry in sorted(grouped_entries.values(), key=lambda item: item["chapter_index"]):
        combined_text = "\n\n".join(entry["texts"]).strip()
        if not combined_text:
            continue

        raw_blocks = _split_raw_blocks(combined_text)
        chapter_title_zh: str | None = None
        title_block_checked = False
        printable_blocks: list[PrintableBlock] = []

        for lines in raw_blocks:
            reference_entries = _extract_reference_entries(lines)
            if reference_entries:
                title_block_checked = True
                printable_blocks.extend(
                    PrintableBlock(kind="reference", text=entry) for entry in reference_entries
                )
                continue

            cleaned_lines = _clean_block_lines(lines)
            if not cleaned_lines:
                continue

            if title_zh is None and _is_book_title(cleaned_lines[0]):
                title_zh = cleaned_lines[0]
                cleaned_lines = cleaned_lines[1:]
                if not cleaned_lines:
                    continue

            if not title_block_checked:
                chapter_title_zh, cleaned_lines = _extract_chapter_title_zh(cleaned_lines)
                title_block_checked = True
                if not cleaned_lines:
                    continue

            if len(cleaned_lines) == 1 and _looks_like_section_heading(cleaned_lines[0]):
                printable_blocks.append(
                    PrintableBlock(
                        kind="section_heading",
                        text=_tighten_mixed_text_spacing(cleaned_lines[0]),
                    )
                )
                continue

            printable_blocks.append(
                PrintableBlock(
                    kind="paragraph",
                    text=_tighten_mixed_text_spacing("".join(cleaned_lines)),
                )
            )

        if not printable_blocks:
            continue

        chapters.append(
            PrintableChapter(
                chapter_id=entry["chapter_id"],
                chapter_index=entry["chapter_index"],
                source_title=entry["source_title"],
                title_kind=_classify_title_kind(
                    entry["source_title"],
                    title_overrides.get(entry["chapter_id"]) or chapter_title_zh,
                ),
                title_en=entry["source_title"],
                title_zh=title_overrides.get(entry["chapter_id"]) or chapter_title_zh,
                header_title=_build_header_title(
                    entry["source_title"],
                    title_overrides.get(entry["chapter_id"]) or chapter_title_zh,
                ),
                toc_label_html=_build_toc_label_html(
                    entry["source_title"],
                    title_overrides.get(entry["chapter_id"]) or chapter_title_zh,
                ),
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
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
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

    fonts = _register_book_fonts(pdfmetrics, TTFont, UnicodeCIDFont)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    page_width, page_height = A5
    margins = {
        "left": 20 * mm,
        "right": 20 * mm,
        "top": 20 * mm,
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
    part_title_style = ParagraphStyle(
        "PartTitleZh",
        parent=styles["Heading1"],
        fontName=fonts["title"],
        fontSize=19.5,
        leading=28,
        alignment=TA_CENTER,
        textColor=palette["ink"],
        spaceAfter=6,
    )
    part_source_style = ParagraphStyle(
        "PartTitleEn",
        parent=styles["BodyText"],
        fontName=fonts["sans"],
        fontSize=9.5,
        leading=14,
        alignment=TA_CENTER,
        textColor=palette["muted"],
        spaceAfter=18,
    )
    chapter_title_style = ParagraphStyle(
        "ChapterTitleZh",
        parent=styles["Heading1"],
        fontName=fonts["title"],
        fontSize=17.2,
        leading=24,
        alignment=TA_CENTER,
        textColor=palette["ink"],
        spaceAfter=5,
    )
    chapter_source_style = ParagraphStyle(
        "ChapterTitleEn",
        parent=styles["BodyText"],
        fontName=fonts["sans"],
        fontSize=9.2,
        leading=13,
        alignment=TA_CENTER,
        textColor=palette["muted"],
        spaceAfter=14,
    )
    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading3"],
        fontName=fonts["title"],
        fontSize=11.8,
        leading=16,
        textColor=palette["accent"],
        alignment=TA_LEFT,
        spaceBefore=10,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "BodyZh",
        parent=styles["BodyText"],
        fontName=fonts["body"],
        fontSize=10.2,
        leading=18.6,
        textColor=palette["ink"],
        alignment=TA_JUSTIFY,
        firstLineIndent=20,
        spaceAfter=6,
    )
    body_mixed_style = ParagraphStyle(
        "BodyZhMixed",
        parent=body_style,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    reference_style = ParagraphStyle(
        "ReferenceZh",
        parent=styles["BodyText"],
        fontName=fonts["body"],
        fontSize=8.6,
        leading=12.4,
        textColor=palette["muted"],
        alignment=TA_LEFT,
        firstLineIndent=0,
        leftIndent=6,
        spaceAfter=3,
        splitLongWords=False,
    )
    toc_part_style = ParagraphStyle(
        "TOCPart",
        parent=styles["BodyText"],
        fontName=fonts["body"],
        fontSize=11,
        leading=18,
        textColor=palette["ink"],
        leftIndent=0,
        firstLineIndent=0,
        spaceBefore=6,
        spaceAfter=7,
    )
    toc_chapter_style = ParagraphStyle(
        "TOCChapter",
        parent=styles["BodyText"],
        fontName=fonts["body"],
        fontSize=10.2,
        leading=15,
        textColor=palette["ink"],
        leftIndent=12,
        firstLineIndent=0,
        spaceBefore=2,
        spaceAfter=3,
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

    story.append(NextPageTemplate("toc"))
    story.append(Paragraph("目录", toc_heading_style))
    toc = TableOfContents()
    toc.levelStyles = [toc_part_style, toc_chapter_style]
    story.append(toc)
    if book.chapters:
        story.append(NextPageTemplate(_opening_template_id(book.chapters[0])))
        story.append(PageBreak())

    for index, chapter in enumerate(book.chapters):
        title_style = part_title_style if chapter.title_kind == "part" else chapter_title_style
        source_style = part_source_style if chapter.title_kind == "part" else chapter_source_style
        top_spacing_mm = 18 if chapter.title_kind == "part" else 9
        title_spacing_mm = 8 if chapter.title_kind == "part" else 4

        story.append(Spacer(1, top_spacing_mm * mm))
        heading = Paragraph(chapter.display_title, title_style)
        heading._toc_level = 0 if chapter.title_kind == "part" else 1
        heading._chapter_title = chapter.header_title
        heading._toc_label_html = chapter.toc_label_html
        story.append(heading)
        if chapter.title_zh and chapter.title_en:
            story.append(Paragraph(chapter.title_en, source_style))
        story.append(Spacer(1, title_spacing_mm * mm))

        for block in chapter.blocks:
            if block.kind == "section_heading":
                story.append(Paragraph(block.text, section_heading_style))
            elif block.kind == "reference":
                story.append(Paragraph(block.text, reference_style))
            else:
                paragraph_style = (
                    body_mixed_style if _has_mixed_script_content(block.text) else body_style
                )
                story.append(Paragraph(block.text, paragraph_style))

        if index != len(book.chapters) - 1:
            story.append(NextPageTemplate(_opening_template_id(book.chapters[index + 1])))
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
                    PageTemplate(id="toc", frames=[frame], onPage=self._draw_toc),
                    PageTemplate(
                        id="part-opening",
                        frames=[frame],
                        onPage=self._draw_opening,
                        autoNextPageTemplate="body",
                    ),
                    PageTemplate(
                        id="chapter-opening",
                        frames=[frame],
                        onPage=self._draw_opening,
                        autoNextPageTemplate="body",
                    ),
                    PageTemplate(id="body", frames=[frame], onPage=self._draw_body),
                ]
            )

        def afterFlowable(self, flowable: Any) -> None:
            if hasattr(flowable, "_chapter_title"):
                self.current_chapter_title = flowable._chapter_title
            if hasattr(flowable, "_toc_level"):
                toc_label = getattr(flowable, "_toc_label_html", flowable.getPlainText())
                self.notify("TOCEntry", (flowable._toc_level, toc_label, self.page))

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

        def _draw_toc(self, canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setStrokeColor(palette["line"])
            canvas.line(
                self.leftMargin,
                page_height - 12 * mm,
                page_width - self.rightMargin,
                page_height - 12 * mm,
            )
            canvas.setFont(fonts["sans"], 8.5)
            canvas.drawCentredString(page_width / 2, 8 * mm, str(canvas.getPageNumber()))
            canvas.restoreState()

        def _draw_opening(self, canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setStrokeColor(palette["line"])
            canvas.line(
                self.leftMargin,
                page_height - 12 * mm,
                page_width - self.rightMargin,
                page_height - 12 * mm,
            )
            canvas.setFont(fonts["sans"], 8.5)
            canvas.drawCentredString(page_width / 2, 8 * mm, str(canvas.getPageNumber()))
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
            left_header, right_header = running_header_texts(
                page_number=canvas.getPageNumber(),
                book_title=cover_title_en,
                chapter_title=self.current_chapter_title,
            )
            if left_header:
                canvas.drawString(self.leftMargin, page_height - 9 * mm, left_header)
            if right_header:
                canvas.drawRightString(
                    page_width - self.rightMargin,
                    page_height - 9 * mm,
                    right_header,
                )
            canvas.setFont(fonts["sans"], 8.5)
            canvas.drawCentredString(page_width / 2, 8 * mm, str(canvas.getPageNumber()))
            canvas.restoreState()

    doc = BookDocTemplate(str(output_path))
    doc.multiBuild(story)


def _opening_template_id(chapter: PrintableChapter) -> str:
    if chapter.title_kind == "part":
        return "part-opening"
    return "chapter-opening"


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
        value = _normalize_line(line)
        if not value:
            continue
        cleaned.append(value)
    return cleaned


def _extract_chapter_title_zh(lines: list[str]) -> tuple[str | None, list[str]]:
    if not lines:
        return None, lines

    first_line = lines[0]
    if _looks_like_chapter_heading(first_line) and _contains_chinese(first_line):
        remainder = lines[1:]
        if remainder and first_line.rstrip().endswith(("：", ":")):
            second_line = remainder[0]
            if _looks_like_translated_title_candidate(second_line):
                return f"{first_line}{second_line}", remainder[1:]
        return first_line, remainder

    if _looks_like_translated_title_candidate(first_line):
        return first_line, lines[1:]

    return None, lines


def _classify_title_kind(title_en: str, title_zh: str | None) -> str:
    if not title_en and not title_zh:
        return "fallback"
    if title_en.lower().startswith("part "):
        return "part"
    if title_zh and title_zh.startswith("第") and "部分" in title_zh:
        return "part"
    return "chapter"


def _build_header_title(title_en: str, title_zh: str | None) -> str:
    return title_zh or title_en or "未命名章节"


def _build_toc_label_html(title_en: str, title_zh: str | None) -> str:
    escaped_title_en = xml_escape(title_en)
    if not title_zh:
        return escaped_title_en
    escaped_title_zh = xml_escape(title_zh)
    return (
        f"{escaped_title_zh}<br/>"
        f"<font size='8.5' color='#6B6259'>{escaped_title_en}</font>"
    )


def _tighten_mixed_text_spacing(text: str) -> str:
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[A-Za-z0-9@#&])", "", text)
    value = re.sub(r"(?<=[A-Za-z0-9@#&])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[（(])", "", value)
    value = re.sub(r"(?<=[）)])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"(?<=[A-Za-z])\s+(?=\d)", " ", value)
    value = re.sub(r"(?<=\d)\s+(?=[A-Za-z])", " ", value)
    return value


def _has_mixed_script_content(text: str) -> bool:
    return _contains_chinese(text) and bool(re.search(r"[A-Za-z0-9]", text))


def _extract_reference_entries(lines: list[str]) -> list[str]:
    entries: list[str] = []
    current_number: str | None = None
    current_parts: list[str] = []

    for line in lines:
        value = _normalize_line(line, keep_number_line=True)
        if not value:
            continue
        if re.fullmatch(r"\d+", value):
            if current_number and current_parts:
                entries.append(f"{current_number} {' '.join(current_parts)}".strip())
            current_number = value
            current_parts = []
            continue
        if current_number is None:
            return []
        current_parts.append(value)

    if current_number and current_parts:
        entries.append(f"{current_number} {' '.join(current_parts)}".strip())

    if len(entries) < 2:
        return []
    return entries


def _normalize_line(line: str, *, keep_number_line: bool = False) -> str:
    value = re.sub(r"^#{1,6}\s*", "", line).strip()
    if _is_translation_preface(value):
        return ""
    if _is_prompt_wrapper(value):
        return ""
    if _is_horizontal_rule(value):
        return ""
    value = value.replace("**", "").replace("__", "")
    value = re.sub(r"^\*(.+)\*$", r"\1", value)
    if not value:
        return ""
    if not keep_number_line and re.fullmatch(r"\d+", value):
        return ""
    return value


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


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _looks_like_translated_title_candidate(text: str) -> bool:
    candidate = text.strip()
    if not candidate or not _contains_chinese(candidate):
        return False
    if len(candidate) > 34:
        return False
    if re.search(r"[。！？；!?]$", candidate):
        return False

    visible_chars = [char for char in candidate if not char.isspace()]
    if not visible_chars:
        return False
    chinese_chars = [char for char in visible_chars if re.match(r"[\u4e00-\u9fff]", char)]
    if len(chinese_chars) < 3:
        return False
    return len(chinese_chars) / len(visible_chars) >= 0.45


def _parse_title_and_author(stem: str) -> tuple[str, str | None]:
    match = re.match(r"^(?P<title>.+?)\s*\((?P<author>[^()]+)\)$", stem)
    if not match:
        return stem, None
    return match.group("title").strip(), match.group("author").strip()


def _source_stem(source_path: str) -> str:
    if re.match(r"^[A-Za-z]:\\", source_path) or "\\" in source_path:
        return PureWindowsPath(source_path).stem
    return PurePosixPath(source_path).stem


def _truncate_for_header(text: str, max_length: int = 22) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def running_header_texts(
    *,
    page_number: int,
    book_title: str,
    chapter_title: str,
) -> tuple[str, str]:
    short_book_title = _short_book_title(book_title)
    if page_number % 2 == 0:
        return _truncate_for_header(short_book_title, max_length=18), ""
    return "", _truncate_for_header(chapter_title, max_length=22)


def _short_book_title(text: str) -> str:
    for separator in (" A Guide to ", ": ", " - ", " — ", " | "):
        if separator in text:
            return text.split(separator, maxsplit=1)[0].strip()
    return text


def _is_translation_preface(text: str) -> bool:
    if not text.startswith("以下是"):
        return False
    if "简体中文" not in text:
        return False
    return "翻译" in text or "内容" in text


def _is_prompt_wrapper(text: str) -> bool:
    if text.startswith(
        ("本书：", "这本书：", "书名：", "章节：", "分块索引：", "原文片段索引：", "翻译如下")
    ):
        return True
    if all(marker in text for marker in ("本书：", "章节：", "分块索引：")):
        return True
    if text.startswith(("本书", "这本书", "书名")) and "原文片段索引：" in text:
        return True
    return False


def _is_horizontal_rule(text: str) -> bool:
    return bool(re.fullmatch(r"[-*_]{3,}", text))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _register_book_fonts(pdfmetrics: Any, TTFont: Any, UnicodeCIDFont: Any) -> dict[str, str]:
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
            try:
                if "STSong-Light" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
                registered[role] = "STSong-Light"
            except Exception as exc:
                raise RuntimeError(f"Unable to register a usable font for {role}.") from exc

    return registered
