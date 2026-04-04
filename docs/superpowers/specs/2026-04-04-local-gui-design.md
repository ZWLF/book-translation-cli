# Local GUI Design

Date: 2026-04-04

## Summary

Add a lightweight local desktop GUI on top of the existing Python CLI so the most common book
translation workflows can be run without typing commands. The GUI must remain separate from the CLI:
users should be able to keep using command-line workflows exactly as they do today, or launch a GUI
window and run the same translation system visually. The GUI should not replace the CLI and must
not fork business logic. It should reuse the current `engineering` and `publishing` pipelines, the
existing config objects, and the same output semantics that already exist in the command-line tool.

The GUI is intended to make the current tool easier to operate for single-book and small-batch
translation runs while preserving the current technical architecture:

- `engineering` remains the fast and resumable workflow
- `publishing` remains the quality-first editorial workflow
- default output behavior still depends on input format
- optional cross-format output must still be explicit

This phase adds a local desktop interface, not a web app, not an Electron app, and not a new API
server.

## Goals

- Add a stable local GUI that runs on the same machine as the current CLI.
- Preserve the CLI as a first-class entry point for advanced and scriptable use.
- Add a separate GUI entry point for users who prefer direct interaction instead of command syntax.
- Reuse the existing pipeline layer instead of shelling out to CLI commands.
- Support both `engineering` and `publishing` modes.
- Support single-file and directory-based input.
- Preserve current output semantics:
  - `PDF -> PDF`
  - `EPUB -> EPUB`
  - explicit `also_pdf` / `also_epub`
- Show progress, stage status, summary metrics, and errors while a run is active.
- Allow users to open the output folder and key result files directly from the GUI.
- Keep the first version small, predictable, and native-feeling on Windows.

## Non-Goals

- No browser-based GUI in this phase.
- No remote job runner, queue server, or web API.
- No task scheduler or multi-user collaboration UI.
- No embedded side-by-side manuscript editor.
- No visual PDF proofing canvas in this phase.
- No attempt to replace all CLI commands; utility commands can stay CLI-only if they are secondary.

## Recommended Approach

Use Python `tkinter` with `ttk` widgets as the first GUI implementation.

### Why tkinter

- already available in standard Python on Windows in most local environments
- lowest dependency cost
- easiest fit for a utility-style desktop application
- adequate for forms, progress, log windows, and file-open actions

### Why not PySide6 first

- larger dependency footprint
- packaging and environment setup become heavier immediately
- overkill for the first utility GUI pass

### Why not a web UI first

- would require a second application surface and local server lifecycle
- would duplicate desktop concerns already solved by native file dialogs
- creates more architecture than this tool needs right now

## Product Shape

The GUI is a thin control surface over the current pipelines.

The product should expose two parallel entry methods:

- **CLI entry**
  - users run `book-translator ...` from the terminal
  - this remains the primary automation-friendly interface
- **GUI entry**
  - users launch a dedicated GUI application window
  - this is the beginner-friendly interface

These are two fronts for the same translation engine, not two separate products.

It should offer one window with four functional areas:

### 1. Job Setup

- input path chooser
- output path chooser
- mode selector:
  - `engineering`
  - `publishing`
- provider selector
- model input

### 2. Run Options

Mode-aware options:

- shared:
  - resume
  - force
  - chunk size
  - max concurrency
  - chapter strategy
  - glossary path
  - name map path
  - render PDF toggle
- publishing only:
  - style
  - from stage
  - to stage
  - audit depth
  - cross review toggle
  - image policy
  - also PDF
  - also EPUB

The UI should hide or disable publishing-only options when `engineering` is selected.

### 3. Active Run Status

- progress bar
- current book name
- current stage or state
- chunk success / failure counters
- estimated cost
- elapsed time
- scrolling log output

### 4. Results

After completion, the GUI should expose buttons for:

- open output folder
- open final `PDF` if present
- open final `EPUB` if present
- open final audit report if present

## Core User Flows

### Flow A: Single PDF in engineering mode

1. User selects a single `PDF`.
2. GUI auto-sets default output expectations to `PDF`.
3. User chooses provider/model and clicks Run.
4. GUI runs `process_book(...)` in the background.
5. GUI shows progress and final summary.
6. User opens the resulting `translated.pdf` or output folder.

### Flow B: Single PDF in publishing mode with EPUB add-on

1. User selects a single `PDF`.
2. GUI defaults to `PDF` primary output.
3. User switches to `publishing`.
4. User enables `also_epub`.
5. GUI runs `process_book_publishing(...)`.
6. GUI shows stage updates and final metrics.
7. User opens `translated.pdf`, `translated.epub`, or the audit report.

### Flow C: Directory batch

1. User selects a directory.
2. GUI scans for supported files.
3. GUI shows a pre-run count.
4. User starts the run.
5. GUI shows overall progress per book and rolling log output.

## Architecture

The GUI should be a new layer above the current application service boundary.

Launch behavior should also be explicit and separate:

- keep the current CLI script:
  - `book-translator`
