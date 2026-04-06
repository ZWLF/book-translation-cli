# Booksmith GUI UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the local Booksmith GUI into a calmer, cleaner, performance-first single-page workspace without changing pipeline semantics.

**Architecture:** Keep the current Tkinter/ttk shell and task runner model, but refactor the view layer into a stronger single-page layout with clearer hierarchy, bilingual labels, an inline advanced-options expander, and better run/result presentation. Keep behavior changes minimal and isolate them mostly to the GUI view/build layer plus narrow app-state glue and tests.

**Tech Stack:** Python 3.11+, Tkinter/ttk, pytest, Ruff

---

### Task 1: Reshape The GUI View Model For The New Layout

**Files:**
- Modify: `H:\AI_Apps\booksmith\src\booksmith\gui\views.py`
- Test: `H:\AI_Apps\booksmith\tests\test_gui_app.py`

- [ ] **Step 1: Add the new view references to `GuiShellViews`**

Update the dataclass fields in `src/booksmith/gui/views.py` so the app layer can control the new UI parts directly:

```python
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
```

- [ ] **Step 2: Run the GUI tests to verify the current code now fails**

Run:

```bash
python -m pytest -q tests/test_gui_app.py
```

Expected:

```text
FAIL because `build_shell()` does not yet populate the new GUI view fields.
```

- [ ] **Step 3: Update `build_shell()` to instantiate the new view-state variables**

Add the expander state and return values in `src/booksmith/gui/views.py`:

```python
publishing_expanded_var = tk.BooleanVar(master=root, value=False)
publishing_frame = ttk.Frame(outer)
publishing_advanced_frame = ttk.Frame(publishing_frame)
publishing_toggle_button = ttk.Button(publishing_frame, text="高级选项 / Advanced")
```

Return them through `GuiShellViews(...)`.

- [ ] **Step 4: Run the GUI tests again**

Run:

```bash
python -m pytest -q tests/test_gui_app.py
```

Expected:

```text
The tests still fail, but now due to layout and behavior expectations rather than missing fields.
```

- [ ] **Step 5: Commit the view-model groundwork**

```bash
git add src/booksmith/gui/views.py tests/test_gui_app.py
git commit -m "refactor: prepare GUI view model for polished layout"
```

### Task 2: Rebuild The Single-Page Layout With Cleaner Hierarchy

**Files:**
- Modify: `H:\AI_Apps\booksmith\src\booksmith\gui\views.py`
- Test: `H:\AI_Apps\booksmith\tests\test_gui_app.py`

- [ ] **Step 1: Add failing assertions for the new layout structure**

Extend `tests/test_gui_app.py` with expectations for:

- bilingual window shell labels
- visible core sections
- publishing advanced section collapsed by default

Use assertions like:

```python
def test_gui_defaults_to_collapsed_publishing_advanced_area() -> None:
    app = _create_gui()
    try:
        assert app.views.publishing_expanded_var.get() is False
        assert app.views.publishing_advanced_frame.winfo_manager() == ""
    finally:
        app.root.destroy()
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
python -m pytest -q tests/test_gui_app.py::test_gui_defaults_to_collapsed_publishing_advanced_area
```

Expected:

```text
FAIL because the advanced publishing region is not yet collapsed and managed with the new layout.
```

- [ ] **Step 3: Replace the current heavy card layout with the new section order**

In `src/booksmith/gui/views.py`, rebuild `build_shell()` around:

- header
- core configuration section
- output/options section
- run status section
- results section
- logs section

Use a lighter structure like:

```python
outer = ttk.Frame(root, padding=20)
header = ttk.Frame(outer)
config_section = ttk.Frame(outer, padding=(0, 14))
options_section = ttk.Frame(outer, padding=(0, 14))
run_section = ttk.Frame(outer, padding=(0, 14))
results_section = ttk.Frame(outer, padding=(0, 14))
logs_section = ttk.Frame(outer, padding=(0, 14))
```

Keep grouping readable, but avoid stacking every part inside a heavy `LabelFrame`.

- [ ] **Step 4: Add bilingual section labels with Chinese primary and English secondary text**

