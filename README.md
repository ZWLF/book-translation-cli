# Booksmith

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

Booksmith is a command-line tool for translating text-based PDF and EPUB books into Simplified Chinese. It supports two workflows on one shared foundation:

- `engineering`: accurate, resumable, cost-aware translation for bulk processing
- `publishing`: quality-first non-fiction translation with staged revision, proofreading, final review, structured source audit, arbitration, and deep review

## GUI

The desktop GUI is a separate local entry point built on the same translation pipelines. It is a companion to the CLI, not a replacement for it.

Use the GUI when you want an interactive local app with engineering and publishing modes, progress updates, logs, and results views. Use the CLI when you want automation, scripting, or batch runs.

Launch the GUI with either command:

```bash
booksmith-gui
python -m booksmith.gui
```

## Features

- Extract text from text-based PDF and EPUB files
- Preserve chapter structure using bookmarks or TOC first, then heading rules
- Chunk chapters for concurrent translation
- Translate with OpenAI or Gemini APIs
- Retry recoverable API failures with exponential backoff
- Resume unfinished runs and rerun selected stages
- Render polished Chinese reading PDFs
- Generate reflowable EPUB output from the structured publishing pipeline
- Produce source-audit artifacts, review consensus, repair logs, and QA screenshots

## Installation

### Standard Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

### Conda fallback

If the local Python interpreter is incompatible with dependencies:

```bash
conda create -n booksmith-py311 python=3.11
conda activate booksmith-py311
pip install -e .[dev]
```

## Configuration

Copy `.env.example` and set the relevant API key:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

## Usage

### Engineering mode

```bash
booksmith engineering --input ./books --output ./out --provider gemini --resume
```

### Publishing mode

```bash
booksmith publishing --input ./books --output ./out --provider openai --model gpt-4o-mini
```

Default output follows the source format:

- `PDF` input writes `publishing/final/translated.pdf`
- `EPUB` input writes `publishing/final/translated.epub`

Cross-format output is explicit:

```bash
booksmith publishing --input ./books/book.pdf --output ./out --also-epub
booksmith publishing --input ./books/book.epub --output ./out --also-pdf
```

Resume only later editorial stages:

```bash
booksmith publishing --input ./books --output ./out --from-stage revision --to-stage final-review
```

Run the source-aware deep-review pass and rebuild the final deliverables:

```bash
booksmith publishing --input ./books --output ./out --from-stage final-review --to-stage deep-review --render-pdf
```

Stop after lexicon creation for inspection:

```bash
booksmith publishing --input ./books --output ./out --to-stage lexicon
```

Re-render a polished PDF from an existing workspace without calling the translation API again:

```bash
booksmith render-pdf --workspace ./out/book-name
```

Export specific PDF pages as PNG files:

```bash
booksmith render-pages --pdf ./out/book-name/translated.pdf --output-dir ./tmp/pages --pages 1,3-5
```

Generate a workspace-local visual QA snapshot set:

```bash
booksmith qa-pdf --workspace ./out/book-name
```

If the engineering PDF is absent but `publishing/final/translated.pdf` exists, `qa-pdf` uses the publishing PDF and writes screenshots under `publishing/qa/`.

## Output Per Book

Each processed book writes a dedicated workspace directory under the output root.

### Engineering outputs

- `manifest.json`
- `chunks.jsonl`
- `translations.jsonl`
- `error_log.json`
- `run_summary.json`
- `translated.txt`
- `translated.pdf`
- `qa/pages/page-###.png`
- `qa/qa_summary.json`

### Publishing outputs

- `publishing/manifest.json`
- `publishing/state/<stage>.json`
- `publishing/draft/chapters.jsonl`
- `publishing/draft/draft.txt`
- `publishing/lexicon/glossary.json`
- `publishing/lexicon/names.json`
- `publishing/lexicon/decisions.json`
- `publishing/revision/revised_chapters.jsonl`
- `publishing/proofread/proofread_notes.jsonl`
- `publishing/proofread/proofread_changes.jsonl`
- `publishing/final/final_chapters.jsonl`
- `publishing/final/translated.txt`
- `publishing/final/translated.pdf`
- `publishing/final/translated.epub`
- `publishing/editorial_log.json`
- `publishing/run_summary.json`
- `publishing/qa/pages/page-###.png`
- `publishing/qa/qa_summary.json`

Additional artifacts when `--to-stage deep-review` runs:

- `publishing/deep_review/findings.jsonl`
- `publishing/deep_review/revised_chapters.jsonl`
- `publishing/deep_review/decisions.json`
- `publishing/audit/source_audit.jsonl`
- `publishing/audit/review_audit.jsonl`
- `publishing/audit/consensus.json`
- `publishing/audit/final_audit_report.json`
- `publishing/assets/manifest.json`
- `publishing/assets/images/*`

## CLI Options

### Shared translation options

- `--input`: single file or directory, scanned recursively
- `--output`: output root directory
- `--provider`: `openai` or `gemini`
- `--model`: override the default provider model
- `--api-key-env`: override the API key environment variable name
- `--max-concurrency`: maximum in-flight translation requests
- `--resume/--no-resume`: reuse successful chunk results when possible
- `--force`: delete previous run state for the target book and rerun from scratch
- `--glossary`: JSON object file for term mappings
- `--name-map`: JSON object file for proper-name mappings
- `--chapter-strategy`: `toc-first`, `auto`, `rule-only`, or `manual`
- `--manual-toc`: JSON list of manual chapter titles when `--chapter-strategy manual`
- `--chunk-size`: approximate max source words per chunk
- `--render-pdf/--no-render-pdf`: enable or disable polished PDF rendering after translation

### Publishing-only options

- `--style`: publishing style profile, currently `non-fiction-publishing`
- `--from-stage`: `draft`, `lexicon`, `revision`, `proofread`, `final-review`, or `deep-review`
- `--to-stage`: stop after a specific publishing stage
- `--also-pdf`: add a PDF output when the source format defaults to EPUB
- `--also-epub`: add an EPUB output when the source format defaults to PDF
- `--audit-depth`: `standard` or `consensus`
- `--enable-cross-review/--no-cross-review`: enable or disable the audit/review arbitration loop
- `--image-policy`: currently `extract-or-preserve-caption`

Publishing stage semantics:

- `draft`: first-pass full-book translation
- `lexicon`: whole-book glossary, proper-name, and decision artifacts
- `revision`: chapter-level revision against the lexicon
- `proofread`: independent proofreading pass with notes
- `final-review`: whole-book consistency pass plus final text/PDF/EPUB output
- `deep-review`: source-aware acceptance pass that emits findings, audit artifacts, and then rebuilds the final text/PDF/EPUB according to the selected outputs

## Validation

```bash
ruff check .
pytest -q
```

## Notes

- Version 1 supports text-based PDFs only, not scanned PDFs.
- Engineering mode outputs Chinese-only plain text plus an optional polished PDF.
- Publishing mode targets non-fiction, publication-style Chinese and preserves intermediate editorial artifacts.
- Resume is on by default; use `--force` to rerun a book from scratch.
- Publishing resume is stage-aware; `--from-stage` and `--to-stage` let you rerun only part of the editorial pipeline.
- The polished PDF renderer uses local Windows Chinese fonts and produces a book-like layout, not a page-faithful clone of the source PDF.
