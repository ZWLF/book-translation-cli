from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue

from book_translator.state.workspace import Workspace
from book_translator.utils import slugify

from .services import build_runtime_request
from .state import GuiFormState, GuiResultState, GuiRunState, GuiRuntimeRequest
from .tasks import GuiEvent, GuiTaskRunner
from .views import GuiShellViews, build_shell


class BookTranslatorGui:
    def __init__(
        self,
        *,
        root: tk.Tk | None = None,
        task_runner: GuiTaskRunner | None = None,
        request_builder: Callable[[GuiFormState], GuiRuntimeRequest] = build_runtime_request,
        open_path: Callable[[Path], None] | None = None,
    ) -> None:
        self.root = root or tk.Tk()
        self.mode_var = tk.StringVar(master=self.root, value="engineering")
        self.views: GuiShellViews = build_shell(self.root, mode_var=self.mode_var)
        self.publishing_frame = self.views.publishing_frame
        self.status_var = self.views.status_var
        self.stage_var = self.views.stage_var
        self.summary_var = self.views.summary_var
        self.progress_var = self.views.progress_var
        self.log_text = self.views.log_text
        self.run_button = self.views.run_button
        self.result_buttons = self.views.result_buttons
        self.result_path_vars = self.views.result_path_vars
        self.run_state = GuiRunState()
        self.result_state = GuiResultState()
        self.current_request: GuiRuntimeRequest | None = None
        self._request_builder = request_builder
        self._open_path_handler = open_path or self._default_open_path
        self._queue_poll_after_id: str | None = None

        if task_runner is None:
            self.event_queue: Queue[GuiEvent] = Queue()
            self.task_runner = GuiTaskRunner(event_queue=self.event_queue)
        else:
            self.task_runner = task_runner
            event_queue = getattr(task_runner, "event_queue", None)
            if event_queue is None:
                raise ValueError("Injected task_runner must expose an event_queue")
            self.event_queue = event_queue

        self.mode_var.trace_add("write", self._on_mode_changed)
        self.views.run_button.configure(command=self._start_run)
        self.sync_mode_panels()
        self._sync_state_widgets()
        self._refresh_result_actions()

    def run(self) -> None:
        self.root.mainloop()

    def sync_mode_panels(self) -> None:
        if self.mode_var.get() == "publishing":
            self.publishing_frame.grid()
        else:
            self.publishing_frame.grid_remove()
        self.root.update_idletasks()

    def _on_mode_changed(self, *_args: object) -> None:
        self.sync_mode_panels()

    def _collect_form_state(self) -> GuiFormState:
        return GuiFormState(
            mode=self.mode_var.get(),
            input_path=self._path_from_var(self.views.input_path_var),
            output_path=self._path_from_var(self.views.output_path_var),
            provider=self.views.provider_var.get().strip(),
            model=self.views.model_var.get().strip(),
            render_pdf=self.views.render_pdf_var.get(),
            also_pdf=self.views.also_pdf_var.get(),
            also_epub=self.views.also_epub_var.get(),
        )

    def _start_run(self) -> None:
        self._clear_logs()
        self._hide_all_result_actions()
        self.run_button.state(["disabled"])
        self.result_state = GuiResultState()

        request: GuiRuntimeRequest | None = None
        try:
            request = self._request_builder(self._collect_form_state())
            self.current_request = request
            self.run_state = GuiRunState(
                status="running",
                total_books=len(request.discovered_books) or 1,
            )
            self.run_state.message = "Queued"
            self.run_state.current_stage = "Queued"
            self.status_var.set("Running")
            self.stage_var.set(self.run_state.current_stage)
            self.summary_var.set("Queued")
            self.progress_var.set(0.0)
            self._append_log_line(
                f"Starting {request.mode} run for {request.input_path} -> {request.output_path}"
            )
            self.task_runner.start(request)
        except Exception as exc:
            self._handle_start_failure(exc, request=request)
            return

        self._schedule_queue_poll()
        self._sync_state_widgets()

    def _schedule_queue_poll(self) -> None:
        if self._queue_poll_after_id is not None:
            return
        self._queue_poll_after_id = self.root.after(50, self._poll_runner_events)

    def _poll_runner_events(self) -> None:
        self._queue_poll_after_id = None
        while True:
            try:
                event = self.event_queue.get_nowait()
            except Empty:
                break
            self._handle_event(event)

        if self.run_button.instate(["disabled"]):
            self._schedule_queue_poll()

    def _handle_event(self, event: GuiEvent) -> None:
        event_type = str(event.get("type", ""))
        if not event_type:
            return

        if event_type == "run_started":
            self._apply_run_started(event)
        elif event_type == "book_started":
            self._apply_book_started(event)
        elif event_type == "book_completed":
            self._apply_book_completed(event)
        elif event_type == "book_failed":
            self._apply_book_failed(event)
        elif event_type == "run_completed":
            self._apply_run_completed(event)
        elif event_type == "run_failed":
            self._apply_run_failed(event)
        else:
            self._append_log_line(f"Unhandled event: {event_type}")

        self._sync_state_widgets()

    def _apply_run_started(self, event: GuiEvent) -> None:
        self.run_state.status = "running"
        self.run_state.total_books = self._int_from_event(
            event,
            "total_books",
            self.run_state.total_books,
        )
        self.run_state.completed_books = 0
        self.run_state.current_book_name = ""
        self.run_state.message = "Run started"
        self.run_state.current_stage = "Run started"
        self.run_state.progress_fraction = 0.0
        self._append_log_line(self._format_event_log(event))
        self.summary_var.set(self._status_summary())

    def _apply_book_started(self, event: GuiEvent) -> None:
        book_index = self._int_from_event(event, "book_index", self.run_state.completed_books + 1)
        self.run_state.current_book_name = str(event.get("book_name") or "")
        self.run_state.completed_books = max(0, book_index - 1)
        self.run_state.total_books = self._int_from_event(
            event,
            "total_books",
            self.run_state.total_books,
        )
        self.run_state.message = f"Processing {self.run_state.current_book_name or 'book'}"
        self.run_state.current_stage = self._book_stage_message("Processing", event)
        self._update_progress(
            completed_books=self.run_state.completed_books,
            total_books=self.run_state.total_books,
        )
        self._append_log_line(self._format_event_log(event))
        self.summary_var.set(self._status_summary())

    def _apply_book_completed(self, event: GuiEvent) -> None:
        book_index = self._int_from_event(event, "book_index", self.run_state.completed_books + 1)
        self.run_state.current_book_name = str(event.get("book_name") or "")
        self.run_state.completed_books = book_index
        self.run_state.total_books = self._int_from_event(
            event,
            "total_books",
            self.run_state.total_books,
        )
        summary = event.get("summary")
        if isinstance(summary, dict):
            self.result_state.summary = dict(summary)
            self._apply_summary_metrics(summary)
        self.run_state.message = self._book_summary_message("Completed", event)
        self.run_state.current_stage = self._book_stage_message("Completed", event)
        self._update_progress(
            completed_books=self.run_state.completed_books,
            total_books=self.run_state.total_books,
        )
        self._append_log_line(self._format_event_log(event))
        self.summary_var.set(self._status_summary())

    def _apply_book_failed(self, event: GuiEvent) -> None:
        book_index = self._int_from_event(event, "book_index", self.run_state.completed_books + 1)
        self.run_state.current_book_name = str(event.get("book_name") or "")
        self.run_state.completed_books = max(0, book_index - 1)
        self.run_state.total_books = self._int_from_event(
            event,
            "total_books",
            self.run_state.total_books,
        )
        self.run_state.status = "failed"
        self.run_state.message = self._book_summary_message("Failed", event)
        self.run_state.current_stage = self._book_stage_message("Failed", event)
        self.result_state.error = str(event.get("error") or "Book failed")
        self.run_state.progress_fraction = self._progress_fraction(
            self.run_state.completed_books,
            self.run_state.total_books,
        )
        self._append_log_line(self._format_event_log(event))
        self.summary_var.set(self._status_summary())

    def _apply_run_completed(self, event: GuiEvent) -> None:
        self.run_state.status = "completed"
        self.run_state.total_books = self._int_from_event(
            event,
            "total_books",
            self.run_state.total_books,
        )
        self.run_state.completed_books = self.run_state.total_books
        self.run_state.progress_fraction = 1.0
        self.run_state.current_stage = "Run completed"
        summaries = event.get("summaries")
        if isinstance(summaries, list) and summaries:
            aggregate = self._aggregate_summaries(
                [summary for summary in summaries if isinstance(summary, dict)]
            )
            if aggregate:
                self.result_state.summary = aggregate
                self._apply_summary_metrics(aggregate)
        self.run_state.message = "Run completed"
        self.result_state.output_paths = self._compute_result_paths()
        self.result_state.audit_report_path = self._audit_report_path_for_current_request()
        self._append_log_line(self._format_event_log(event))
        self.summary_var.set(self._status_summary())
        self.status_var.set("Completed")
        self._refresh_result_actions()
        self.run_button.state(["!disabled"])
        self.progress_var.set(1.0)

    def _apply_run_failed(self, event: GuiEvent) -> None:
        self.run_state.status = "failed"
        self.run_state.message = str(event.get("error") or "Run failed")
        self.run_state.current_stage = "Run failed"
        self.result_state.error = self.run_state.message
        self.result_state.output_paths = self._compute_result_paths()
        self.result_state.audit_report_path = self._audit_report_path_for_current_request()
        self._append_log_line(self._format_event_log(event))
        self._refresh_result_actions()
        self.run_button.state(["!disabled"])
        self._sync_state_widgets()

    def _handle_start_failure(
        self,
        exc: Exception,
        *,
        request: GuiRuntimeRequest | None,
    ) -> None:
        if request is None:
            self.current_request = None
        message = str(exc) or exc.__class__.__name__
        self.run_state = GuiRunState(
            status="failed",
            current_stage="Run failed",
            message=message,
        )
        if request is not None:
            self.run_state.total_books = len(request.discovered_books) or 1
        self.result_state.error = message
        self._append_log_line(f"Run start failed: {message}")
        self.run_button.state(["!disabled"])
        self._sync_state_widgets()

    def _update_progress(self, *, completed_books: int, total_books: int) -> None:
        self.run_state.progress_fraction = self._progress_fraction(completed_books, total_books)
        self.progress_var.set(self.run_state.progress_fraction)

    def _sync_state_widgets(self) -> None:
        self.status_var.set(self._status_label())
        self.stage_var.set(self.run_state.current_stage or self._status_label())
        self.summary_var.set(self._status_summary())
        self.progress_var.set(self.run_state.progress_fraction)

    def _status_label(self) -> str:
        return self.run_state.status.replace("_", " ").title()

    def _status_summary(self) -> str:
        if self.run_state.status == "failed":
            return self.run_state.message or "Run failed"

        parts: list[str] = []
        if self.run_state.total_books:
            parts.append(f"{self.run_state.completed_books}/{self.run_state.total_books} books")
        if self.run_state.successful_chunks or self.run_state.failed_chunks:
            parts.append(
                f"{self.run_state.successful_chunks} successful chunks, "
                f"{self.run_state.failed_chunks} failed"
            )
        if self.run_state.estimated_cost_usd:
            parts.append(f"${self.run_state.estimated_cost_usd:.2f} estimated cost")
        if self.run_state.elapsed_seconds:
            parts.append(f"{self.run_state.elapsed_seconds:.1f}s elapsed")
        if self.run_state.message and self.run_state.message not in parts:
            parts.append(self.run_state.message)
        if not parts:
            return "Ready"
        return " | ".join(parts)

    def _apply_summary_metrics(self, summary: dict[str, object]) -> None:
        self.run_state.successful_chunks = self._int_from_dict(
            summary,
            "successful_chunks",
            self.run_state.successful_chunks,
        )
        self.run_state.failed_chunks = self._int_from_dict(
            summary,
            "failed_chunks",
            self.run_state.failed_chunks,
        )
        self.run_state.estimated_cost_usd = self._float_from_dict(
            summary,
            "estimated_cost_usd",
            self.run_state.estimated_cost_usd,
        )
        self.run_state.elapsed_seconds = self._float_from_dict(
            summary,
            "duration_seconds",
            self.run_state.elapsed_seconds,
        )

    def _book_summary_message(self, prefix: str, event: GuiEvent) -> str:
        book_name = str(event.get("book_name") or "book")
        book_index = self._int_from_event(event, "book_index", 0)
        total_books = self._int_from_event(event, "total_books", 0)
        if total_books:
            return f"{prefix} {book_name} ({book_index}/{total_books})"
        return f"{prefix} {book_name}"

    def _book_stage_message(self, prefix: str, event: GuiEvent) -> str:
        book_name = str(event.get("book_name") or "book")
        book_index = self._int_from_event(event, "book_index", 0)
        total_books = self._int_from_event(event, "total_books", 0)
        if total_books:
            return f"{prefix} {book_name} ({book_index}/{total_books})"
        return f"{prefix} {book_name}"

    def _format_event_log(self, event: GuiEvent) -> str:
        event_type = str(event.get("type") or "event")
        if event_type == "book_started":
            return self._book_summary_message("Started", event)
        if event_type == "book_completed":
            return self._book_summary_message("Completed", event)
        if event_type == "book_failed":
            error = str(event.get("error") or "book failed")
            return f"Failed {event.get('book_name') or 'book'}: {error}"
        if event_type == "run_started":
            total_books = self._int_from_event(event, "total_books", 0)
            return f"Run started for {total_books} book(s)"
        if event_type == "run_completed":
            total_books = self._int_from_event(event, "total_books", 0)
            return f"Run completed for {total_books} book(s)"
        if event_type == "run_failed":
            return f"Run failed: {event.get('error') or 'unknown error'}"
        return event_type

    @staticmethod
    def _int_from_dict(data: dict[str, object], key: str, default: int) -> int:
        value = data.get(key)
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return default

    @staticmethod
    def _float_from_dict(data: dict[str, object], key: str, default: float) -> float:
        value = data.get(key)
        if isinstance(value, bool):
            return default
        if isinstance(value, int | float):
            return float(value)
        return default

    @staticmethod
    def _progress_fraction(book_index: int, total_books: int) -> float:
        if total_books <= 0:
            return 0.0
        return min(1.0, max(0.0, book_index / total_books))

    def _append_log_line(self, line: str) -> None:
        self.run_state.logs.append(line)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_logs(self) -> None:
        self.run_state.logs.clear()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _compute_result_paths(self) -> tuple[Path, ...]:
        if self.current_request is None:
            return ()

        workspace = self._workspace_for_current_request()
        if workspace is None:
            return ()

        ordered_keys = (
            "open_run_summary",
            "open_translated_txt",
            "open_translated_pdf",
            "open_translated_epub",
            "open_audit_report",
        )
        path_map = self._single_book_result_paths()
        existing = tuple(
            path
            for key in ordered_keys
            if (path := path_map.get(key)) is not None and path.exists()
        )
        self.result_state.output_paths = existing
        return existing

    def _audit_report_path_for_current_request(self) -> Path | None:
        if self.current_request is None or self.current_request.mode != "publishing":
            return None
        workspace = self._workspace_for_current_request()
        if workspace is None:
            return None
        path = workspace.publishing_audit_report_path
        return path if path.exists() else None

    def _refresh_result_actions(self) -> None:
        if self.current_request is None and not self.result_state.output_paths:
            self._hide_all_result_actions()
            return

        if self.current_request is not None and len(self.current_request.discovered_books) > 1:
            self._refresh_multi_book_result_actions()
            return

        path_map = self._single_book_result_paths()

        for key, button in self.result_buttons.items():
            path = path_map.get(key)
            path_var = self.result_path_vars[key]
            if path is not None and path.exists():
                path_var.set(str(path))
                button.state(["!disabled"])
                button.configure(command=self._open_path_command(path))
                button.grid()
            else:
                path_var.set("")
                button.state(["disabled"])
                button.grid_remove()

    def _refresh_multi_book_result_actions(self) -> None:
        output_folder = self._output_folder_path()
        for key, button in self.result_buttons.items():
            path_var = self.result_path_vars[key]
            if key == "open_output_folder" and output_folder is not None and output_folder.exists():
                path_var.set(str(output_folder))
                button.state(["!disabled"])
                button.configure(command=self._open_path_command(output_folder))
                button.grid()
            else:
                path_var.set("")
                button.state(["disabled"])
                button.grid_remove()

    def _single_book_result_paths(self) -> dict[str, Path | None]:
        workspace = self._workspace_for_current_request()
        if workspace is None:
            return {}
        if self.current_request is None:
            return {}
        requested_output_kinds = self._requested_output_kinds()
        if self.current_request.mode == "engineering":
            return {
                "open_output_folder": workspace.root,
                "open_run_summary": workspace.summary_path,
                "open_translated_txt": (
                    workspace.output_path if "txt" in requested_output_kinds else None
                ),
                "open_translated_pdf": (
                    workspace.pdf_output_path if "pdf" in requested_output_kinds else None
                ),
                "open_translated_epub": None,
                "open_audit_report": None,
            }
        return {
            "open_output_folder": workspace.root,
            "open_run_summary": workspace.publishing_summary_path,
            "open_translated_txt": workspace.publishing_final_text_path,
            "open_translated_pdf": (
                workspace.publishing_final_pdf_path if "pdf" in requested_output_kinds else None
            ),
            "open_translated_epub": (
                workspace.publishing_final_epub_path
                if "epub" in requested_output_kinds
                else None
            ),
            "open_audit_report": (
                workspace.publishing_audit_report_path
                if self._publishing_audit_expected()
                else None
            ),
        }

    def _hide_all_result_actions(self) -> None:
        for key, button in self.result_buttons.items():
            button.state(["disabled"])
            button.grid_remove()
            self.result_path_vars[key].set("")

    def _output_folder_path(self) -> Path | None:
        if self.current_request is not None:
            workspace = self._workspace_for_current_request()
            if len(self.current_request.discovered_books) == 1:
                if workspace is not None:
                    return workspace.root
                return self.current_request.output_path
            return self.current_request.output_path
        if not self.result_state.output_paths:
            return None
        parents = [str(path.parent) for path in self.result_state.output_paths]
        try:
            return Path(os.path.commonpath(parents))
        except ValueError:
            return self.result_state.output_paths[0].parent

    def _workspace_for_current_request(self) -> Workspace | None:
        if self.current_request is None:
            return None
        if len(self.current_request.discovered_books) == 1:
            book = self.current_request.discovered_books[0]
            return Workspace(self.current_request.output_path / slugify(book.stem))
        return None

    def _requested_output_kinds(self) -> set[str]:
        if self.current_request is None:
            return set()
        kinds: set[str] = set()
        if self.current_request.primary_output is not None:
            kinds.add(self.current_request.primary_output)
        kinds.update(self.current_request.additional_outputs)
        return kinds

    def _publishing_audit_expected(self) -> bool:
        if self.current_request is None or self.current_request.mode != "publishing":
            return False
        return getattr(self.current_request.config, "to_stage", None) == "deep-review"

    @staticmethod
    def _aggregate_summaries(summaries: list[dict[str, object]]) -> dict[str, object]:
        aggregate = {
            "successful_chunks": 0,
            "failed_chunks": 0,
            "estimated_cost_usd": 0.0,
            "duration_seconds": 0.0,
        }
        for summary in summaries:
            aggregate["successful_chunks"] += BookTranslatorGui._int_from_dict(
                summary,
                "successful_chunks",
                0,
            )
            aggregate["failed_chunks"] += BookTranslatorGui._int_from_dict(
                summary,
                "failed_chunks",
                0,
            )
            aggregate["estimated_cost_usd"] += BookTranslatorGui._float_from_dict(
                summary,
                "estimated_cost_usd",
                0.0,
            )
            aggregate["duration_seconds"] += BookTranslatorGui._float_from_dict(
                summary,
                "duration_seconds",
                0.0,
            )
        return aggregate

    @staticmethod
    def _default_open_path(path: Path) -> None:
        if hasattr(os, "startfile"):
            os.startfile(path)  # type: ignore[attr-defined]
            return
        import webbrowser

        webbrowser.open(path.as_uri())

    def _open_path_command(self, path: Path) -> Callable[[], None]:
        return lambda: self._open_path_handler(path)

    @staticmethod
    def _path_from_var(var: tk.StringVar) -> Path | None:
        value = var.get().strip()
        if not value:
            return None
        return Path(value)

    @staticmethod
    def _int_from_event(event: GuiEvent, key: str, default: int) -> int:
        value = event.get(key)
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return default

    @staticmethod
    def _float_from_event(event: GuiEvent, key: str, default: float) -> float:
        value = event.get(key)
        if isinstance(value, bool):
            return default
        if isinstance(value, int | float):
            return float(value)
        return default


def main() -> None:
    app = BookTranslatorGui()
    app.run()
