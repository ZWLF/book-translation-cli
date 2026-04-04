from __future__ import annotations

import tkinter as tk
import tomllib
from pathlib import Path
from queue import Queue
from tkinter import ttk

import pytest

from booksmith.gui.app import BooksmithGui
from booksmith.gui.services import GuiFormValidationError, GuiValidationIssue
from booksmith.gui.state import GuiRuntimeRequest
from booksmith.gui.tasks import GuiTaskRunner
from booksmith.utils import slugify


def _create_gui(**kwargs: object) -> BooksmithGui:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable in this environment: {exc}")
    return BooksmithGui(root=root, **kwargs)


class _FakeTaskRunner:
    def __init__(self) -> None:
        self.event_queue: Queue[dict[str, object]] = Queue()
        self.started_requests: list[GuiRuntimeRequest] = []

    def start(self, request: GuiRuntimeRequest) -> None:
        self.started_requests.append(request)


class _FailingStartTaskRunner:
    def __init__(self, exc: Exception) -> None:
        self.event_queue: Queue[dict[str, object]] = Queue()
        self.started_requests: list[GuiRuntimeRequest] = []
        self._exc = exc

    def start(self, request: GuiRuntimeRequest) -> None:
        self.started_requests.append(request)
        raise self._exc


def _configure_engineering_form(
    app: BooksmithGui,
    input_path: Path,
    output_path: Path,
) -> None:
    app.views.input_path_var.set(str(input_path))
    app.views.output_path_var.set(str(output_path))
    app.views.provider_var.set("openai")
    app.views.model_var.set("gpt-4.1")
    app.views.render_pdf_var.set(True)


def _configure_publishing_form(
    app: BooksmithGui,
    input_path: Path,
    output_path: Path,
) -> None:
    app.mode_var.set("publishing")
    app.views.input_path_var.set(str(input_path))
    app.views.output_path_var.set(str(output_path))
    app.views.provider_var.set("openai")
    app.views.model_var.set("gpt-4.1")
    app.views.render_pdf_var.set(True)
    app.views.also_pdf_var.set(True)
    app.views.also_epub_var.set(True)


def test_gui_app_bootstraps_without_mainloop() -> None:
    app = _create_gui()
    try:
        assert app.root.title() == "Booksmith"
        assert app.mode_var.get() == "engineering"
        assert app.publishing_frame.winfo_manager() == ""
        assert app.task_runner._event_queue is app.event_queue
    finally:
        app.root.destroy()


def test_gui_exposes_publishing_view_refs_for_polished_layout() -> None:
    app = _create_gui()
    try:
        assert type(app.views.publishing_frame) is ttk.Frame
        assert isinstance(app.views.publishing_advanced_frame, ttk.Frame)
        assert isinstance(app.views.publishing_expanded_var, tk.BooleanVar)
        assert app.views.publishing_expanded_var.get() is False
        assert isinstance(app.views.publishing_toggle_button, ttk.Button)
    finally:
        app.root.destroy()


def test_gui_app_accepts_real_task_runner_injection() -> None:
    queue: Queue[dict[str, object]] = Queue()
    runner = GuiTaskRunner(event_queue=queue)
    app = _create_gui(task_runner=runner)
    try:
        assert app.task_runner is runner
        assert app.event_queue is queue
        assert app.task_runner.event_queue is queue
    finally:
        app.root.destroy()


def test_gui_publishing_panel_visibility_tracks_mode() -> None:
    app = _create_gui()
    try:
        app.mode_var.set("publishing")
        app.sync_mode_panels()
        app.root.update_idletasks()
        assert app.publishing_frame.winfo_manager() == "grid"

        app.mode_var.set("engineering")
        app.sync_mode_panels()
        app.root.update_idletasks()
        assert app.publishing_frame.winfo_manager() == ""
    finally:
        app.root.destroy()


