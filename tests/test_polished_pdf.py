from pathlib import Path

from pypdf import PdfReader

from book_translator.models import Chunk, Manifest, PublishingChapterArtifact, TranslationResult
from book_translator.output.polished_pdf import (
    PrintableBlock,
    PrintableBook,
    PrintableChapter,
    _parse_title_and_author,
    build_printable_book,
    build_printable_book_from_artifacts,
    render_polished_pdf,
    running_header_texts,
)


def _chunk(
    *,
    chunk_id: str,
    chapter_id: str,
    chapter_index: int,
    chunk_index: int,
    title: str,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        chapter_id=chapter_id,
        chapter_index=chapter_index,
        chunk_index=chunk_index,
        chapter_title=title,
        source_text="source",
        source_token_estimate=1,
    )


def _translation(chunk_id: str, text: str) -> TranslationResult:
    return TranslationResult(
        chunk_id=chunk_id,
        translated_text=text,
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        attempt_count=1,
        latency_ms=10,
        input_tokens=1,
        output_tokens=1,
        estimated_cost_usd=0.0,
    )


def _manifest() -> Manifest:
    return Manifest(
        book_id="sample-book",
        source_path=r"H:\books\Sample Book (Author Name).pdf",
        source_fingerprint="fingerprint",
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        config_fingerprint="config",
    )


def _printable_chapter(
    *,
    index: int,
    title_en: str,
    title_zh: str | None = None,
    title_kind: str = "chapter",
    body_text: str = "Body text for testing.",
) -> PrintableChapter:
    header_title = title_zh or title_en
    toc_label_html = (
        f"{title_zh}<br/><font size='9' color='#6B6259'>{title_en}</font>"
        if title_zh
        else title_en
    )
    return PrintableChapter(
        chapter_id=f"chapter-{index}",
        chapter_index=index,
        source_title=title_en,
        title_kind=title_kind,
        title_en=title_en,
        title_zh=title_zh,
        header_title=header_title,
        toc_label_html=toc_label_html,
        blocks=[PrintableBlock(kind="paragraph", text=body_text)],
    )


def test_build_printable_book_normalizes_wrapped_lines_and_headings() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        ),
        _chunk(
            chunk_id="chapter-2-0",
            chapter_id="chapter-2",
            chapter_index=1,
            chunk_index=0,
            title="Chapter Two",
        ),
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "《示例图书》",
                    "",
                    "### 第一章：中文标题",
                    "",
                    "这是第一行",
                    "继续一段。",
                    "",
                    "42",
                    "",
                    "小节标题",
                    "",
                    "这里有正文。",
                ]
            ),
        ),
        "chapter-2-0": _translation("chapter-2-0", "   "),
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.123456},
        chunks=chunks,
        translations=translations,
    )

    assert book.title_en == "Sample Book"
    assert book.title_zh == "《示例图书》"
    assert book.author == "Author Name"
    assert len(book.chapters) == 1

    chapter = book.chapters[0]
    assert chapter.source_title == "Chapter One"
    assert chapter.title_kind == "chapter"
    assert chapter.title_en == "Chapter One"
    assert chapter.title_zh == "第一章：中文标题"
    assert chapter.header_title == "第一章：中文标题"
    assert "第一章：中文标题" in chapter.toc_label_html
    assert "Chapter One" in chapter.toc_label_html
    assert [block.kind for block in chapter.blocks] == ["paragraph", "section_heading", "paragraph"]
    assert chapter.blocks[0].text == "这是第一行继续一段。"
    assert chapter.blocks[1].text == "小节标题"
    assert chapter.blocks[2].text == "这里有正文。"


