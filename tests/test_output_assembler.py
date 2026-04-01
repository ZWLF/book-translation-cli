from book_translator.models import Chapter, Chunk, TranslationResult
from book_translator.output.assembler import assemble_output_text


def test_assembler_skips_chapters_without_chunks() -> None:
    chapters = [
        Chapter(chapter_id="c-empty", chapter_index=0, title="Empty", text=""),
        Chapter(chapter_id="c-full", chapter_index=1, title="Full", text="Body"),
    ]
    chunks = [
        Chunk(
            chunk_id="chunk-1",
            chapter_id="c-full",
            chapter_index=1,
            chunk_index=0,
            chapter_title="Full",
            source_text="Body",
            source_token_estimate=1,
        )
    ]
    translations = {
        "chunk-1": TranslationResult(
            chunk_id="chunk-1",
            translated_text="正文",
            provider="openai",
            model="gpt-4o-mini",
            attempt_count=1,
            latency_ms=10,
            input_tokens=1,
            output_tokens=1,
            estimated_cost_usd=0.0,
        )
    }

    text = assemble_output_text(chapters, chunks, translations, failed_chunk_ids=set())

    assert "Empty" not in text
    assert "Full" in text
    assert "正文" in text
