# Booksmith Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the project completely from `book-translation-cli` / `book_translator` / `book-translator` to `Booksmith` / `booksmith` / `booksmith` with no compatibility aliases.

**Architecture:** Perform the rename in two layers. First, complete the code, packaging, CLI, GUI, docs, and tests rename inside the existing repository checkout so the project remains runnable and verifiable. Second, after the code-level rename is merged, rename the GitHub repository and local filesystem directory, then re-verify from the renamed path.

**Tech Stack:** Python 3.11+, setuptools, Typer CLI, Tkinter GUI, pytest, Ruff, Git, GitHub CLI

---

### Task 1: Rename The Python Package Namespace

**Files:**
- Rename: `src/book_translator` -> `src/booksmith`
- Modify: `src/booksmith/__init__.py`
- Modify: `src/booksmith/__main__.py`
- Modify: `src/booksmith/cli.py`
- Modify: `src/booksmith/app_services.py`
- Modify: `src/booksmith/config.py`
- Modify: `src/booksmith/models.py`
- Modify: `src/booksmith/pipeline.py`
- Modify: all modules under `src/booksmith/chaptering/`
- Modify: all modules under `src/booksmith/chunking/`
- Modify: all modules under `src/booksmith/extractors/`
- Modify: all modules under `src/booksmith/gui/`
- Modify: all modules under `src/booksmith/output/`
- Modify: all modules under `src/booksmith/providers/`
- Modify: all modules under `src/booksmith/publishing/`
- Modify: all modules under `src/booksmith/state/`
- Modify: all modules under `src/booksmith/translation/`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_gui_app.py`
- Test: `tests/test_gui_services.py`
- Test: `tests/test_gui_tasks.py`
- Test: all import-sensitive test files under `tests/`

- [ ] **Step 1: Rename the package directory**

Move:

```text
src/book_translator -> src/booksmith
```

Expected result:

```text
src/booksmith/__init__.py
src/booksmith/__main__.py
src/booksmith/gui/app.py
...
```

- [ ] **Step 2: Rewrite intra-package imports from `book_translator` to `booksmith`**

Representative examples:

```python
# before
from book_translator.cli import main

# after
from booksmith.cli import main
```

```python
# before
from book_translator.state.workspace import Workspace

# after
from booksmith.state.workspace import Workspace
```

Apply the same rename across the moved package tree and all tests.

- [ ] **Step 3: Update public package identity files**

Set the package exports to the new product/module name where appropriate:

```python
# src/booksmith/__main__.py
from booksmith.cli import main

if __name__ == "__main__":
    main()
```

Update `src/booksmith/gui/__init__.py` similarly so it exposes `BooksmithGui` rather than the old class name if the GUI class is renamed in Task 2.

- [ ] **Step 4: Run focused import tests**

Run:

```bash
python -m pytest -q tests/test_cli_smoke.py tests/test_gui_app.py tests/test_gui_services.py tests/test_gui_tasks.py
```

Expected:

```text
All selected tests pass with imports resolving from booksmith.*
```

- [ ] **Step 5: Commit the package-namespace rename**

```bash
git add src/booksmith tests
git commit -m "refactor: rename package namespace to booksmith"
```

### Task 2: Rename Packaging, CLI, And GUI Entry Points

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/booksmith/cli.py`
- Modify: `src/booksmith/gui/app.py`
- Modify: `src/booksmith/gui/__init__.py`
- Modify: `src/booksmith/gui/__main__.py`
- Modify: `tests/test_cli_smoke.py`
- Modify: `tests/test_gui_app.py`
- Modify: `tests/test_gui_services.py`
- Modify: `tests/test_gui_tasks.py`

- [ ] **Step 1: Update package metadata in `pyproject.toml`**

Change the project metadata from the old package and command names to the new ones:

```toml
[project]
name = "booksmith"
description = "Booksmith: engineering and publishing workflows for translating books."

[project.scripts]
booksmith = "booksmith.cli:main"
booksmith-gui = "booksmith.gui.app:main"
```

Remove the old `book-translator` and `book-translator-gui` entries entirely.

- [ ] **Step 2: Update CLI help text and top-level command language**

Any CLI-facing help strings that still mention `book-translator` or `Book Translator` should be updated to `booksmith` / `Booksmith`.

Representative update:

```python
# before
prog_name = "book-translator"

# after
prog_name = "booksmith"
```

Apply the same rule to command examples and error/help output.

- [ ] **Step 3: Update GUI product identity**

Rename visible GUI product strings and, if appropriate, the main GUI class:

```python
# before
class BookTranslatorGui:
    ...
    self.root.title("Book Translator")

# after
class BooksmithGui:
    ...
    self.root.title("Booksmith")
```

Also update imports and exports if the class name changes:

```python
from .app import BooksmithGui, main

__all__ = ["BooksmithGui", "main"]
```

- [ ] **Step 4: Reinstall the project in editable mode to refresh generated entry points**

Run:

```bash
pip install -e .[dev]
```

Expected:

```text
Editable install succeeds and new scripts booksmith / booksmith-gui are generated.
```

- [ ] **Step 5: Verify the new command and module entry points**

Run:

```bash
python -m booksmith --help
booksmith --help
python -m booksmith.gui
booksmith-gui
```

Expected:

```text
CLI help opens under the new command name and GUI launches under the new module/script names.
```

- [ ] **Step 6: Commit the entry-point rename**

```bash
git add pyproject.toml src/booksmith tests
git commit -m "feat: rename CLI and GUI entry points to Booksmith"
```

