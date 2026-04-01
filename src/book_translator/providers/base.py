from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from book_translator.models import TranslationRequest, TranslationResult


class BaseProvider(ABC):
    def __init__(
        self,
        provider_name: str,
        model: str,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.api_key = api_key
        self.client = client

    @abstractmethod
    async def translate(self, request: TranslationRequest) -> TranslationResult:
        raise NotImplementedError

    async def aclose(self) -> None:
        if self.client is not None:
            await self.client.aclose()

    def make_result(
        self,
        *,
        chunk_id: str,
        translated_text: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: float,
        attempt_count: int = 1,
        latency_ms: int = 0,
    ) -> TranslationResult:
        return TranslationResult(
            chunk_id=chunk_id,
            translated_text=translated_text,
            provider=self.provider_name,
            model=self.model,
            attempt_count=attempt_count,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = {
        ("openai", "gpt-4o-mini"): (0.15, 0.60),
        ("gemini", "gemini-3.1-flash-lite-preview"): (0.25, 1.50),
        ("gemini", "gemini-2.5-flash-lite"): (0.10, 0.40),
    }
    default = pricing[("openai", "gpt-4o-mini")]
    input_rate, output_rate = pricing.get((provider, model), default)
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