def test_gui_run_button_starts_injected_task_runner_and_polls_shared_queue(
    tmp_path: Path,
) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "book.pdf"
    input_path.write_text("pdf", encoding="utf-8")
    output_path = tmp_path / "out"
    workspace_root = output_path / slugify(input_path.stem)
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "run_summary.json").write_text("{}", encoding="utf-8")
    (workspace_root / "translated.txt").write_text("translated", encoding="utf-8")
    (workspace_root / "translated.pdf").write_text("pdf", encoding="utf-8")

    try:
        _configure_engineering_form(app, input_path, output_path)

        app._start_run()
        assert app.event_queue is runner.event_queue
        assert len(runner.started_requests) == 1

        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 2,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_started",
                "mode": "engineering",
                "book_index": 2,
                "total_books": 2,
                "book_path": str(input_path),
                "book_name": input_path.name,
            }
        )
        app._poll_runner_events()

        assert app.stage_var.get() == "Processing book.pdf (2/2)"
        assert app.run_state.progress_fraction == 0.5
        assert app.status_var.get() == "Running"
        assert app.result_state.output_paths == ()

        runner.event_queue.put(
            {
                "type": "book_completed",
                "mode": "engineering",
                "book_index": 2,
                "total_books": 2,
                "book_path": str(input_path),
                "book_name": input_path.name,
                "summary": {
                    "successful_chunks": 3,
                    "failed_chunks": 1,
                    "estimated_cost_usd": 1.25,
                    "duration_seconds": 12.5,
                },
            }
        )
        runner.event_queue.put(
            {
                "type": "run_completed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 2,
                "summaries": [
                    {
                        "successful_chunks": 3,
                        "failed_chunks": 1,
                        "estimated_cost_usd": 1.25,
                        "duration_seconds": 12.5,
                    }
                ],
            }
        )
        app._poll_runner_events()

        request = runner.started_requests[0]
        assert request.input_path == input_path
        assert request.output_path == output_path
        assert app.status_var.get() == "Completed"
        assert "3 successful chunks" in app.summary_var.get()
        assert app.run_state.successful_chunks == 3
        assert app.run_state.failed_chunks == 1
        assert app.run_state.estimated_cost_usd == 1.25
        assert app.run_state.elapsed_seconds == 12.5
        assert app.run_state.progress_fraction == 1.0
        assert app.stage_var.get() == "Run completed"
        assert app.result_state.output_paths == (
            workspace_root / "run_summary.json",
            workspace_root / "translated.txt",
            workspace_root / "translated.pdf",
        )
        assert app.views.result_buttons["open_output_folder"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_run_summary"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_translated_txt"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_translated_pdf"].winfo_manager() == "grid"
    finally:
        app.root.destroy()


def test_gui_start_run_validation_error_is_handled_inline_without_raising(
    tmp_path: Path,
) -> None:
    runner = _FakeTaskRunner()

    def _raise_validation_error(_form: object) -> GuiRuntimeRequest:
        raise GuiFormValidationError(
            [GuiValidationIssue(field="input_path", message="validation boom")]
        )

    app = _create_gui(task_runner=runner, request_builder=_raise_validation_error)
    input_path = tmp_path / "book.pdf"
    input_path.write_text("pdf", encoding="utf-8")
    output_path = tmp_path / "out"

    try:
        _configure_engineering_form(app, input_path, output_path)

        app._start_run()

        assert app.status_var.get() == "Failed"
        assert app.summary_var.get() == "input_path: validation boom"
        assert app.result_state.error == "input_path: validation boom"
        assert "validation boom" in app.log_text.get("1.0", "end")
        assert not app.run_button.instate(["disabled"])
        assert app._queue_poll_after_id is None
        assert runner.started_requests == []
    finally:
        app.root.destroy()


def test_gui_start_run_runner_start_error_is_handled_inline_without_raising(
    tmp_path: Path,
) -> None:
    runner = _FailingStartTaskRunner(RuntimeError("runner start boom"))
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "book.pdf"
    input_path.write_text("pdf", encoding="utf-8")
    output_path = tmp_path / "out"

    try:
        _configure_engineering_form(app, input_path, output_path)

        app._start_run()

        assert app.status_var.get() == "Failed"
        assert app.summary_var.get() == "runner start boom"
        assert app.result_state.error == "runner start boom"
        assert "runner start boom" in app.log_text.get("1.0", "end")
        assert not app.run_button.instate(["disabled"])
        assert app._queue_poll_after_id is None
        assert len(runner.started_requests) == 1
    finally:
        app.root.destroy()


def test_gui_handles_book_failed_event(tmp_path: Path) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "book.pdf"
    input_path.write_text("pdf", encoding="utf-8")
    output_path = tmp_path / "out"

    try:
        _configure_engineering_form(app, input_path, output_path)
        app._start_run()

        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 2,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_started",
                "mode": "engineering",
                "total_books": 2,
                "book_index": 1,
                "book_path": str(input_path),
                "book_name": input_path.name,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_failed",
                "mode": "engineering",
                "book_index": 1,
                "total_books": 2,
                "book_path": str(input_path),
                "book_name": input_path.name,
                "error": "boom",
            }
        )
        runner.event_queue.put(
            {
                "type": "run_failed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 2,
                "summaries": [],
                "error": "boom",
            }
        )
        app._poll_runner_events()

        assert app.status_var.get() == "Failed"
        assert "boom" in app.summary_var.get()
        assert app.result_state.error == "boom"
        assert "Failed book.pdf" in app.log_text.get("1.0", "end")
    finally:
        app.root.destroy()


