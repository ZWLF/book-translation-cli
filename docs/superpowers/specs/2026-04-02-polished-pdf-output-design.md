# Polished PDF Output Design

## Goal

Add a post-translation output stage that turns a completed book workspace into a polished, readable Chinese PDF without re-running translation.

## Scope

- Keep the existing translation pipeline unchanged for extraction, chunking, provider calls, retries, resume, and `.txt` output.
- Add a new rendering path that reads an existing workspace and writes `translated.pdf`.
- Support direct rendering from a finished workspace and optional rendering at the end of a translation run.
- Produce a book-like layout with:
  - cover page
  - translator note / production note page
  - table of contents
  - chapter title pages
  - running headers and page numbers
  - Chinese body typography using local Windows fonts

## Non-Goals

- Pixel-perfect recreation of the source PDF's original design.
- OCR or scanned-PDF support.
- Re-translation or literary rewrite of the book body.
- Visual asset extraction from the source PDF.

## Approach

Use a local Python PDF renderer built on `reportlab`.

Reasons:

- Works offline and does not require an extra cloud service.
- Can use installed Windows Chinese fonts directly.
- Supports page templates, headers, page numbers, and table-of-contents generation.
- Keeps the output stage fully inside the existing CLI project.

## Architecture

### 1. Workspace-to-book normalization

Read the workspace's `manifest.json`, `chunks.jsonl`, `translations.jsonl`, and `run_summary.json`, then reconstruct ordered chapter content.

The normalization layer will:

- group translated chunks by chapter order
- skip failed or empty chapters
- clean Markdown heading prefixes like `#` / `##` / `###`
- drop standalone page-number noise such as lines that are only digits
- merge wrapped lines inside a paragraph while preserving blank-line paragraph breaks
- classify content into printable blocks:
  - chapter heading
  - section heading
  - paragraph

### 2. PDF rendering

Render a `PrintableBook` model into `translated.pdf`.

Layout decisions:

- page size: A5 for a more book-like reading footprint
- generous margins
- Chinese serif-style body text with a readable line height
- chapter opening pages start on a new page
- running header shows source title on the left and chapter title on the right
- page numbers centered in footer

### 3. CLI surface

Add two ways to use the feature:

- translation flow:
  - `--render-pdf/--no-render-pdf`
- standalone render flow:
  - `book-translator render-pdf --workspace <workspace-dir>`

The standalone command is required so already-translated books can be rendered without paying for translation again.

## Output Files

Per book workspace:

- existing: `translated.txt`
- new: `translated.pdf`

## Error Handling

- If required workspace files are missing, fail with a clear CLI error.
- If no usable Chinese font can be registered, fail fast and explain which font paths were tried.
- If a chapter has no successful translated chunks, skip it instead of generating blank pages.

## Verification

- unit test paragraph normalization and heading detection
- unit test PDF generation by asserting `%PDF` header and non-zero output file size
- integration test rendering from a completed fake workspace
- manual validation by generating the polished PDF for the existing Elon book workspace
