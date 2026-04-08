from __future__ import annotations

import tomllib
from pathlib import Path


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
