# Polished PDF Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a polished Chinese PDF output stage that renders a completed translation workspace into `translated.pdf`.

**Architecture:** Keep translation intact and add a separate normalization plus rendering pipeline. Render directly from workspace artifacts so existing translated books can be upgraded without new API calls.

**Tech Stack:** Python, reportlab, typer, pytest, rich

---

### Task 1: Add failing tests for printable-book normalization

**Files:**
- Create: `H:\AI_Apps\book-translation-cli\tests\test_polished_pdf.py`

- [ ] **Step 1: Write the failing tests**

Add tests that build tiny in-memory chapter/chunk/translation fixtures and assert:

- wrapped lines are merged into a single paragraph
- Markdown heading markers are stripped
- numeric page-number-only lines are removed
- empty chapters are skipped

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest H:\AI_Apps\book-translation-cli\tests\test_polished_pdf.py -q`

- [ ] **Step 3: Implement the minimal normalization code**

Create a focused normalization module under `src/book_translator/output/` that converts workspace content into printable blocks.

- [ ] **Step 4: Re-run the targeted tests**

Run: `python -m pytest H:\AI_Apps\book-translation-cli\tests\test_polished_pdf.py -q`

### Task 2: Add failing tests for PDF generation

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\tests\test_polished_pdf.py`
- Modify: `H:\AI_Apps\book-translation-cli\pyproject.toml`

- [ ] **Step 1: Write the failing PDF render test**

Add a test that renders a tiny printable book to a temp file and asserts:

- file exists
- file starts with `%PDF`
- file size is greater than zero

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python -m pytest H:\AI_Apps\book-translation-cli\tests\test_polished_pdf.py -q`

- [ ] **Step 3: Add `reportlab` and implement the renderer**

Create the renderer in `src/book_translator/output/` with local font registration, cover page, contents, chapter pages, headers, and footers.

- [ ] **Step 4: Re-run the targeted tests**

Run: `python -m pytest H:\AI_Apps\book-translation-cli\tests\test_polished_pdf.py -q`

### Task 3: Wire the renderer into the CLI

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\cli.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\pipeline.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py`

- [ ] **Step 1: Write the failing CLI/integration tests**

Extend integration coverage so a processed fake book can render a PDF from its workspace, and add a CLI smoke check for the new subcommand.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest H:\AI_Apps\book-translation-cli\tests\test_pipeline_integration.py H:\AI_Apps\book-translation-cli\tests\test_cli_smoke.py -q`

- [ ] **Step 3: Implement CLI integration**

Add:

- `--render-pdf/--no-render-pdf` to the main translate flow
- `render-pdf` subcommand for completed workspaces

- [ ] **Step 4: Re-run the targeted tests**

Run: `python -m pytest H:\AI_Apps\book-translation-cli\tests\test_pipeline_integration.py H:\AI_Apps\book-translation-cli\tests\test_cli_smoke.py -q`

### Task 4: Documentation and real-book verification

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\README.md`

- [ ] **Step 1: Update README**

Document:

- polished PDF feature
- CLI examples
- font assumptions
- output file list

- [ ] **Step 2: Run full verification**

Run:

- `python -m pytest -q`
- `ruff check .`

- [ ] **Step 3: Render the Elon book PDF**

Run the new renderer against:

- `H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson`

- [ ] **Step 4: Check the artifact exists**

Verify `H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson\translated.pdf`
