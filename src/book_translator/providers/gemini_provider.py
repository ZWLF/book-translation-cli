from __future__ import annotations

import time

import httpx

from book_translator.models import TranslationRequest, TranslationResult
from book_translator.providers.base import BaseProvider, estimate_cost
from book_translator.translation.prompts import build_user_prompt


class GeminiProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://generativelanguage.googleapis.com",
    ) -> None:
        super().__init__("gemini", model, api_key=api_key, client=client)
        self.base_url = base_url.rstrip("/")

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        close_client = False
        client = self.client
        if client is None:
            client = httpx.AsyncClient(timeout=60.0)
            close_client = True
        started = time.perf_counter()
        try:
            response = await client.post(
                f"{self.base_url}/v1beta/models/{self.model}:generateContent",
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": build_user_prompt(request)}]}],
                    "generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}},
                },
            )
            response.raise_for_status()
            data = response.json()
            usage = data.get("usageMetadata", {})
            translated_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            input_tokens = int(usage.get("promptTokenCount", 0))
            output_tokens = int(usage.get("candidatesTokenCount", 0))
            return self.make_result(
                chunk_id=request.chunk_id,
                translated_text=translated_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimate_cost("gemini", self.model, input_tokens, output_tokens),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        finally:
            if close_client:
                await client.aclose()
