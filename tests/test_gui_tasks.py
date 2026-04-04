from __future__ import annotations

from pathlib import Path
from queue import Queue
from threading import Event

from book_translator.config import RunConfig
from book_translator.gui.state import GuiRuntimeRequest
from book_translator.gui.tasks import GuiTaskRunner


class _UnsupportedSummary:
    pass


def _runtime_request(tmp_path: Path, mode: str = "engineering") -> GuiRuntimeRequest:
    input_path = tmp_path / "book.pdf"
    output_path = tmp_path / "out"
    return GuiRuntimeRequest(
        mode=mode,
        input_path=input_path,
        output_path=output_path,
        source_kind="file",
        source_format="pdf",
        provider="openai",
        model="gpt-4o-mini",
        config=RunConfig(provider="openai", model="gpt-4o-mini"),
        primary_output="pdf",
        discovered_books=(input_path,),
        additional_outputs=(),
        expected_outputs=(),
    )


def test_gui_task_runner_forwards_progress_events_and_posts_terminal_success(
    tmp_path: Path,
) -> None:
    queue: Queue[dict[str, object]] = Queue()
    started = Event()

    def run_engineering_fn(
        *,
        input_path: Path,
        output_path: Path,
        config: RunConfig,
        event_listener,
    ) -> list[dict[str, object]]:
        event_listener({"type": "run_started", "mode": "engineering", "total_books": 1})
        event_listener({"type": "book_completed", "summary": {"successful_chunks": 3}})
        started.set()
        return [{"successful_chunks": 3, "failed_chunks": 0}]

    runner = GuiTaskRunner(
        event_queue=queue,
        run_engineering_fn=run_engineering_fn,
    )

    runner.start(_runtime_request(tmp_path))
    assert started.wait(timeout=2)
    runner.join(timeout=2)

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert events == [
        {"type": "run_started", "mode": "engineering", "total_books": 1},
        {"type": "book_completed", "summary": {"successful_chunks": 3}},
        {
            "type": "run_completed",
            "mode": "engineering",
            "input_path": str(tmp_path / "book.pdf"),
            "output_path": str(tmp_path / "out"),
            "total_books": 1,
            "summaries": [{"successful_chunks": 3, "failed_chunks": 0}],
        },
    ]


def test_gui_task_runner_posts_terminal_failure_event(tmp_path: Path) -> None:
    queue: Queue[dict[str, object]] = Queue()

    def run_publishing_fn(
        *,
        input_path: Path,
        output_path: Path,
        config,
        event_listener,
    ) -> list[dict[str, object]]:
        event_listener({"type": "run_started", "mode": "publishing", "total_books": 1})
        raise RuntimeError("boom")

    runner = GuiTaskRunner(
        event_queue=queue,
        run_publishing_fn=run_publishing_fn,
    )

    runner.start(_runtime_request(tmp_path, mode="publishing"))
    runner.join(timeout=2)

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert events == [
        {"type": "run_started", "mode": "publishing", "total_books": 1},
        {
            "type": "run_failed",
            "mode": "publishing",
            "input_path": str(tmp_path / "book.pdf"),
            "output_path": str(tmp_path / "out"),
            "total_books": 1,
            "summaries": [],
            "error": "boom",
        },
    ]


def test_gui_task_runner_posts_run_failed_for_unsupported_summary_object(
    tmp_path: Path,
) -> None:
    queue: Queue[dict[str, object]] = Queue()

    def run_engineering_fn(
        *,
        input_path: Path,
        output_path: Path,
        config: RunConfig,
        event_listener,
    ) -> list[object]:
        return [_UnsupportedSummary()]

    runner = GuiTaskRunner(
        event_queue=queue,
        run_engineering_fn=run_engineering_fn,
    )

    runner.start(_runtime_request(tmp_path))
    assert runner.join(timeout=2)

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert events[0]["type"] == "run_failed"
    assert events[0]["mode"] == "engineering"
    assert events[0]["input_path"] == str(tmp_path / "book.pdf")
    assert events[0]["output_path"] == str(tmp_path / "out")
    assert events[0]["total_books"] == 1
    assert events[0]["summaries"] == []
    assert isinstance(events[0]["error"], str)
    assert events[0]["error"]


def test_gui_task_runner_does_not_duplicate_forwarded_run_completed_event(
    tmp_path: Path,
) -> None:
    queue: Queue[dict[str, object]] = Queue()

    def run_engineering_fn(
        *,
        input_path: Path,
        output_path: Path,
        config: RunConfig,
        event_listener,
    ) -> list[dict[str, object]]:
        event_listener(
            {
                "type": "run_completed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
                "summaries": [{"successful_chunks": 1}],
            }
        )
        return [{"successful_chunks": 1}]

    runner = GuiTaskRunner(
        event_queue=queue,
        run_engineering_fn=run_engineering_fn,
    )

    runner.start(_runtime_request(tmp_path))
    assert runner.join(timeout=2)

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert events == [
        {
            "type": "run_completed",
            "mode": "engineering",
            "input_path": str(tmp_path / "book.pdf"),
            "output_path": str(tmp_path / "out"),
            "total_books": 1,
            "summaries": [{"successful_chunks": 1}],
        }
    ]


def test_gui_task_runner_does_not_duplicate_forwarded_run_failed_event(
    tmp_path: Path,
) -> None:
    queue: Queue[dict[str, object]] = Queue()

    def run_publishing_fn(
        *,
        input_path: Path,
        output_path: Path,
        config,
        event_listener,
    ) -> list[dict[str, object]]:
        event_listener(
            {
                "type": "run_failed",
                "mode": "publishing",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
                "summaries": [],
                "error": "boom",
            }
        )
        raise RuntimeError("boom")

    runner = GuiTaskRunner(
        event_queue=queue,
        run_publishing_fn=run_publishing_fn,
    )

    runner.start(_runtime_request(tmp_path, mode="publishing"))
    assert runner.join(timeout=2)

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert events == [
        {
            "type": "run_failed",
            "mode": "publishing",
            "input_path": str(tmp_path / "book.pdf"),
            "output_path": str(tmp_path / "out"),
            "total_books": 1,
            "summaries": [],
            "error": "boom",
        }
    ]