def test_gui_run_failed_keeps_multi_book_output_folder_accessible(
    tmp_path: Path,
) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "books"
    input_path.mkdir()
    (input_path / "a.pdf").write_text("a", encoding="utf-8")
    (input_path / "b.epub").write_text("b", encoding="utf-8")
    output_path = tmp_path / "out"
    output_path.mkdir()

    try:
        _configure_engineering_form(app, input_path, output_path)
        app._start_run()

        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 2,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_completed",
                "mode": "engineering",
                "book_index": 1,
                "total_books": 2,
                "book_path": str(input_path / "a.pdf"),
                "book_name": "a.pdf",
                "summary": {
                    "successful_chunks": 2,
                    "failed_chunks": 0,
                    "estimated_cost_usd": 0.5,
                    "duration_seconds": 4.0,
                },
            }
        )
        runner.event_queue.put(
            {
                "type": "run_failed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 2,
                "summaries": [],
                "error": "boom",
            }
        )
        app._poll_runner_events()

        assert app.status_var.get() == "Failed"
        assert app.views.result_buttons["open_output_folder"].winfo_manager() == "grid"
        assert app.result_state.error == "boom"
    finally:
        app.root.destroy()


def test_gui_run_failed_keeps_single_book_result_files_accessible(
    tmp_path: Path,
) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "book.pdf"
    input_path.write_text("pdf", encoding="utf-8")
    output_path = tmp_path / "out"
    workspace_root = output_path / slugify(input_path.stem)
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "run_summary.json").write_text("{}", encoding="utf-8")
    (workspace_root / "translated.txt").write_text("translated", encoding="utf-8")

    try:
        _configure_engineering_form(app, input_path, output_path)
        app._start_run()

        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_completed",
                "mode": "engineering",
                "book_index": 1,
                "total_books": 1,
                "book_path": str(input_path),
                "book_name": input_path.name,
                "summary": {
                    "successful_chunks": 1,
                    "failed_chunks": 0,
                    "estimated_cost_usd": 0.25,
                    "duration_seconds": 3.0,
                },
            }
        )
        runner.event_queue.put(
            {
                "type": "run_failed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
                "summaries": [],
                "error": "boom",
            }
        )
        app._poll_runner_events()

        assert app.status_var.get() == "Failed"
        assert app.views.result_buttons["open_output_folder"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_run_summary"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_translated_txt"].winfo_manager() == "grid"
        assert app.result_state.error == "boom"
    finally:
        app.root.destroy()


