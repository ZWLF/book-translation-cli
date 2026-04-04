from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


@dataclass(slots=True)
class GuiShellViews:
    root: tk.Tk
    mode_var: tk.StringVar
    input_path_var: tk.StringVar
    output_path_var: tk.StringVar
    provider_var: tk.StringVar
    model_var: tk.StringVar
    render_pdf_var: tk.BooleanVar
    also_pdf_var: tk.BooleanVar
    also_epub_var: tk.BooleanVar
    status_var: tk.StringVar
    stage_var: tk.StringVar
    summary_var: tk.StringVar
    progress_var: tk.DoubleVar
    publishing_frame: ttk.Frame
    publishing_advanced_frame: ttk.Frame
    publishing_expanded_var: tk.BooleanVar
    publishing_toggle_button: ttk.Button
    run_button: ttk.Button
    log_text: tk.Text
    result_buttons: dict[str, ttk.Button]
    result_path_vars: dict[str, tk.StringVar]


def build_shell(root: tk.Tk, *, mode_var: tk.StringVar) -> GuiShellViews:
    root.title("Booksmith")
    root.minsize(900, 720)

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    input_path_var = tk.StringVar(master=root, value="")
    output_path_var = tk.StringVar(master=root, value="")
    provider_var = tk.StringVar(master=root, value="openai")
    model_var = tk.StringVar(master=root, value="")
    render_pdf_var = tk.BooleanVar(master=root, value=True)
    also_pdf_var = tk.BooleanVar(master=root, value=False)
    also_epub_var = tk.BooleanVar(master=root, value=False)
    status_var = tk.StringVar(master=root, value="Idle")
    stage_var = tk.StringVar(master=root, value="Idle")
    summary_var = tk.StringVar(master=root, value="Ready")
    progress_var = tk.DoubleVar(master=root, value=0.0)
    publishing_expanded_var = tk.BooleanVar(master=root, value=False)

    outer = ttk.Frame(root, padding=18)
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)

    ttk.Label(header, text="Booksmith", font=("TkDefaultFont", 18, "bold")).grid(
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
    ttk.Entry(workspace_body, textvariable=input_path_var).grid(
        row=0,
        column=1,
        sticky="ew",
        padx=(12, 0),
    )
    ttk.Label(workspace_body, text="Output").grid(row=1, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(workspace_body, textvariable=output_path_var).grid(
        row=1,
        column=1,
        sticky="ew",
        padx=(12, 0),
        pady=(10, 0),
    )
    ttk.Label(workspace_body, text="Provider").grid(row=2, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(workspace_body, textvariable=provider_var).grid(
        row=2,
        column=1,
        sticky="ew",
        padx=(12, 0),
        pady=(10, 0),
    )
    ttk.Label(workspace_body, text="Model").grid(row=3, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(workspace_body, textvariable=model_var).grid(
        row=3,
        column=1,
        sticky="ew",
        padx=(12, 0),
        pady=(10, 0),
    )

    publishing_frame = ttk.Frame(outer)
    publishing_frame.grid(row=3, column=0, sticky="ew", pady=(18, 0))
    publishing_frame.columnconfigure(0, weight=1)

    publishing_panel = ttk.LabelFrame(publishing_frame, text="Publishing options")
    publishing_panel.grid(row=0, column=0, sticky="ew")
    publishing_panel.columnconfigure(0, weight=1)

    publishing_body = ttk.Frame(publishing_panel, padding=12)
    publishing_body.grid(row=0, column=0, sticky="ew")
    publishing_body.columnconfigure(1, weight=1)

    ttk.Label(publishing_body, text="Shown only for publishing mode.").grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="w",
    )
    ttk.Checkbutton(publishing_body, text="Also export PDF", variable=also_pdf_var).grid(
        row=1,
        column=0,
        sticky="w",
        pady=(10, 0),
    )
    ttk.Checkbutton(publishing_body, text="Also export EPUB", variable=also_epub_var).grid(
        row=1,
        column=1,
        sticky="w",
        padx=(16, 0),
        pady=(10, 0),
    )

    publishing_advanced_frame = ttk.Frame(publishing_frame)
    publishing_toggle_button = ttk.Button(publishing_frame, text="Advanced")

    run_card = ttk.LabelFrame(outer, text="Run")
    run_card.grid(row=4, column=0, sticky="ew", pady=(18, 0))
    run_card.columnconfigure(1, weight=1)

    run_body = ttk.Frame(run_card, padding=12)
    run_body.grid(row=0, column=0, sticky="ew")
    run_body.columnconfigure(1, weight=1)

    run_button = ttk.Button(run_body, text="Run")
    run_button.grid(row=0, column=0, sticky="w")
    ttk.Label(run_body, textvariable=status_var, font=("TkDefaultFont", 10, "bold")).grid(
        row=0,
        column=1,
        sticky="w",
        padx=(16, 0),
    )
    ttk.Label(run_body, text="Stage").grid(row=1, column=0, sticky="w", pady=(10, 0))
    ttk.Label(run_body, textvariable=stage_var).grid(
        row=1,
        column=1,
        sticky="w",
        padx=(16, 0),
        pady=(10, 0),
    )
    ttk.Label(run_body, textvariable=summary_var, wraplength=780).grid(
        row=2,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(10, 0),
    )
    ttk.Progressbar(
        run_body,
        orient="horizontal",
        mode="determinate",
        maximum=1.0,
        variable=progress_var,
    ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    log_frame = ttk.LabelFrame(outer, text="Logs")
    log_frame.grid(row=5, column=0, sticky="nsew", pady=(18, 0))
    log_frame.columnconfigure(0, weight=1)
    log_frame.rowconfigure(0, weight=1)
    outer.rowconfigure(5, weight=1)

    log_body = ttk.Frame(log_frame, padding=12)
    log_body.grid(row=0, column=0, sticky="nsew")
    log_body.columnconfigure(0, weight=1)
    log_body.rowconfigure(0, weight=1)

    log_text = tk.Text(log_body, height=9, wrap="word")
    log_scrollbar = ttk.Scrollbar(log_body, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=log_scrollbar.set, state="disabled")
    log_text.grid(row=0, column=0, sticky="nsew")
    log_scrollbar.grid(row=0, column=1, sticky="ns")

    results_frame = ttk.LabelFrame(outer, text="Results")
    results_frame.grid(row=6, column=0, sticky="ew", pady=(18, 0))
    results_frame.columnconfigure(1, weight=1)

    results_body = ttk.Frame(results_frame, padding=12)
    results_body.grid(row=0, column=0, sticky="ew")
    results_body.columnconfigure(1, weight=1)

    result_buttons: dict[str, ttk.Button] = {}
    result_path_vars: dict[str, tk.StringVar] = {}

    result_specs = [
        ("open_output_folder", "Output folder"),
        ("open_run_summary", "Run summary"),
        ("open_translated_txt", "translated.txt"),
        ("open_translated_pdf", "translated.pdf"),
        ("open_translated_epub", "translated.epub"),
        ("open_audit_report", "final_audit_report.json"),
    ]
    for row_index, (key, label) in enumerate(result_specs):
        path_var = tk.StringVar(master=root, value="")
        result_path_vars[key] = path_var
        ttk.Label(results_body, text=label).grid(row=row_index, column=0, sticky="w")
        button = ttk.Button(results_body, text="Open")
        button.grid(row=row_index, column=1, sticky="w", padx=(12, 0), pady=(0, 6))
        ttk.Label(results_body, textvariable=path_var).grid(
            row=row_index,
            column=2,
            sticky="w",
            padx=(12, 0),
        )
        result_buttons[key] = button
        button.grid_remove()

    footer = ttk.Label(
        outer,
        text="Run controls and progress are wired to the local task runner.",
        foreground="#555555",
    )
    footer.grid(row=7, column=0, sticky="w", pady=(18, 0))

    publishing_frame.grid_remove()
    return GuiShellViews(
        root=root,
        mode_var=mode_var,
        input_path_var=input_path_var,
        output_path_var=output_path_var,
        provider_var=provider_var,
        model_var=model_var,
        render_pdf_var=render_pdf_var,
        also_pdf_var=also_pdf_var,
        also_epub_var=also_epub_var,
        status_var=status_var,
        stage_var=stage_var,
        summary_var=summary_var,
        progress_var=progress_var,
        publishing_frame=publishing_frame,
        publishing_advanced_frame=publishing_advanced_frame,
        publishing_expanded_var=publishing_expanded_var,
        publishing_toggle_button=publishing_toggle_button,
        run_button=run_button,
        log_text=log_text,
        result_buttons=result_buttons,
        result_path_vars=result_path_vars,
    )
