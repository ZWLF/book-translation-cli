from __future__ import annotations

from pathlib import Path

from book_translator.app_services import (
    BookDiscoveryError,
    run_engineering_books_sync,
    run_publishing_books_sync,
)
from book_translator.config import PublishingRunConfig, RunConfig
from book_translator.models import BookRunSummary


def _engineering_summary() -> BookRunSummary:
    return BookRunSummary(
        source_path="book.pdf",
        provider="openai",
        model="gpt-4o-mini",
        total_chapters=1,
        total_chunks=1,
        successful_chunks=1,
        failed_chunks=0,
        estimated_input_tokens=10,
        estimated_output_tokens=12,
        estimated_cost_usd=0.001,
        duration_seconds=0.1,
        avg_chunk_latency_ms=5.0,
    )


def test_run_engineering_books_sync_emits_progress_events_and_returns_summaries(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "book.pdf"
    input_path.write_text("placeholder", encoding="utf-8")
    output_path = tmp_path / "out"
    config = RunConfig(provider="openai", model="gpt-4o-mini")
    calls: list[tuple[Path, Path, RunConfig]] = []
    events: list[dict[str, object]] = []

    async def fake_process_book(*, input_path: Path, output_root: Path, config: RunConfig):
        calls.append((input_path, output_root, config))
        return _engineering_summary()

    def listener(event: dict[str, object]) -> None:
        events.append(event)

    summaries = run_engineering_books_sync(
        input_path=input_path,
        output_path=output_path,
        config=config,
        process_book_fn=fake_process_book,
        event_listener=listener,
    )

    assert summaries == [_engineering_summary().model_dump()]
    assert calls == [(input_path, output_path, config)]
    assert [event["type"] for event in events] == [
        "run_started",
        "book_started",
        "book_completed",
        "run_completed",
    ]
    assert events[0]["mode"] == "engineering"
    assert events[0]["total_books"] == 1
    assert events[2]["summary"] == _engineering_summary().model_dump()
    assert events[3]["summaries"] == [_engineering_summary().model_dump()]


def test_run_engineering_books_sync_raises_when_no_books_are_found(
    tmp_path: Path,
) -> None:
    empty_input = tmp_path / "empty"
    empty_input.mkdir()
    output_path = tmp_path / "out"
    events: list[dict[str, object]] = []

    async def fake_process_book(*, input_path: Path, output_root: Path, config: RunConfig):
        raise AssertionError("process_book should not be called for empty input")

    def listener(event: dict[str, object]) -> None:
        events.append(event)

    try:
        run_engineering_books_sync(
            input_path=empty_input,
            output_path=output_path,
            config=RunConfig(provider="openai", model="gpt-4o-mini"),
            process_book_fn=fake_process_book,
            event_listener=listener,
        )
    except BookDiscoveryError as exc:
        assert "No supported .pdf or .epub files found under" in str(exc)
    else:
        raise AssertionError("BookDiscoveryError was not raised")

    assert events == []
    assert not output_path.exists()


def test_run_engineering_books_sync_emits_failed_book_and_run_failed_events(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "books"
    input_path.mkdir()
    first_book = input_path / "a.pdf"
    second_book = input_path / "b.pdf"
    first_book.write_text("first", encoding="utf-8")
    second_book.write_text("second", encoding="utf-8")
    output_path = tmp_path / "out"
    config = RunConfig(provider="openai", model="gpt-4o-mini")
    calls: list[str] = []
    events: list[dict[str, object]] = []
    summaries_seen: list[dict[str, object]] = []

    async def fake_process_book(*, input_path: Path, output_root: Path, config: RunConfig):
        calls.append(input_path.name)
        if input_path.name == "a.pdf":
            summary = _engineering_summary().model_dump()
            summaries_seen.append(summary)
            return _engineering_summary()
        raise RuntimeError("boom")

    def listener(event: dict[str, object]) -> None:
        events.append(event)

    try:
        run_engineering_books_sync(
            input_path=input_path,
            output_path=output_path,
            config=config,
            process_book_fn=fake_process_book,
            event_listener=listener,
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("RuntimeError was not raised")

    assert calls == ["a.pdf", "b.pdf"]
    assert [event["type"] for event in events] == [
        "run_started",
        "book_started",
        "book_completed",
        "book_started",
        "book_failed",
        "run_failed",
    ]
    assert events[5]["summaries"] == summaries_seen
    assert events[5]["error"] == "boom"


def test_run_publishing_books_sync_emits_progress_events_and_returns_summaries(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "book.epub"
    input_path.write_text("placeholder", encoding="utf-8")
    output_path = tmp_path / "out"
    config = PublishingRunConfig(provider="openai", model="gpt-4o-mini")
    calls: list[tuple[Path, Path, PublishingRunConfig]] = []
    events: list[dict[str, object]] = []

    async def fake_process_book_publishing(
        *,
        input_path: Path,
        output_root: Path,
        config: PublishingRunConfig,
    ) -> dict[str, object]:
        calls.append((input_path, output_root, config))
        return {
            "mode": "publishing",
            "source_path": str(input_path),
            "completed_stage": "final-review",
            "successful_chunks": 1,
            "total_chunks": 1,
            "failed_chunks": 0,
            "estimated_cost_usd": 0.002,
        }

    def listener(event: dict[str, object]) -> None:
        events.append(event)

    summaries = run_publishing_books_sync(
        input_path=input_path,
        output_path=output_path,
        config=config,
        process_book_fn=fake_process_book_publishing,
        event_listener=listener,
    )

    assert summaries == [
        {
            "mode": "publishing",
            "source_path": str(input_path),
            "completed_stage": "final-review",
            "successful_chunks": 1,
            "total_chunks": 1,
            "failed_chunks": 0,
            "estimated_cost_usd": 0.002,
        }
    ]
    assert calls == [(input_path, output_path, config)]
    assert [event["type"] for event in events] == [
        "run_started",
        "book_started",
        "book_completed",
        "run_completed",
    ]
    assert events[0]["mode"] == "publishing"
    assert events[0]["total_books"] == 1
    assert events[2]["summary"]["completed_stage"] == "final-review"
    assert events[3]["summaries"] == summaries
