from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


@dataclass(slots=True)
class GuiShellViews:
    root: tk.Tk
    mode_var: tk.StringVar
    input_path_var: tk.StringVar
    input_path_entry: ttk.Entry
    input_browse_button: ttk.Button
    output_path_var: tk.StringVar
    output_path_entry: ttk.Entry
    output_browse_button: ttk.Button
    provider_var: tk.StringVar
    provider_combobox: ttk.Combobox
    api_key_var: tk.StringVar
    api_key_visible_var: tk.BooleanVar
    api_key_entry: ttk.Entry
    api_key_toggle_button: ttk.Button
    remember_locally_var: tk.BooleanVar
    remember_locally_checkbutton: ttk.Checkbutton
    model_var: tk.StringVar
    model_combobox: ttk.Combobox
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


def _add_section_heading(
    parent: ttk.Frame,
    *,
    row: int,
    zh_text: str,
    en_text: str,
    top_padding: int = 0,
) -> None:
    heading = ttk.Frame(parent)
    heading.grid(row=row, column=0, sticky="ew", pady=(top_padding, 0))
    heading.columnconfigure(0, weight=1)

    ttk.Label(heading, text=zh_text, font=("TkDefaultFont", 12, "bold")).grid(
        row=0,
        column=0,
        sticky="w",
    )
    ttk.Label(heading, text=en_text).grid(row=1, column=0, sticky="w", pady=(2, 0))


