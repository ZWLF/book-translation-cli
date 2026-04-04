from __future__ import annotations

import tkinter as tk
import tomllib
from pathlib import Path

import pytest

from book_translator.gui.app import BookTranslatorGui


def _create_gui() -> BookTranslatorGui:
    try:
        probe = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable in this environment: {exc}")
    else:
        probe.destroy()
    return BookTranslatorGui()


def test_gui_app_bootstraps_without_mainloop() -> None:
    app = _create_gui()
    try:
        assert app.root.title() == "Book Translator"
        assert app.mode_var.get() == "engineering"
        assert app.publishing_frame.winfo_manager() == ""
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


def test_gui_entry_points_are_declarable() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["book-translator-gui"] == "book_translator.gui.app:main"

    from book_translator.gui import __main__ as module_main

    assert callable(module_main.main)