def test_build_printable_book_classifies_part_titles_for_bilingual_toc() -> None:
    chunks = [
        _chunk(
            chunk_id="part-1-0",
            chapter_id="part-1",
            chapter_index=0,
            chunk_index=0,
            title="Part I",
        )
    ]
    translations = {
        "part-1-0": _translation(
            "part-1-0",
            "\n".join(
                [
                    "### 第一部分：成为多行星物种",
                    "",
                    "这是分部导语。",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert chapter.title_kind == "part"
    assert chapter.title_en == "Part I"
    assert chapter.title_zh == "第一部分：成为多行星物种"
    assert chapter.header_title == "第一部分：成为多行星物种"
    assert "第一部分：成为多行星物种" in chapter.toc_label_html
    assert "Part I" in chapter.toc_label_html


def test_build_printable_book_merges_two_line_part_titles() -> None:
    chunks = [
        _chunk(
            chunk_id="part-1-0",
            chapter_id="part-1",
            chapter_index=0,
            chunk_index=0,
            title="Part I: Pursue Purpose",
        )
    ]
    translations = {
        "part-1-0": _translation(
            "part-1-0",
            "\n".join(
                [
                    "第一部分：",
                    "追求使命",
                    "",
                    "这是分部导语。",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert chapter.title_kind == "part"
    assert chapter.title_zh == "第一部分：追求使命"
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert chapter.blocks[0].text == "这是分部导语。"


def test_build_printable_book_falls_back_to_english_only_title_when_no_chinese_heading() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="If You Love Life, Protect It",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "这是一段没有单独中文标题的正文。",
                    "它应该直接进入正文排版。",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert chapter.title_kind == "chapter"
    assert chapter.title_en == "If You Love Life, Protect It"
    assert chapter.title_zh is None
    assert chapter.header_title == "If You Love Life, Protect It"
    assert chapter.toc_label_html == "If You Love Life, Protect It"


def test_build_printable_book_converts_reference_entries_and_strips_markdown() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "以下是该文本的简体中文翻译：",
                    "",
                    "35",
                    "“第一条参考资料”。",
                    "36",
                    "“第二条参考资料”。",
                    "",
                    "***",
                    "",
                    "**反馈重于感受**",
                    "",
                    "这是正文第一行",
                    "这是正文第二行。",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == [
        "reference",
        "reference",
        "section_heading",
        "paragraph",
    ]
    assert chapter.blocks[0].text == "35 “第一条参考资料”。"
    assert chapter.blocks[1].text == "36 “第二条参考资料”。"
    assert chapter.blocks[2].text == "反馈重于感受"
    assert chapter.blocks[3].text == "这是正文第一行这是正文第二行。"


def test_build_printable_book_marks_short_quoted_blocks_as_callouts() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "Life is too short for long-term grudges.",
                    "459",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == ["callout"]
    assert "Life is too short for long-term grudges." in chapter.blocks[0].text
    assert "459" in chapter.blocks[0].text
    assert "2F5BD2" in chapter.blocks[0].text


def test_build_printable_book_appends_inline_citations_to_regular_paragraphs() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "Instead of fighting during a critical time, I thought it was best to concede.",
                    "I had to focus on keeping the company alive and preserving the team.",
                    "456",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert "I thought it was best to concede." in chapter.blocks[0].text
    assert "456" in chapter.blocks[0].text
    assert "2F5BD2" in chapter.blocks[0].text
    assert "<super>456</super>" in chapter.blocks[0].text


def test_build_printable_book_from_artifacts_splits_single_newline_citation_sequences() -> None:
    artifact = PublishingChapterArtifact(
        chapter_id="chapter-1",
        chapter_index=0,
        title="From Exile to Exit",
        text="\n".join(
            [
                "I thought it was best to concede during a difficult transition.",
                "456",
                "Life is too short for long-term grudges.",
                "459",
                "I put almost all of my money into the next game.",
            ]
        ),
    )

    book = build_printable_book_from_artifacts(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chapters=[artifact],
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == ["paragraph", "callout", "paragraph"]
    assert "<super>456</super>" in chapter.blocks[0].text
    assert "<super>459</super>" in chapter.blocks[1].text
    assert "Life is too short for long-term grudges." in chapter.blocks[1].text


def test_build_printable_book_from_artifacts_styles_inline_sentence_citations() -> None:
    artifact = PublishingChapterArtifact(
        chapter_id="chapter-1",
        chapter_index=0,
        title="The Only One Crazy Enough for Space",
        text=(
            "我们并没有失去探索的意愿；人们只是认为没有前进的道路。584 "
            "必须有一些事情来激励我们——让我们为自己身为人类的一员而感到自豪。585 "
            "阿波罗登月就是一个例子。586"
        ),
    )

    book = build_printable_book_from_artifacts(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chapters=[artifact],
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert "<super>584</super>" in chapter.blocks[0].text
    assert "<super>585</super>" in chapter.blocks[0].text
    assert "<super>586</super>" in chapter.blocks[0].text
    assert "2F5BD2" in chapter.blocks[0].text


def test_build_printable_book_from_artifacts_restores_numbered_method_lists() -> None:
    artifact = PublishingChapterArtifact(
        chapter_id="chapter-69",
        chapter_index=0,
        title="The 69 Core Musk Methods",
        text="\n\n".join(
            [
                "这些方法被选为促使埃隆及其公司取得成功的根本理念。它们已被编辑或改写为简短且令人难忘的准则。",
                "\n".join(
                    [
                        "1. 你拥有的能力远超你的想象。",
                        "2. 普通人完全可以选择变得不普通。",
                        "3. 你可以自学任何东西。",
                    ]
                ),
            ]
        ),
    )

    book = build_printable_book_from_artifacts(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chapters=[artifact],
        title_overrides={"chapter-69": "马斯克核心法则69条"},
    )

    chapter = book.chapters[0]
    assert chapter.title_zh == "马斯克的 69 条核心法则"
    assert [block.kind for block in chapter.blocks] == [
        "paragraph",
        "numbered_item",
        "numbered_item",
        "numbered_item",
    ]
    assert chapter.blocks[1].text.startswith("1. ")
    assert chapter.blocks[2].text.startswith("2. ")
    assert chapter.blocks[3].text.startswith("3. ")


def test_build_printable_book_from_artifacts_keeps_numeric_leading_body_blocks() -> None:
    artifact = PublishingChapterArtifact(
        chapter_id="chapter-1",
        chapter_index=0,
        title="Chapter One",
        text="\n".join(
            [
                "2024",
                "was the hardest year.",
            ]
        ),
    )

    book = build_printable_book_from_artifacts(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chapters=[artifact],
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert chapter.blocks[0].text == "2024 was the hardest year."


def test_build_printable_book_treats_short_cited_lines_without_punctuation_as_callouts() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "Move fast",
                    "456",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == ["callout"]
    assert "<super>456</super>" in chapter.blocks[0].text
    assert "Move fast" in chapter.blocks[0].text


def test_build_printable_book_strips_prompt_echo_wrappers() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "本书：示例图书 章节：第一章：中文标题 分块索引：0",
                    "",
                    "真正的正文从这里开始。",
                    "第二句也应该保留下来。",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert chapter.blocks[0].text == "真正的正文从这里开始。第二句也应该保留下来。"


def test_build_printable_book_strips_additional_prompt_echo_variants() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Engineering Is Magic",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "以下是为您翻译的简体中文内容：",
                    "",
                    "这本书：埃隆·马斯克传：使命与成功指南（作者：Eric Jorgenson）",
                    "原文片段索引：0",
                    "",
                    "工程学在任何实际意义上都是魔法。",
                    "谁不想成为一名魔术师呢？",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert chapter.title_zh is None
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert chapter.blocks[0].text == "工程学在任何实际意义上都是魔法。谁不想成为一名魔术师呢？"


def test_build_printable_book_strips_translation_marker_titles() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Seek the Nature of the Universe",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "翻译如下：",
                    "",
                    "我不知道生命的意义是什么。",
                    "但我认为我们应该继续探索。",
                ]
            ),
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    chapter = book.chapters[0]
    assert chapter.title_zh is None
    assert chapter.header_title == "Seek the Nature of the Universe"
    assert [block.kind for block in chapter.blocks] == ["paragraph"]
    assert chapter.blocks[0].text == "我不知道生命的意义是什么。但我认为我们应该继续探索。"


def test_build_printable_book_applies_title_overrides_and_tightens_mixed_spacing() -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Obsess for Success",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "我将大部分 Zip2 的收益投入到了 X.com，投资了 1250 万美元。",
        )
    }

    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
        title_overrides={"chapter-1": "痴迷于成功"},
    )

    chapter = book.chapters[0]
    assert chapter.title_zh == "痴迷于成功"
    assert chapter.header_title == "痴迷于成功"
    assert chapter.blocks[0].text == "我将大部分Zip2的收益投入到了X.com，投资了1250万美元。"


def test_running_header_texts_avoids_left_right_overlap() -> None:
    left_even, right_even = running_header_texts(
        page_number=120,
        book_title="The Book of Elon A Guide to Purpose and Success",
        chapter_title="第一章：成为多行星物种是一场进化层级的事件",
    )
    left_odd, right_odd = running_header_texts(
        page_number=121,
        book_title="The Book of Elon A Guide to Purpose and Success",
        chapter_title="第一章：成为多行星物种是一场进化层级的事件",
    )

    assert left_even == "The Book of Elon"
    assert right_even == ""
    assert left_odd == ""
    assert right_odd == "第一章：成为多行星物种是一场进化层级的事件"


def test_render_polished_pdf_writes_pdf_file(tmp_path: Path) -> None:
    chunks = [
        _chunk(
            chunk_id="chapter-1-0",
            chapter_id="chapter-1",
            chapter_index=0,
            chunk_index=0,
            title="Chapter One",
        )
    ]
    translations = {
        "chapter-1-0": _translation(
            "chapter-1-0",
            "\n".join(
                [
                    "《示例图书》",
                    "",
                    "### 第一章：中文标题",
                    "",
                    "这里是排版后的正文。",
                ]
            ),
        )
    }
    book = build_printable_book(
        manifest=_manifest(),
        summary={"estimated_cost_usd": 0.0},
        chunks=chunks,
        translations=translations,
    )

    output_path = tmp_path / "translated.pdf"
    render_polished_pdf(book, output_path)

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF")
    assert output_path.stat().st_size > 0


def test_render_polished_pdf_hides_running_headers_on_toc_pages(tmp_path: Path) -> None:
    chapters = [
        _printable_chapter(
            index=0,
            title_en="Part I",
            title_zh="第一部分：成为多行星物种",
            title_kind="part",
        )
    ] + [
        _printable_chapter(
            index=index,
            title_en=f"Chapter {index}",
            title_zh=f"第{index}章：中文标题",
        )
        for index in range(1, 80)
    ]
    book = PrintableBook(
        book_id="sample-book",
        title_en="Sample Book",
        title_zh="示例图书",
        author="Author Name",
        source_path=r"H:\books\Sample Book (Author Name).pdf",
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        estimated_cost_usd=0.0,
        chapters=chapters,
    )

    output_path = tmp_path / "toc.pdf"
    render_polished_pdf(book, output_path)

    reader = PdfReader(str(output_path))
    toc_page_text = " ".join((reader.pages[3].extract_text() or "").split())
    combined_toc_text = " ".join(
        " ".join((reader.pages[index].extract_text() or "").split())
        for index in range(2, min(6, len(reader.pages)))
    )

    assert "Chapter 13" in toc_page_text
    assert "第一部分：成为多行星物种" in combined_toc_text
    assert "Part I" in combined_toc_text
    assert not toc_page_text.startswith("Sample Book 4")


def test_render_polished_pdf_restores_running_headers_after_opening_page(tmp_path: Path) -> None:
    long_body = " ".join(["连续正文测试。"] * 1800)
    chapters = [
        _printable_chapter(
            index=0,
            title_en="Part I",
            title_zh="第一部分：成为多行星物种",
            title_kind="part",
            body_text="这是分部首页的导语。",
        ),
        _printable_chapter(
            index=1,
            title_en="If You Love Life, Protect It",
            title_zh="第一章：如果你热爱生命，就守护它",
            body_text=long_body,
        ),
    ]
    book = PrintableBook(
        book_id="sample-book",
        title_en="Sample Book",
        title_zh="示例图书",
        author="Author Name",
        source_path=r"H:\books\Sample Book (Author Name).pdf",
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        estimated_cost_usd=0.0,
        chapters=chapters,
    )

    output_path = tmp_path / "body-headers.pdf"
    render_polished_pdf(book, output_path)

    reader = PdfReader(str(output_path))
    page_texts = [" ".join((page.extract_text() or "").split()) for page in reader.pages]

    chapter_opening_page = next(
        index
        for index, text in enumerate(page_texts)
        if "If You Love Life, Protect It" in text and "第一章：如果你热爱生命，就守护它" in text
    )
    continued_body_pages = [
        index
        for index in range(chapter_opening_page + 1, len(page_texts))
        if "连续正文测试" in page_texts[index]
    ]

    assert not page_texts[chapter_opening_page].startswith("Sample Book")
    assert continued_body_pages
    assert any(
        ("Sample Book" in page_texts[index])
        or ("第一章：如果你热爱生命，就守护它" in page_texts[index])
        for index in continued_body_pages
    )
def test_render_polished_pdf_uses_publishing_front_matter(tmp_path: Path) -> None:
    output_path = tmp_path / "publishing.pdf"
    book = PrintableBook(
        book_id="sample-book",
        title_en="The Book of Elon: A Guide to Purpose and Success",
        title_zh="埃隆之书",
        author="Eric Jorgenson",
        source_path=r"H:\\books\\The Book of Elon.pdf",
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        estimated_cost_usd=0.12,
        chapters=[
            _printable_chapter(
                index=0,
                title_en="Part I",
                title_zh="第一部分",
                title_kind="part",
            )
        ],
    )

    render_polished_pdf(book, output_path, edition_label="publishing")

    extracted = "\n".join(
        (PdfReader(output_path).pages[index].extract_text() or "") for index in range(2)
    )
    assert "出版级翻译精排版" in extracted
    assert "正文内容来自出版级翻译终稿" in extracted
    assert "The Book of Elon: A Guide to Purpose and Success" in extracted
    assert "埃隆之书：使命与成功指南" in extracted
    assert "开发者：ZWLF" in extracted
    assert "Codex" in extracted
    assert "Vibe Coding" in extracted
    assert "weiliangzeng03@gmail.com" in extracted
    assert "https://github.com/ZWLF/book-translation-cli" in extracted
    assert "免费公开" in extracted
    assert "支持我的项目" in extracted
    assert "本次实际翻译成本：$0.120000" in extracted
    assert "H:\\\\books\\\\The Book of Elon.pdf" not in extracted
    assert "Weiliang Zeng" not in extracted
    assert "工程化翻译精排版" not in extracted
    assert "工程化翻译结果" not in extracted


def test_parse_title_and_author_normalizes_elon_book_title() -> None:
    title, author = _parse_title_and_author(
        "The Book of Elon A Guide to Purpose and Success (Eric Jorgenson)"
    )

    assert title == "The Book of Elon: A Guide to Purpose and Success"
    assert author == "Eric Jorgenson"