### Task 3: Rename Documentation And Remove Public Old-Name References

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `README.ja.md`
- Modify: `docs/design.md`
- Modify: `docs/superpowers/specs/2026-04-05-booksmith-rename-design.md` only if cross-links need the new repo name after rename
- Modify: any other docs in `docs/` that identify the product as `Book Translation CLI` or `Book Translator`
- Test: repo-wide reference scan

- [ ] **Step 1: Rewrite the primary README to use `Booksmith`**

Update:

```markdown
# Booksmith
```

Update command examples:

```bash
booksmith engineering --input ./books --output ./out --provider gemini --resume
booksmith publishing --input ./books --output ./out --provider openai --model gpt-4o-mini
booksmith-gui
python -m booksmith.gui
```

Remove mention of old top-level compatibility aliases.

- [ ] **Step 2: Rewrite the Chinese and Japanese READMEs**

Apply the same rename rules to:

```text
README.zh-CN.md
README.ja.md
```

Ensure all examples, labels, and product mentions use `Booksmith`.

- [ ] **Step 3: Update project documentation and product labels**

Replace public old-name references in docs:

```text
book-translation-cli
Book Translation CLI
Book Translator
book-translator
book-translator-gui
book_translator
```

Allowed exceptions:

- historical notes explicitly describing the rename
- generated metadata that will be regenerated after reinstall

- [ ] **Step 4: Run a reference scan for old names**

Run:

```bash
python - <<'PY'
from pathlib import Path

root = Path(r"H:\AI_Apps\book-translation-cli")
needles = [
    "book-translation-cli",
    "Book Translation CLI",
    "Book Translator",
    "book-translator",
    "book-translator-gui",
    "book_translator",
]
for path in root.rglob("*"):
    if not path.is_file():
        continue
    if ".git" in path.parts or "__pycache__" in path.parts:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue
    for needle in needles:
        if needle in text:
            print(f"{path}: {needle}")
PY
```

Expected:

```text
No active public/code references remain, or remaining hits are intentionally historical/generated and reviewed.
```

- [ ] **Step 5: Run full repo verification**

Run:

```bash
python -m ruff check .
python -m pytest -q
```

Expected:

```text
All checks pass after documentation and public-surface rename.
```

- [ ] **Step 6: Commit the documentation rename**

```bash
git add README.md README.zh-CN.md README.ja.md docs src tests
git commit -m "docs: rename product surfaces to Booksmith"
```

### Task 4: Push, Merge, And Perform Post-Merge Repo/Path Rename

**Files:**
- Modify: GitHub repository settings (rename repo)
- Modify: local filesystem directory `H:\AI_Apps\book-translation-cli` -> `H:\AI_Apps\booksmith`
- Modify: local git remote URL if required
- Test: post-rename command verification from the renamed local path

- [ ] **Step 1: Push the rename branch and open a PR**

Run:

```bash
git push -u origin codex/booksmith-rename-design
gh pr create --title "Rename project to Booksmith" --body "## Summary
- rename package namespace, CLI, and GUI entry points to Booksmith
- update README and docs to the new product identity
- remove public old-name aliases

## Test Plan
- [ ] python -m ruff check .
- [ ] python -m pytest -q
- [ ] python -m booksmith --help
- [ ] booksmith --help
- [ ] python -m booksmith.gui
- [ ] booksmith-gui"
```

Expected:

```text
PR opens successfully and CI is green before merge.
```

- [ ] **Step 2: Merge the PR to `main`**

Run:

```bash
gh pr merge --squash --delete-branch
```

Expected:

```text
Rename lands on main and branch is removed remotely.
```

- [ ] **Step 3: Rename the GitHub repository**

Use GitHub settings or `gh repo rename` so:

```text
ZWLF/book-translation-cli -> ZWLF/booksmith
```

Then verify:

```bash
gh repo view ZWLF/booksmith
```

- [ ] **Step 4: Rename the local project directory**

Move:

```text
H:\AI_Apps\book-translation-cli -> H:\AI_Apps\booksmith
```

Then ensure the shell is operating from the renamed path for the final verification steps.

- [ ] **Step 5: Update and verify the local remote URL**

Run from the renamed directory:

```bash
git remote -v
```

Expected:

```text
origin points at https://github.com/ZWLF/booksmith.git
```

If needed:

```bash
git remote set-url origin https://github.com/ZWLF/booksmith.git
```

- [ ] **Step 6: Run final smoke verification from `H:\AI_Apps\booksmith`**

Run:

```bash
python -m ruff check .
python -m pytest -q
python -m booksmith --help
booksmith --help
python -m booksmith.gui
booksmith-gui
```

Expected:

```text
All checks pass from the renamed local directory and the project is fully operating as Booksmith.
```

- [ ] **Step 7: Commit any final doc/link fixes caused by repo rename**

If the GitHub repo rename required doc-link adjustments after merge, commit only those fixes:

```bash
git add README.md README.zh-CN.md README.ja.md docs
git commit -m "docs: update links after Booksmith repo rename"
```

Otherwise skip this step.

## Self-Review

### Spec coverage

- Full product rename across package, commands, GUI, docs, repo, and local path: covered by Tasks 1-4.
- No compatibility aliases: enforced in Tasks 2 and 3.
- CLI and GUI remain parallel entry points: verified in Tasks 2 and 4.
- Deferred repo/path rename order: captured explicitly in Task 4.

### Placeholder scan

- No `TODO`, `TBD`, or deferred code placeholders remain in this plan.
- Every task includes exact files, commands, and expected outputs.

### Type and naming consistency

- New package namespace is consistently `booksmith`.
- New CLI command is consistently `booksmith`.
- New GUI command is consistently `booksmith-gui`.
- New module entry is consistently `python -m booksmith` / `python -m booksmith.gui`.