def test_gui_continues_polling_until_run_failed_arrives(tmp_path: Path) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "book.pdf"
    input_path.write_text("pdf", encoding="utf-8")
    output_path = tmp_path / "out"

    try:
        _configure_engineering_form(app, input_path, output_path)
        app._start_run()

        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_failed",
                "mode": "engineering",
                "book_index": 1,
                "total_books": 1,
                "book_path": str(input_path),
                "book_name": input_path.name,
                "error": "boom",
            }
        )
        app._poll_runner_events()

        assert app.status_var.get() == "Failed"
        assert app.run_button.instate(["disabled"])
        assert app._queue_poll_after_id is not None

        runner.event_queue.put(
            {
                "type": "run_failed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
                "summaries": [],
                "error": "boom",
            }
        )
        app._poll_runner_events()

        assert app.status_var.get() == "Failed"
        assert not app.run_button.instate(["disabled"])
        assert app.result_state.error == "boom"
    finally:
        app.root.destroy()


def test_gui_run_completed_aggregates_multi_book_summaries(tmp_path: Path) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "books"
    input_path.mkdir()
    (input_path / "a.pdf").write_text("a", encoding="utf-8")
    (input_path / "b.pdf").write_text("b", encoding="utf-8")
    output_path = tmp_path / "out"
    output_path.mkdir()

    try:
        _configure_engineering_form(app, input_path, output_path)
        app._start_run()

        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 2,
            }
        )
        runner.event_queue.put(
            {
                "type": "run_completed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 2,
                "summaries": [
                    {
                        "successful_chunks": 10,
                        "failed_chunks": 1,
                        "estimated_cost_usd": 2.5,
                        "duration_seconds": 12.0,
                    },
                    {
                        "successful_chunks": 3,
                        "failed_chunks": 2,
                        "estimated_cost_usd": 0.75,
                        "duration_seconds": 8.0,
                    },
                ],
            }
        )
        app._poll_runner_events()

        assert app.run_state.successful_chunks == 13
        assert app.run_state.failed_chunks == 3
        assert app.run_state.estimated_cost_usd == 3.25
        assert app.run_state.elapsed_seconds == 20.0
        assert "13 successful chunks" in app.summary_var.get()
        assert app.views.result_buttons["open_output_folder"].winfo_manager() == "grid"
    finally:
        app.root.destroy()


def test_gui_result_actions_only_show_existing_paths(tmp_path: Path) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "book.epub"
    input_path.write_text("epub", encoding="utf-8")
    output_path = tmp_path / "out"
    workspace_root = output_path / slugify(input_path.stem)
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "run_summary.json").write_text("{}", encoding="utf-8")
    (workspace_root / "translated.txt").write_text("translated", encoding="utf-8")

    try:
        _configure_engineering_form(app, input_path, output_path)
        app._start_run()
        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_completed",
                "mode": "engineering",
                "book_index": 1,
                "total_books": 1,
                "book_path": str(input_path),
                "book_name": input_path.name,
                "summary": {
                    "successful_chunks": 1,
                    "failed_chunks": 0,
                    "estimated_cost_usd": 0.25,
                    "duration_seconds": 3.0,
                },
            }
        )
        runner.event_queue.put(
            {
                "type": "run_completed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
                "summaries": [
                    {
                        "successful_chunks": 1,
                        "failed_chunks": 0,
                        "estimated_cost_usd": 0.25,
                        "duration_seconds": 3.0,
                    }
                ],
            }
        )
        app._poll_runner_events()

        assert app.views.result_buttons["open_output_folder"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_run_summary"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_translated_txt"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_translated_pdf"].winfo_manager() == ""
    finally:
        app.root.destroy()


def test_gui_publishing_toggles_affect_request_and_result_actions(tmp_path: Path) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "book.pdf"
    input_path.write_text("pdf", encoding="utf-8")
    output_path = tmp_path / "out"
    workspace_root = output_path / slugify(input_path.stem)
    final_root = workspace_root / "publishing" / "final"
    audit_root = workspace_root / "publishing" / "audit"
    final_root.mkdir(parents=True, exist_ok=True)
    audit_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "publishing" / "run_summary.json").write_text("{}", encoding="utf-8")
    (final_root / "translated.txt").write_text("translated", encoding="utf-8")
    (final_root / "translated.pdf").write_text("pdf", encoding="utf-8")
    (final_root / "translated.epub").write_text("epub", encoding="utf-8")
    (audit_root / "final_audit_report.json").write_text("{}", encoding="utf-8")

    try:
        _configure_publishing_form(app, input_path, output_path)
        app.views.also_pdf_var.set(False)
        app.views.also_epub_var.set(False)
        app._start_run()

        request = runner.started_requests[0]
        assert request.mode == "publishing"
        assert request.config.also_pdf is False
        assert request.config.also_epub is False

        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "publishing",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_completed",
                "mode": "publishing",
                "book_index": 1,
                "total_books": 1,
                "book_path": str(input_path),
                "book_name": input_path.name,
                "summary": {
                    "successful_chunks": 9,
                    "failed_chunks": 0,
                    "estimated_cost_usd": 2.5,
                    "duration_seconds": 30.0,
                },
            }
        )
        runner.event_queue.put(
            {
                "type": "run_completed",
                "mode": "publishing",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
                "summaries": [
                    {
                        "successful_chunks": 9,
                        "failed_chunks": 0,
                        "estimated_cost_usd": 2.5,
                        "duration_seconds": 30.0,
                    }
                ],
            }
        )
        app._poll_runner_events()

        assert app.views.result_buttons["open_output_folder"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_run_summary"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_translated_txt"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_translated_pdf"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_translated_epub"].winfo_manager() == ""
        assert app.views.result_buttons["open_audit_report"].winfo_manager() == ""
        assert app.result_state.output_paths == (
            workspace_root / "publishing" / "run_summary.json",
            final_root / "translated.txt",
            final_root / "translated.pdf",
        )
    finally:
        app.root.destroy()


