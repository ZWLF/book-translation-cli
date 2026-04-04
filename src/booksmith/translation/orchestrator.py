from __future__ import annotations

import asyncio

from booksmith.models import Chunk, TranslationRequest, TranslationResult
from booksmith.providers.base import BaseProvider
from booksmith.translation.retries import retry_async


async def translate_chunks(
    *,
    book_title: str,
    chunks: list[Chunk],
    provider: BaseProvider,
    glossary: dict[str, str],
    name_map: dict[str, str],
    max_concurrency: int,
    max_attempts: int,
) -> tuple[list[TranslationResult], list[dict[str, object]]]:
    semaphore = asyncio.Semaphore(max_concurrency)
    results: list[TranslationResult] = []
    errors: list[dict[str, object]] = []

    async def worker(chunk: Chunk) -> None:
        async with semaphore:
            request = TranslationRequest(
                book_title=book_title,
                chapter_title=chunk.chapter_title,
                chunk_index=chunk.chunk_index,
                source_text=chunk.source_text,
                chunk_id=chunk.chunk_id,
                glossary=glossary,
                name_map=name_map,
            )

            async def op():
                return await provider.translate(request)

            try:
                result, attempts = await retry_async(op, max_attempts=max_attempts)
                result.attempt_count = attempts
                results.append(result)
            except Exception as error:
                errors.append(
                    {
                        "chunk_id": chunk.chunk_id,
                        "chapter_id": chunk.chapter_id,
                        "chapter_title": chunk.chapter_title,
                        "chunk_index": chunk.chunk_index,
                        "error_type": error.__class__.__name__,
                        "error_message": str(error),
                        "attempts": max_attempts,
                    }
                )

    await asyncio.gather(*(worker(chunk) for chunk in chunks))
    return results, errors
