# book-translation-cli

Command-line tool for translating text-based PDF and EPUB books into Simplified Chinese.

## Modes

- `engineering`: accurate, resumable, cost-aware translation for bulk processing
- `publishing`: quality-first non-fiction translation with staged revision, proofreading, and final review

The top-level command remains an alias to `engineering` for compatibility.

## Features

- Extract text from text-based PDF and EPUB files
- Preserve chapter structure using bookmarks/TOC first, then heading rules
- Chunk chapters for concurrent translation
- Translate with OpenAI or Gemini APIs
- Async concurrency with exponential backoff retries
- Resume unfinished runs
- Write `translated.txt`, `error_log.json`, and `run_summary.json`
- Render a polished Chinese reading PDF as `translated.pdf`
- Add a staged publishing workflow with draft, lexicon, revision, proofread, and final-review outputs
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

### Engineering mode

```bash
book-translator engineering --input ./books --output ./out --provider gemini --resume
```

Compatibility alias:

```bash
book-translator --input ./books --output ./out --provider gemini --resume
```

### Publishing mode

```bash
book-translator publishing --input ./books --output ./out --provider openai --model gpt-4o-mini
```

To resume only the later editorial stages:

```bash
book-translator publishing --input ./books --output ./out --from-stage revision --to-stage final-review
```

To stop after lexicon creation for inspection:

```bash
book-translator publishing --input ./books --output ./out --to-stage lexicon
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

If the engineering PDF is absent but `publishing/final/translated.pdf` exists, `qa-pdf` will use the publishing PDF and write screenshots under `publishing/qa/`.

## Output Per Book

Each processed book writes a dedicated workspace directory under the output root:

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
- `publishing/editorial_log.json`
- `publishing/run_summary.json`
- `publishing/qa/pages/page-###.png`
- `publishing/qa/qa_summary.json`

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
- `--from-stage`: `draft`, `lexicon`, `revision`, `proofread`, or `final-review`
- `--to-stage`: stop after a specific publishing stage

Publishing stage semantics:

- `draft`: first-pass full-book translation
- `lexicon`: whole-book glossary, proper-name, and decision artifacts
- `revision`: chapter-level revision against the lexicon
- `proofread`: independent proofreading pass with notes
- `final-review`: whole-book consistency pass plus final text/PDF output

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