def test_gui_clears_previous_result_actions_when_a_new_run_starts(tmp_path: Path) -> None:
    runner = _FakeTaskRunner()
    app = _create_gui(task_runner=runner)
    input_path = tmp_path / "book.pdf"
    input_path.write_text("pdf", encoding="utf-8")
    output_path = tmp_path / "out"
    workspace_root = output_path / slugify(input_path.stem)
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "run_summary.json").write_text("{}", encoding="utf-8")
    (workspace_root / "translated.txt").write_text("translated", encoding="utf-8")
    (workspace_root / "translated.pdf").write_text("pdf", encoding="utf-8")

    try:
        _configure_engineering_form(app, input_path, output_path)
        app._start_run()
        runner.event_queue.put(
            {
                "type": "run_started",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
            }
        )
        runner.event_queue.put(
            {
                "type": "book_completed",
                "mode": "engineering",
                "book_index": 1,
                "total_books": 1,
                "book_path": str(input_path),
                "book_name": input_path.name,
                "summary": {
                    "successful_chunks": 1,
                    "failed_chunks": 0,
                    "estimated_cost_usd": 0.25,
                    "duration_seconds": 3.0,
                },
            }
        )
        runner.event_queue.put(
            {
                "type": "run_completed",
                "mode": "engineering",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_books": 1,
                "summaries": [
                    {
                        "successful_chunks": 1,
                        "failed_chunks": 0,
                        "estimated_cost_usd": 0.25,
                        "duration_seconds": 3.0,
                    }
                ],
            }
        )
        app._poll_runner_events()

        assert app.views.result_buttons["open_translated_pdf"].winfo_manager() == "grid"
        assert app.views.result_buttons["open_run_summary"].winfo_manager() == "grid"

        app._start_run()

        for key in (
            "open_output_folder",
            "open_run_summary",
            "open_translated_txt",
            "open_translated_pdf",
            "open_translated_epub",
            "open_audit_report",
        ):
            assert app.views.result_buttons[key].winfo_manager() == ""
            assert app.views.result_path_vars[key].get() == ""
    finally:
        app.root.destroy()


def test_gui_entry_points_are_declarable() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "booksmith"
    assert pyproject["project"]["description"] == (
        "Booksmith: engineering and publishing workflows for translating books."
    )
    assert pyproject["project"]["scripts"]["booksmith"] == "booksmith.cli:main"
    assert pyproject["project"]["scripts"]["booksmith-gui"] == "booksmith.gui.app:main"

    from booksmith.gui import __main__ as module_main

    assert callable(module_main.main)
