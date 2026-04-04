from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from booksmith.output.polished_pdf import (
    PrintableBook,
    PrintableChapter,
    _build_header_title,
    _build_toc_label_html,
    _classify_title_kind,
    _contains_chinese,
    _preferred_chapter_title_zh,
    _tighten_mixed_text_spacing,
)
from booksmith.state.workspace import Workspace
from booksmith.translation.retries import retry_async

TitleTranslator = Callable[[str, str], Awaitable[str]]

_TITLE_SYSTEM_PROMPT = (
    "You translate English book section titles into concise, natural Simplified Chinese "
    "for a professionally typeset Chinese edition. Return only the Chinese title on one line. "
    "Do not add explanation, bullets, numbering, or quotes unless the source title includes them."
)


async def enrich_missing_titles(
    *,
    book: PrintableBook,
    workspace: Workspace | None,
    translator: TitleTranslator | None = None,
    provider_name: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_concurrency: int = 5,
    max_attempts: int = 4,
) -> PrintableBook:
    overrides = workspace.read_title_translations() if workspace else {}
    enriched_book = _apply_title_overrides(book, overrides)
    pending = [
        chapter
        for chapter in enriched_book.chapters
        if not chapter.title_zh and chapter.title_en
    ]
    if not pending:
        return enriched_book

    if translator is None:
        if not provider_name or not model or not api_key:
            return enriched_book
        translator = _build_title_translator(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
        )

    semaphore = asyncio.Semaphore(max_concurrency)
    updates: dict[str, str] = {}

    async def worker(chapter: PrintableChapter) -> None:
        async with semaphore:
            try:
                async def op() -> str:
                    return await translator(chapter.title_en, book.title_en)

                translated_text, _attempts = await retry_async(op, max_attempts=max_attempts)
                normalized = _normalize_title_translation(str(translated_text))
                if normalized:
                    updates[chapter.chapter_id] = normalized
            except Exception:
                return

    await asyncio.gather(*(worker(chapter) for chapter in pending))
    if not updates:
        return enriched_book

    merged = {**overrides, **updates}
    if workspace:
        workspace.write_title_translations(merged)
    return _apply_title_overrides(book, merged)


def _apply_title_overrides(book: PrintableBook, overrides: dict[str, str]) -> PrintableBook:
    chapters: list[PrintableChapter] = []
    for chapter in book.chapters:
        resolved_title_zh = _preferred_chapter_title_zh(
            chapter.title_en,
            overrides.get(chapter.chapter_id) or chapter.title_zh,
        )
        chapters.append(
            PrintableChapter(
                chapter_id=chapter.chapter_id,
                chapter_index=chapter.chapter_index,
                source_title=chapter.source_title,
                title_kind=_classify_title_kind(
                    chapter.title_en,
                    resolved_title_zh,
                ),
                title_en=chapter.title_en,
                title_zh=resolved_title_zh,
                header_title=_build_header_title(
                    chapter.title_en,
                    resolved_title_zh,
                ),
                toc_label_html=_build_toc_label_html(
                    chapter.title_en,
                    resolved_title_zh,
                ),
                blocks=chapter.blocks,
            )
        )
    return PrintableBook(
        book_id=book.book_id,
        title_en=book.title_en,
        title_zh=book.title_zh,
        author=book.author,
        source_path=book.source_path,
        provider=book.provider,
        model=book.model,
        estimated_cost_usd=book.estimated_cost_usd,
        chapters=chapters,
    )


def _normalize_title_translation(text: str) -> str | None:
    for raw_line in text.replace("\r\n", "\n").splitlines():
        line = raw_line.strip().replace("**", "").replace("__", "")
        line = line.strip("`\"'“”")
        if not line:
            continue
        if line.startswith(("标题：", "翻译：", "译文：")):
            line = line.split("：", 1)[1].strip()
        line = _tighten_mixed_text_spacing(line)
        if _contains_chinese(line):
            return line
    return None


def _build_title_translator(
    *,
    provider_name: str,
    model: str,
    api_key: str,
) -> TitleTranslator:
    async def translate_with_openai(title_en: str, book_title: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _TITLE_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": _build_title_user_prompt(
                                book_title=book_title,
                                title_en=title_en,
                            ),
                        },
                    ],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

    async def translate_with_gemini(title_en: str, book_title: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": _TITLE_SYSTEM_PROMPT
                                    + "\n\n"
                                    + _build_title_user_prompt(
                                        book_title=book_title,
                                        title_en=title_en,
                                    )
                                }
                            ]
                        }
                    ],
                    "generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}},
                },
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    if provider_name == "openai":
        return translate_with_openai
    if provider_name == "gemini":
        return translate_with_gemini
    raise ValueError(f"Unsupported provider: {provider_name}")


def _build_title_user_prompt(*, book_title: str, title_en: str) -> str:
    return (
        f"Book title: {book_title}\n"
        f"English heading: {title_en}\n\n"
        "Translate the heading into concise natural Simplified Chinese "
        "suitable for a printed book. "
        "Return only the Chinese heading on one line."
    )
