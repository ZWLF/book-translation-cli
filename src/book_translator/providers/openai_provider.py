from __future__ import annotations

import time

import httpx

from book_translator.models import TranslationRequest, TranslationResult
from book_translator.providers.base import BaseProvider, estimate_cost
from book_translator.translation.prompts import build_system_prompt, build_user_prompt


class OpenAIProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.openai.com",
    ) -> None:
        super().__init__("openai", model, api_key=api_key, client=client)
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
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": build_system_prompt()},
                        {"role": "user", "content": build_user_prompt(request)},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            usage = data.get("usage", {})
            translated_text = data["choices"][0]["message"]["content"].strip()
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
            return self.make_result(
                chunk_id=request.chunk_id,
                translated_text=translated_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimate_cost("openai", self.model, input_tokens, output_tokens),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        finally:
            if close_client:
                await client.aclose()
