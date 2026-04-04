from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


@dataclass(slots=True)
class GuiShellViews:
    root: tk.Tk
    mode_var: tk.StringVar
    publishing_frame: ttk.LabelFrame


def build_shell(root: tk.Tk, *, mode_var: tk.StringVar) -> GuiShellViews:
    root.title("Book Translator")
    root.minsize(900, 620)

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    outer = ttk.Frame(root, padding=18)
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)

    ttk.Label(header, text="Book Translator", font=("TkDefaultFont", 18, "bold")).grid(
        row=0,
        column=0,
        sticky="w",
    )
    ttk.Label(
        header,
        text="A lightweight desktop shell for engineering and publishing workflows.",
    ).grid(row=1, column=0, sticky="w", pady=(6, 0))

    mode_card = ttk.LabelFrame(outer, text="Mode")
    mode_card.grid(row=1, column=0, sticky="ew", pady=(18, 0))
    mode_card.columnconfigure(0, weight=1)

    mode_row = ttk.Frame(mode_card, padding=12)
    mode_row.grid(row=0, column=0, sticky="ew")

    ttk.Radiobutton(
        mode_row,
        text="Engineering",
        value="engineering",
        variable=mode_var,
    ).grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(
        mode_row,
        text="Publishing",
        value="publishing",
        variable=mode_var,
    ).grid(row=0, column=1, sticky="w", padx=(16, 0))

    workspace_card = ttk.LabelFrame(outer, text="Workspace")
    workspace_card.grid(row=2, column=0, sticky="ew", pady=(18, 0))
    workspace_card.columnconfigure(1, weight=1)

    workspace_body = ttk.Frame(workspace_card, padding=12)
    workspace_body.grid(row=0, column=0, sticky="ew")
    workspace_body.columnconfigure(1, weight=1)

    ttk.Label(workspace_body, text="Input").grid(row=0, column=0, sticky="w")
    ttk.Entry(workspace_body).grid(row=0, column=1, sticky="ew", padx=(12, 0))
    ttk.Label(workspace_body, text="Output").grid(row=1, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(workspace_body).grid(
        row=1,
        column=1,
        sticky="ew",
        padx=(12, 0),
        pady=(10, 0),
    )

    publishing_frame = ttk.LabelFrame(outer, text="Publishing options")
    publishing_frame.grid(row=3, column=0, sticky="ew", pady=(18, 0))
    publishing_frame.columnconfigure(0, weight=1)

    publishing_body = ttk.Frame(publishing_frame, padding=12)
    publishing_body.grid(row=0, column=0, sticky="ew")
    publishing_body.columnconfigure(1, weight=1)

    ttk.Label(publishing_body, text="Shown only for publishing mode.").grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="w",
    )
    ttk.Checkbutton(publishing_body, text="Also export PDF").grid(
        row=1,
        column=0,
        sticky="w",
        pady=(10, 0),
    )
    ttk.Checkbutton(publishing_body, text="Also export EPUB").grid(
        row=1,
        column=1,
        sticky="w",
        padx=(16, 0),
        pady=(10, 0),
    )

    footer = ttk.Label(
        outer,
        text="Run controls and progress will be wired in a later task.",
        foreground="#555555",
    )
    footer.grid(row=4, column=0, sticky="w", pady=(18, 0))

    publishing_frame.grid_remove()
    return GuiShellViews(root=root, mode_var=mode_var, publishing_frame=publishing_frame)