def build_shell(root: tk.Tk, *, mode_var: tk.StringVar) -> GuiShellViews:
    root.title("Booksmith")
    root.minsize(900, 720)

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    input_path_var = tk.StringVar(master=root, value="")
    output_path_var = tk.StringVar(master=root, value="")
    provider_var = tk.StringVar(master=root, value="openai")
    api_key_var = tk.StringVar(master=root, value="")
    api_key_visible_var = tk.BooleanVar(master=root, value=False)
    remember_locally_var = tk.BooleanVar(master=root, value=False)
    model_var = tk.StringVar(master=root, value="gpt-4o-mini")
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
    outer.rowconfigure(10, weight=1)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)

    ttk.Label(header, text="书匠", font=("TkDefaultFont", 18, "bold")).grid(
        row=0,
        column=0,
        sticky="w",
    )
    ttk.Label(header, text="Booksmith", font=("TkDefaultFont", 11)).grid(
        row=1,
        column=0,
        sticky="w",
        pady=(4, 0),
    )
    ttk.Label(
        header,
        text="工程与出版桌面工作台",
    ).grid(row=2, column=0, sticky="w", pady=(8, 0))
    ttk.Label(
        header,
        text="Engineering and publishing desktop workspace",
    ).grid(row=3, column=0, sticky="w", pady=(2, 0))

    _add_section_heading(
        outer,
        row=1,
        zh_text="工作区",
        en_text="Workspace",
        top_padding=18,
    )
    workspace_section = ttk.Frame(outer)
    workspace_section.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    workspace_section.columnconfigure(0, weight=1)

    workspace_body = ttk.Frame(workspace_section, padding=(0, 0, 0, 4))
    workspace_body.grid(row=0, column=0, sticky="ew")
    workspace_body.columnconfigure(0, weight=1)

    provider_options = ("openai", "gemini")
    model_options = ("gpt-4o-mini", "gpt-4.1-mini")

    input_row = ttk.Frame(workspace_body)
    input_row.grid(row=0, column=0, sticky="ew")
    input_row.columnconfigure(1, weight=1)
    ttk.Label(input_row, text="Input / 输入书籍").grid(row=0, column=0, sticky="w")
    input_path_entry = ttk.Entry(input_row, textvariable=input_path_var)
    input_path_entry.grid(row=0, column=1, sticky="ew", padx=(12, 0))
    input_browse_button = ttk.Button(input_row, text="Browse / 浏览文件", width=14)
    input_browse_button.grid(row=0, column=2, sticky="e", padx=(12, 0))

    output_row = ttk.Frame(workspace_body)
    output_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    output_row.columnconfigure(1, weight=1)
    ttk.Label(output_row, text="Output / 输出目录").grid(row=0, column=0, sticky="w")
    output_path_entry = ttk.Entry(output_row, textvariable=output_path_var)
    output_path_entry.grid(row=0, column=1, sticky="ew", padx=(12, 0))
    output_browse_button = ttk.Button(output_row, text="Browse / 浏览目录", width=14)
    output_browse_button.grid(row=0, column=2, sticky="e", padx=(12, 0))

    ttk.Label(
        workspace_body,
        text="Workspace output / 工作区输出目录: translated PDF, EPUB, TXT, and audit artifacts are stored here.",
        wraplength=760,
        foreground="#555555",
    ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    provider_row = ttk.Frame(workspace_body)
    provider_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
    provider_row.columnconfigure(1, weight=1)
    ttk.Label(provider_row, text="Provider API / 服务商 API").grid(row=0, column=0, sticky="w")
    provider_combobox = ttk.Combobox(
        provider_row,
        textvariable=provider_var,
        values=provider_options,
        state="readonly",
    )
    provider_combobox.grid(row=0, column=1, sticky="ew", padx=(12, 0))

    api_key_row = ttk.Frame(workspace_body)
    api_key_row.grid(row=4, column=0, sticky="ew", pady=(10, 0))
    api_key_row.columnconfigure(1, weight=1)
    ttk.Label(api_key_row, text="API Key / 密钥").grid(row=0, column=0, sticky="w")
    api_key_entry = ttk.Entry(api_key_row, textvariable=api_key_var, show="*")
    api_key_entry.grid(row=0, column=1, sticky="ew", padx=(12, 0))
    api_key_toggle_button = ttk.Button(api_key_row, text="Show / 显示", width=12)
    api_key_toggle_button.grid(row=0, column=2, sticky="e", padx=(12, 0))
    remember_locally_checkbutton = ttk.Checkbutton(
        api_key_row,
        text="Remember locally / 本地记住",
        variable=remember_locally_var,
    )
    remember_locally_checkbutton.grid(row=1, column=1, columnspan=2, sticky="w", pady=(6, 0))

    model_row = ttk.Frame(workspace_body)
    model_row.grid(row=5, column=0, sticky="ew", pady=(10, 0))
    model_row.columnconfigure(1, weight=1)
    ttk.Label(model_row, text="Model / 模型").grid(row=0, column=0, sticky="w")
    model_combobox = ttk.Combobox(
        model_row,
        textvariable=model_var,
        values=model_options,
        state="readonly",
    )
    model_combobox.grid(row=0, column=1, sticky="ew", padx=(12, 0))

    _add_section_heading(
        outer,
        row=3,
        zh_text="输出与选项",
        en_text="Output & options",
        top_padding=18,
    )
    options_section = ttk.Frame(outer)
    options_section.grid(row=4, column=0, sticky="ew", pady=(10, 0))
    options_section.columnconfigure(0, weight=1)

    options_body = ttk.Frame(options_section, padding=(0, 0, 0, 4))
    options_body.grid(row=0, column=0, sticky="ew")
    options_body.columnconfigure(0, weight=1)

    mode_row = ttk.Frame(options_body)
    mode_row.grid(row=0, column=0, sticky="w")

    ttk.Label(mode_row, text="模式 / Mode").grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(
        mode_row,
        text="Engineering",
        value="engineering",
        variable=mode_var,
    ).grid(row=0, column=1, sticky="w", padx=(16, 0))
    ttk.Radiobutton(
        mode_row,
        text="Publishing",
        value="publishing",
        variable=mode_var,
    ).grid(row=0, column=2, sticky="w", padx=(16, 0))

    publishing_frame = ttk.Frame(options_body)
    publishing_frame.grid(row=1, column=0, sticky="ew", pady=(14, 0))
    publishing_frame.columnconfigure(0, weight=1)

    ttk.Label(
        publishing_frame,
        text="出版选项",
        font=("TkDefaultFont", 11, "bold"),
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(publishing_frame, text="Publishing options").grid(
        row=1,
        column=0,
        sticky="w",
        pady=(2, 0),
    )

    publishing_body = ttk.Frame(publishing_frame)
    publishing_body.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    publishing_body.columnconfigure(1, weight=1)

    ttk.Label(publishing_body, text="Shown only for publishing mode.").grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="w",
    )
    publishing_toggle_button = ttk.Button(
        publishing_body,
        text="高级选项 / Advanced",
    )
    publishing_toggle_button.grid(row=1, column=0, sticky="w", pady=(10, 0))
    publishing_advanced_frame = ttk.Frame(publishing_frame)
    publishing_advanced_frame.columnconfigure(0, weight=1)
    publishing_advanced_frame.columnconfigure(1, weight=1)

    ttk.Checkbutton(
        publishing_advanced_frame,
        text="Also export PDF",
        variable=also_pdf_var,
    ).grid(row=0, column=0, sticky="w")
    ttk.Checkbutton(
        publishing_advanced_frame,
        text="Also export EPUB",
        variable=also_epub_var,
    ).grid(row=0, column=1, sticky="w", padx=(16, 0))

    _add_section_heading(
        outer,
        row=5,
        zh_text="运行状态",
        en_text="Run status",
        top_padding=18,
    )
    run_section = ttk.Frame(outer)
    run_section.grid(row=6, column=0, sticky="ew", pady=(10, 0))
    run_section.columnconfigure(0, weight=1)

    run_body = ttk.Frame(run_section, padding=(0, 0, 0, 4))
    run_body.grid(row=0, column=0, sticky="ew")
    run_body.columnconfigure(0, weight=1)

    run_action_row = ttk.Frame(run_body)
    run_action_row.grid(row=0, column=0, sticky="ew")
    run_action_row.columnconfigure(1, weight=1)

    run_button = ttk.Button(run_action_row, text="Run", width=14)
    run_button.grid(row=0, column=0, sticky="w")
    ttk.Label(
        run_action_row,
        textvariable=status_var,
        font=("TkDefaultFont", 10, "bold"),
    ).grid(
        row=0,
        column=1,
        sticky="w",
        padx=(16, 0),
    )

    run_meta_row = ttk.Frame(run_body)
    run_meta_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    run_meta_row.columnconfigure(1, weight=1)

    ttk.Label(run_meta_row, text="Current step").grid(row=0, column=0, sticky="w")
    ttk.Label(run_meta_row, textvariable=stage_var).grid(
        row=0,
        column=1,
        sticky="w",
        padx=(16, 0),
    )
    ttk.Label(run_body, textvariable=summary_var, wraplength=760).grid(
        row=2,
        column=0,
        sticky="w",
        pady=(10, 0),
    )
    ttk.Progressbar(
        run_body,
        orient="horizontal",
        mode="determinate",
        maximum=1.0,
        variable=progress_var,
    ).grid(row=3, column=0, sticky="ew", pady=(12, 0))

    _add_section_heading(
        outer,
        row=7,
        zh_text="结果",
        en_text="Results",
        top_padding=18,
    )
    results_section = ttk.Frame(outer)
    results_section.grid(row=8, column=0, sticky="ew", pady=(10, 0))
    results_section.columnconfigure(0, weight=1)

    results_body = ttk.Frame(results_section, padding=(0, 0, 0, 4))
    results_body.grid(row=0, column=0, sticky="ew")
    results_body.columnconfigure(0, weight=1)

    ttk.Label(results_body, text="Ready artifacts appear here when a run finishes.").grid(
        row=0,
        column=0,
        sticky="w",
    )

    results_actions = ttk.Frame(results_body)
    results_actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    results_actions.columnconfigure(1, weight=1)

    result_buttons: dict[str, ttk.Button] = {}
    result_path_vars: dict[str, tk.StringVar] = {}

    result_specs = [
        ("open_output_folder", "Open output folder"),
        ("open_run_summary", "Open run summary"),
        ("open_translated_txt", "Open translated text"),
        ("open_translated_pdf", "Open translated PDF"),
        ("open_translated_epub", "Open translated EPUB"),
        ("open_audit_report", "Open audit report"),
    ]
    for row_index, (key, label) in enumerate(result_specs):
        path_var = tk.StringVar(master=root, value="")
        result_path_vars[key] = path_var
        button = ttk.Button(results_actions, text=label, width=22)
        button.grid(row=row_index, column=0, sticky="w", pady=(0, 6))
        ttk.Label(results_actions, textvariable=path_var, wraplength=540).grid(
            row=row_index,
            column=1,
            sticky="w",
            padx=(12, 0),
        )
        result_buttons[key] = button
        button.grid_remove()

    _add_section_heading(
        outer,
        row=9,
        zh_text="日志",
        en_text="Logs",
        top_padding=18,
    )
    log_section = ttk.Frame(outer)
    log_section.grid(row=10, column=0, sticky="nsew", pady=(10, 0))
    log_section.columnconfigure(0, weight=1)
    log_section.rowconfigure(0, weight=1)

    log_body = ttk.Frame(log_section, padding=(0, 0, 0, 4))
    log_body.grid(row=0, column=0, sticky="nsew")
    log_body.columnconfigure(0, weight=1)
    log_body.rowconfigure(1, weight=1)

    ttk.Label(log_body, text="Recent events").grid(row=0, column=0, sticky="w", pady=(0, 8))

    log_text = tk.Text(log_body, height=7, wrap="word")
    log_scrollbar = ttk.Scrollbar(log_body, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=log_scrollbar.set, state="disabled")
    log_text.grid(row=1, column=0, sticky="nsew")
    log_scrollbar.grid(row=1, column=1, sticky="ns")

    footer = ttk.Label(
        outer,
        text="Run controls and progress are wired to the local task runner.",
        foreground="#555555",
    )
    footer.grid(row=11, column=0, sticky="w", pady=(18, 0))

    publishing_frame.grid_remove()
    return GuiShellViews(
        root=root,
        mode_var=mode_var,
        input_path_var=input_path_var,
        input_path_entry=input_path_entry,
        input_browse_button=input_browse_button,
        output_path_var=output_path_var,
        output_path_entry=output_path_entry,
        output_browse_button=output_browse_button,
        provider_var=provider_var,
        provider_combobox=provider_combobox,
        api_key_var=api_key_var,
        api_key_visible_var=api_key_visible_var,
        api_key_entry=api_key_entry,
        api_key_toggle_button=api_key_toggle_button,
        remember_locally_var=remember_locally_var,
        remember_locally_checkbutton=remember_locally_checkbutton,
        model_var=model_var,
        model_combobox=model_combobox,
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
