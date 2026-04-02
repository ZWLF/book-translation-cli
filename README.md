# book-translation-cli

Command-line tool for engineering-grade translation of text-based PDF and EPUB books into Simplified Chinese.

## Features

- Extract text from text-based PDF and EPUB files
- Preserve chapter structure using bookmarks/TOC first, then heading rules
- Chunk chapters for concurrent translation
- Translate with OpenAI or Gemini APIs
- Async concurrency with exponential backoff retries
- Resume unfinished runs
- Write `translated.txt`, `error_log.json`, and `run_summary.json`
- Render a polished Chinese reading PDF as `translated.pdf`
- Rasterize rendered PDF pages into PNG screenshots for visual QA

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
conda create -n book-translation-cli-py311 python=3.11
conda activate book-translation-cli-py311
pip install -e .[dev]
```

## Configuration

Copy `.env.example` and set the relevant API key:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

## Usage

```bash
book-translator --input ./books --output ./out --provider gemini --resume
```

To re-render a polished PDF from an existing workspace without calling the translation API again:

```bash
book-translator render-pdf --workspace ./out/book-name
```

To export specific PDF pages as PNG files:

```bash
book-translator render-pages --pdf ./out/book-name/translated.pdf --output-dir ./tmp/pages --pages 1,3-5
```

To generate a workspace-local visual QA snapshot set:

```bash
book-translator qa-pdf --workspace ./out/book-name
```

## Output Per Book

Each processed book writes a dedicated workspace directory under the output root:

- `manifest.json`
- `chunks.jsonl`
- `translations.jsonl`
- `error_log.json`
- `run_summary.json`
- `translated.txt`
- `translated.pdf`
- `qa/pages/page-###.png`
- `qa/qa_summary.json`

## CLI Options

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

## Validation

```bash
ruff check .
pytest -q
```

## Notes

- Version 1 supports text-based PDFs only, not scanned PDFs.
- Output is Chinese-only plain text plus an optional polished PDF.
- Resume is on by default; use `--force` to rerun a book from scratch.
- The polished PDF renderer uses local Windows Chinese fonts and produces a book-like layout, not a page-faithful clone of the source PDF.