Use a compact stacked pattern in `src/booksmith/gui/views.py`, for example:

```python
section_title = ttk.Label(parent, text="工作区", style="SectionTitle.TLabel")
section_subtitle = ttk.Label(parent, text="Workspace", style="SectionSubtitle.TLabel")
```

Apply this to:

- header subtitle
- workspace section
- output/options section
- run status section
- results section
- logs section

- [ ] **Step 5: Run the GUI test file**

Run:

```bash
python -m pytest -q tests/test_gui_app.py
```

Expected:

```text
PASS for the new structure assertions, or only fail on not-yet-implemented expander behavior.
```

- [ ] **Step 6: Commit the layout rewrite**

```bash
git add src/booksmith/gui/views.py tests/test_gui_app.py
git commit -m "feat: redesign Booksmith GUI into a cleaner single-page workspace"
```

### Task 3: Add Publishing Advanced-Options Collapse And Refine Mode Behavior

**Files:**
- Modify: `H:\AI_Apps\booksmith\src\booksmith\gui\views.py`
- Modify: `H:\AI_Apps\booksmith\src\booksmith\gui\app.py`
- Test: `H:\AI_Apps\booksmith\tests\test_gui_app.py`

- [ ] **Step 1: Add a failing test for the publishing expander behavior**

Extend `tests/test_gui_app.py`:

```python
def test_gui_expands_publishing_advanced_options_on_toggle() -> None:
    app = _create_gui()
    try:
        app.mode_var.set("publishing")
        app.sync_mode_panels()
        app._toggle_publishing_advanced()
        assert app.views.publishing_expanded_var.get() is True
        assert app.views.publishing_advanced_frame.winfo_manager() == "grid"
    finally:
        app.root.destroy()
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
python -m pytest -q tests/test_gui_app.py::test_gui_expands_publishing_advanced_options_on_toggle
```

Expected:

```text
FAIL because the toggle handler and inline expand/collapse behavior do not yet exist.
```

- [ ] **Step 3: Implement the toggle handler and publishing visibility logic**

In `src/booksmith/gui/app.py`, add:

```python
def _toggle_publishing_advanced(self) -> None:
    expanded = not self.views.publishing_expanded_var.get()
    self.views.publishing_expanded_var.set(expanded)
    self._sync_publishing_advanced_visibility()

def _sync_publishing_advanced_visibility(self) -> None:
    if self.mode_var.get() != "publishing" or not self.views.publishing_expanded_var.get():
        self.views.publishing_advanced_frame.grid_remove()
    else:
        self.views.publishing_advanced_frame.grid()
```

Wire the toggle button command to `_toggle_publishing_advanced()` and call `_sync_publishing_advanced_visibility()` from `sync_mode_panels()`.

- [ ] **Step 4: Keep publishing options hidden in engineering mode**

Ensure `sync_mode_panels()` keeps:

- the whole publishing section hidden in engineering mode
- the advanced subsection hidden unless both publishing mode and expanded state are true

Representative logic:

```python
if self.mode_var.get() == "publishing":
    self.publishing_frame.grid()
else:
    self.publishing_frame.grid_remove()
    self.views.publishing_advanced_frame.grid_remove()
```

- [ ] **Step 5: Run the GUI behavior tests**

Run:

```bash
python -m pytest -q tests/test_gui_app.py
```

Expected:

```text
All GUI app tests pass with collapsed-by-default publishing advanced options.
```

- [ ] **Step 6: Commit the advanced-options behavior**

```bash
git add src/booksmith/gui/views.py src/booksmith/gui/app.py tests/test_gui_app.py
git commit -m "feat: add inline publishing advanced options toggle"
```

### Task 4: Refine Run, Results, And Log Presentation

**Files:**
- Modify: `H:\AI_Apps\booksmith\src\booksmith\gui\views.py`
- Modify: `H:\AI_Apps\booksmith\src\booksmith\gui\app.py`
- Test: `H:\AI_Apps\booksmith\tests\test_gui_app.py`

- [ ] **Step 1: Add failing assertions for cleaner result visibility**

Add or update tests in `tests/test_gui_app.py` so they verify:

- result buttons are hidden before completion
- only relevant buttons are shown after completion
- status summary stays concise

Representative test:

```python
def test_gui_hides_result_actions_before_run_completion(tmp_path: Path) -> None:
    app = _create_gui(task_runner=_FakeTaskRunner())
    try:
        assert app.views.result_buttons["open_translated_pdf"].winfo_manager() == ""
        assert app.views.result_buttons["open_translated_epub"].winfo_manager() == ""
    finally:
        app.root.destroy()
```

- [ ] **Step 2: Run the targeted test to verify current behavior**

Run:

```bash
python -m pytest -q tests/test_gui_app.py::test_gui_hides_result_actions_before_run_completion
```

Expected:

```text
FAIL if any result controls are still visible too early or if the new layout assumptions are not yet enforced.
```

- [ ] **Step 3: Rebalance the run area and results area**

In `src/booksmith/gui/views.py`:

- keep the run button as the single dominant action
- reduce secondary status clutter
- give results its own clearer action strip
- keep logs visible but smaller and quieter

Use tighter summary text presentation and move the log frame visually below the results area.

- [ ] **Step 4: Keep app-state wiring unchanged while aligning visuals**

In `src/booksmith/gui/app.py`, avoid semantic changes. Only adjust what is needed so the new layout still receives:

- run button enable/disable
- result action refresh
- status text
- summary text
- stage text

Do not move runtime orchestration into the view layer.

- [ ] **Step 5: Run the GUI tests and the CLI/GUI focused suite**

Run:

```bash
python -m pytest -q tests/test_gui_app.py tests/test_gui_services.py tests/test_gui_tasks.py tests/test_cli_smoke.py
```

Expected:

```text
All focused GUI and CLI smoke tests pass.
```

- [ ] **Step 6: Commit the status/results polish**

```bash
git add src/booksmith/gui/views.py src/booksmith/gui/app.py tests/test_gui_app.py
git commit -m "feat: polish Booksmith GUI run and results presentation"
```

### Task 5: Final Verification And Manual Smoke Validation

**Files:**
- Verify only: `H:\AI_Apps\booksmith\src\booksmith\gui\views.py`
- Verify only: `H:\AI_Apps\booksmith\src\booksmith\gui\app.py`
- Verify only: `H:\AI_Apps\booksmith\tests\test_gui_app.py`

- [ ] **Step 1: Run repository verification**

Run:

```bash
python -m ruff check .
python -m pytest -q
```

Expected:

```text
Ruff passes and the full test suite passes.
```

- [ ] **Step 2: Run module and script GUI smoke checks**

Run:

```bash
python -m booksmith.gui
booksmith-gui
```

Expected:

```text
The GUI launches successfully from both entry points.
```

- [ ] **Step 3: Manually verify key UI behaviors**

Check:

- engineering mode starts in the simpler layout
- publishing mode reveals publishing options
- advanced publishing options stay collapsed by default
- expanding advanced options works inline
- result actions appear only when a run produces artifacts
- logs remain visible but visually secondary

- [ ] **Step 4: Commit any final GUI-only fixups if needed**

If the smoke test reveals a GUI-only issue, commit the minimal fix:

```bash
git add src/booksmith/gui/views.py src/booksmith/gui/app.py tests/test_gui_app.py
git commit -m "fix: resolve final Booksmith GUI polish issues"
```

Otherwise skip this step.

## Self-Review

### Spec coverage

- Single-page GUI refinement: covered in Tasks 1-4.
- Bilingual Chinese-primary copy: covered in Task 2.
- Publishing advanced options collapsed by default: covered in Task 3.
- Results and logs reprioritized: covered in Task 4.
- Performance-first and no behavior changes: enforced by the implementation constraints and final verification.

### Placeholder scan

- No `TODO`, `TBD`, or deferred implementation placeholders remain in the plan.
- Every code-changing step contains exact files, tests, or representative code.

### Type consistency

- The new GUI fields use consistent names:
  - `publishing_advanced_frame`
  - `publishing_expanded_var`
  - `publishing_toggle_button`
- The app methods consistently reference `_toggle_publishing_advanced()` and `_sync_publishing_advanced_visibility()`.
