from __future__ import annotations

from collections.abc import Callable, Mapping
from queue import Queue
from threading import Thread
from typing import Any

from book_translator.app_services import (
    run_engineering_books_sync,
    run_publishing_books_sync,
)

from .state import GuiRuntimeRequest

GuiEvent = dict[str, object]
RunnerFn = Callable[..., Any]


class GuiTaskRunner:
    def __init__(
        self,
        *,
        event_queue: Queue[GuiEvent],
        run_engineering_fn: RunnerFn = run_engineering_books_sync,
        run_publishing_fn: RunnerFn = run_publishing_books_sync,
    ) -> None:
        self._event_queue = event_queue
        self._run_engineering_fn = run_engineering_fn
        self._run_publishing_fn = run_publishing_fn
        self._thread: Thread | None = None

    def start(self, request: GuiRuntimeRequest) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("GuiTaskRunner is already running")

        self._thread = Thread(target=self._run_request, args=(request,), daemon=True)
        self._thread.start()

    def join(self, timeout: float | None = None) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _run_request(self, request: GuiRuntimeRequest) -> None:
        terminal_event_type: str | None = None

        def listener(event: GuiEvent) -> None:
            nonlocal terminal_event_type
            self._event_queue.put(dict(event))
            event_type = event.get("type")
            if event_type in {"run_completed", "run_failed"}:
                terminal_event_type = str(event_type)

        try:
            runner = self._runner_for_mode(request.mode)
            result = runner(
                input_path=request.input_path,
                output_path=request.output_path,
                config=request.config,
                event_listener=listener,
            )
        except Exception as exc:
            if terminal_event_type is None:
                self._emit_run_failed(request, str(exc), summaries=())
            return

        if terminal_event_type is not None:
            return

        try:
            summaries = self._normalize_summaries(result)
            self._emit_run_completed(request, summaries)
        except Exception as exc:
            if terminal_event_type is None:
                self._emit_run_failed(request, str(exc), summaries=())

    def _runner_for_mode(self, mode: str) -> RunnerFn:
        if mode == "engineering":
            return self._run_engineering_fn
        if mode == "publishing":
            return self._run_publishing_fn
        raise ValueError(f"unsupported GUI runtime mode: {mode}")

    def _emit_run_completed(
        self,
        request: GuiRuntimeRequest,
        summaries: list[dict[str, object]],
    ) -> None:
        self._event_queue.put(
            {
                "type": "run_completed",
                "mode": request.mode,
                "input_path": str(request.input_path),
                "output_path": str(request.output_path),
                "total_books": len(request.discovered_books) or 1,
                "summaries": summaries,
            }
        )

    def _emit_run_failed(
        self,
        request: GuiRuntimeRequest,
        error: str,
        *,
        summaries: tuple[dict[str, object], ...] | list[dict[str, object]],
    ) -> None:
        self._event_queue.put(
            {
                "type": "run_failed",
                "mode": request.mode,
                "input_path": str(request.input_path),
                "output_path": str(request.output_path),
                "total_books": len(request.discovered_books) or 1,
                "summaries": list(summaries),
                "error": error,
            }
        )

    def _normalize_summaries(self, result: Any) -> list[dict[str, object]]:
        if result is None:
            return []
        if isinstance(result, list):
            items = result
        elif isinstance(result, tuple):
            items = list(result)
        else:
            items = [result]

        normalized: list[dict[str, object]] = []
        for item in items:
            if isinstance(item, Mapping):
                normalized.append(dict(item))
                continue
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                normalized.append(dict(model_dump()))
                continue
            normalized.append(dict(item))
        return normalized
