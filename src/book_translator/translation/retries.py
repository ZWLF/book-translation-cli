from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx


def is_retryable_exception(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    if isinstance(error, httpx.TimeoutException | httpx.NetworkError | httpx.RemoteProtocolError):
        return True
    if isinstance(error, httpx.RequestError):
        return True
    return False


async def retry_async(
    operation: Callable[[], Awaitable[object]],
    *,
    max_attempts: int = 4,
    base_delay: float = 1.0,
) -> tuple[object, int]:
    attempt = 0
    while True:
        attempt += 1
        try:
            return await operation(), attempt
        except Exception as error:
            if attempt >= max_attempts or not is_retryable_exception(error):
                raise
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)) + random.uniform(0.0, 0.25))
