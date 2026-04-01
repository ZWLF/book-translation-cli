import httpx
import pytest

from book_translator.models import TranslationRequest
from book_translator.providers.gemini_provider import GeminiProvider
from book_translator.providers.openai_provider import OpenAIProvider
from book_translator.translation.retries import is_retryable_exception


@pytest.mark.asyncio
async def test_openai_provider_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.openai.com/v1/chat/completions")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "你好"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 6, "total_tokens": 16},
            },
        )

    provider = OpenAIProvider(
        api_key="secret",
        model="gpt-4o-mini",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await provider.translate(
        TranslationRequest(
            book_title="Book",
            chapter_title="Chapter 1",
            chunk_index=0,
            source_text="Hello",
        )
    )

    assert result.translated_text == "你好"
    assert result.input_tokens == 10
    await provider.aclose()


@pytest.mark.asyncio
async def test_gemini_provider_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent"
        )
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "你好"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 12,
                    "candidatesTokenCount": 7,
                    "totalTokenCount": 19,
                },
            },
        )

    provider = GeminiProvider(
        api_key="secret",
        model="gemini-3.1-flash-lite-preview",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await provider.translate(
        TranslationRequest(
            book_title="Book",
            chapter_title="Chapter 1",
            chunk_index=0,
            source_text="Hello",
        )
    )

    assert result.translated_text == "你好"
    assert result.output_tokens == 7
    await provider.aclose()


def test_retryable_exception_flags_http_429() -> None:
    error = httpx.HTTPStatusError(
        "rate limit",
        request=httpx.Request("POST", "https://example.com"),
        response=httpx.Response(429),
    )

    assert is_retryable_exception(error) is True
