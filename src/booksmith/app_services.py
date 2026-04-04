from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal, TypedDict

from booksmith.config import PublishingRunConfig, RunConfig
from booksmith.models import BookRunSummary
from booksmith.pipeline import discover_books, process_book
from booksmith.publishing.pipeline import process_book_publishing

RunMode = Literal["engineering", "publishing"]


class RunStartedEvent(TypedDict):
    type: Literal["run_started"]
    mode: RunMode
    input_path: str
    output_path: str
    total_books: int


class BookStartedEvent(TypedDict):
    type: Literal["book_started"]
    mode: RunMode
    book_index: int
    total_books: int
    book_path: str
    book_name: str


class BookCompletedEvent(TypedDict):
    type: Literal["book_completed"]
    mode: RunMode
    book_index: int
    total_books: int
    book_path: str
    book_name: str
    summary: dict[str, object]


class BookFailedEvent(TypedDict):
    type: Literal["book_failed"]
    mode: RunMode
    book_index: int
    total_books: int
    book_path: str
    book_name: str
    error: str


class RunCompletedEvent(TypedDict):
    type: Literal["run_completed"]
    mode: RunMode
    input_path: str
    output_path: str
    total_books: int
    summaries: list[dict[str, object]]


class RunFailedEvent(TypedDict):
    type: Literal["run_failed"]
    mode: RunMode
    input_path: str
    output_path: str
    total_books: int
    summaries: list[dict[str, object]]
    error: str


ProgressEvent = (
    RunStartedEvent
    | BookStartedEvent
    | BookCompletedEvent
    | BookFailedEvent
    | RunCompletedEvent
    | RunFailedEvent
)
EventListener = Callable[[ProgressEvent], None]
EngineeringProcessor = Callable[..., Awaitable[Any]]
PublishingProcessor = Callable[..., Awaitable[Any]]


class BookDiscoveryError(ValueError):
    pass


def run_engineering_books_sync(
    *,
    input_path: Path,
    output_path: Path,
    config: RunConfig,
    process_book_fn: EngineeringProcessor = process_book,
    event_listener: EventListener | None = None,
) -> list[dict[str, object]]:
    return _run_books_sync(
        mode="engineering",
        input_path=input_path,
        output_path=output_path,
        config=config,
        process_book_fn=process_book_fn,
        event_listener=event_listener,
    )


def run_publishing_books_sync(
    *,
    input_path: Path,
    output_path: Path,
    config: PublishingRunConfig,
    process_book_fn: PublishingProcessor = process_book_publishing,
    event_listener: EventListener | None = None,
) -> list[dict[str, object]]:
    return _run_books_sync(
        mode="publishing",
        input_path=input_path,
        output_path=output_path,
        config=config,
        process_book_fn=process_book_fn,
        event_listener=event_listener,
    )


def _run_books_sync(
    *,
    mode: RunMode,
    input_path: Path,
    output_path: Path,
    config: RunConfig | PublishingRunConfig,
    process_book_fn: Callable[..., Awaitable[Any]],
    event_listener: EventListener | None,
) -> list[dict[str, object]]:
    books = discover_books(input_path)
    if not books:
        raise BookDiscoveryError(f"No supported .pdf or .epub files found under {input_path}.")

    output_path.mkdir(parents=True, exist_ok=True)
    _emit(
        event_listener,
        {
            "type": "run_started",
            "mode": mode,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "total_books": len(books),
        },
    )
    summaries: list[dict[str, object]] = []
    for book_index, book in enumerate(books, start=1):
        _emit(
            event_listener,
            {
                "type": "book_started",
                "mode": mode,
                "book_index": book_index,
                "total_books": len(books),
                "book_path": str(book),
                "book_name": book.name,
            },
        )
        try:
            summary = _run_async_sync(
                process_book_fn(
                    input_path=book,
                    output_root=output_path,
                    config=config,
                )
            )
        except Exception as exc:
            _emit(
                event_listener,
                {
                    "type": "book_failed",
                    "mode": mode,
                    "book_index": book_index,
                    "total_books": len(books),
                    "book_path": str(book),
                    "book_name": book.name,
                    "error": str(exc),
                },
            )
            _emit(
                event_listener,
                {
                    "type": "run_failed",
                    "mode": mode,
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "total_books": len(books),
                    "summaries": summaries,
                    "error": str(exc),
                },
            )
            raise
        summary_data = _summary_to_dict(summary)
        summaries.append(summary_data)
        _emit(
            event_listener,
            {
                "type": "book_completed",
                "mode": mode,
                "book_index": book_index,
                "total_books": len(books),
                "book_path": str(book),
                "book_name": book.name,
                "summary": summary_data,
            },
        )
    _emit(
        event_listener,
        {
            "type": "run_completed",
            "mode": mode,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "total_books": len(books),
            "summaries": summaries,
        },
    )
    return summaries


def _emit(event_listener: EventListener | None, event: ProgressEvent) -> None:
    if event_listener is not None:
        event_listener(event)


def _summary_to_dict(summary: Any) -> dict[str, object]:
    if isinstance(summary, Mapping):
        return dict(summary)
    model_dump = getattr(summary, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump())
    if isinstance(summary, BookRunSummary):
        return summary.model_dump()
    raise TypeError(f"Unsupported summary type: {type(summary)!r}")


def _run_async_sync(awaitable: Awaitable[Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(awaitable)).result()