- add a GUI launch path such as:
  - `book-translator gui`
  - and/or a Python module entry such as `python -m book_translator.gui`

The exact launch command can be finalized during implementation, but the GUI must be independently
launchable and must not interfere with current CLI behavior.

### Desired layering

1. **Pipelines**
   - existing `process_book(...)`
   - existing `process_book_publishing(...)`

2. **GUI service layer**
   - converts form state into `RunConfig` / `PublishingRunConfig`
   - resolves expected output paths
   - emits structured progress events

3. **GUI view layer**
   - windows
   - forms
   - progress widgets
   - result actions

The GUI must call Python functions directly. It must not spawn `book-translator ...` subprocesses
for normal runs.

## New Modules

The first GUI pass should introduce a small, clear module set:

### `src/book_translator/gui/app.py`

Desktop app entry point and window bootstrap.

### `src/book_translator/gui/state.py`

UI state container:

- selected mode
- selected input/output paths
- toggles and options
- current run state
- latest summary
- available result paths

### `src/book_translator/gui/services.py`

Bridges GUI state to runtime behavior:

- build `RunConfig`
- build `PublishingRunConfig`
- validate fields before run
- compute expected outputs for display

### `src/book_translator/gui/tasks.py`

Background execution bridge:

- runs the selected pipeline off the main UI thread
- forwards status events back to the GUI
- handles completion and failure

### `src/book_translator/gui/views.py`

Reusable view construction for:

- job form
- publishing option panel
- progress panel
- result/action panel

If this file grows too large during implementation, split it further by panel.

## Shared Service Boundary

Before the GUI is implemented, extract or formalize a small shared execution helper from the CLI.

The CLI currently owns:

- config assembly
- book discovery
- progress display
- pipeline invocation

The GUI should not copy those rules. It should consume a shared service boundary that can:

- discover books
- validate input/output
- invoke the correct pipeline
- report progress and summaries in a renderer-agnostic format

This shared boundary should be usable by both:

- `cli.py`
- the new GUI

## Progress Model

The GUI should not try to parse console text.

Instead, the service layer should expose structured progress events such as:

- run started
- book discovered
- book started
- stage changed
- book completed
- run completed
- run failed

Each event should carry enough context for the GUI to render status without string parsing.

## Validation Rules

The GUI should validate before starting:

- input path exists
- output path is provided
- provider is selected
- model is present when required
- publishing-only options are internally consistent
- `also_pdf` and `also_epub` do not conflict with primary output semantics

Validation errors should be shown inline in the window, not only in logs.

## Result Path Semantics

The GUI must respect current output semantics exactly:

- engineering:
  - final text always available when successful
  - PDF only if enabled and render succeeds
- publishing:
  - primary output determined by input extension
  - extra format only when explicitly requested

The result panel should show only files that actually exist.

## Error Handling

Errors should be separated into:

- validation errors before run
- pipeline/runtime errors during run
- partial-success outcomes where output exists but some chunks or files failed

The GUI should always preserve the raw exception text in the log panel for debugging, but show a
clear user-facing summary message in the status area.

## Testing Strategy

### Unit tests

- GUI config conversion
- mode-aware field visibility rules
- output expectation logic
- validation rules

### Integration tests

- background task invokes `process_book(...)` correctly
- background task invokes `process_book_publishing(...)` correctly
- completion updates result paths and summary state
- failure updates status and log state

### GUI smoke tests

Keep these light. The first phase only needs confidence that:

- window bootstrap works
- state updates do not crash
- clicking Run with mocked services enters a running state and exits cleanly

## Documentation

After implementation, update:

- `README.md`
- `README.zh-CN.md`
- `README.ja.md`

The docs should describe:

- how to launch the GUI
- what workflows are supported
- how GUI output maps to CLI behavior
- that CLI remains the source of truth for advanced operations

## Risks

### 1. UI freeze risk

If pipelines run on the main thread, the GUI will appear broken. Background execution is mandatory.

### 2. Logic drift risk

If GUI and CLI each build runtime behavior differently, they will diverge. Shared execution helpers
must be introduced early.

### 3. Scope creep risk

Trying to build a “full desktop product” immediately will slow everything down. The first release
must stay focused on translating books with visible progress and easy result access.

## Acceptance Criteria

The first GUI release is successful if all of the following are true:

- A user can still run the full translation system from the CLI exactly as before.
- A user can process a single book without using the command line.
- Both `engineering` and `publishing` modes can be launched from the GUI.
- Output behavior matches CLI semantics for `PDF`, `EPUB`, and explicit cross-format options.
- The window remains responsive during long-running work.
- Users can see progress, summary metrics, and final output locations.
- The GUI can open generated result files or the workspace folder directly.
- The CLI remains fully functional and unchanged in behavior.

## Final Recommendation

Implement the GUI as a lightweight native desktop shell around the existing Python pipelines. Keep
the first version intentionally narrow:

- local only
- single-window
- native file pickers
- background execution
- explicit result access

That delivers the main usability gain without compromising the current architecture.
