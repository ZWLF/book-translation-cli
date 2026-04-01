# Design Notes

This repository implements the engineering-grade phase of the book translation workflow.

## Version 1 Guarantees

- Text-based `PDF` and `EPUB` inputs
- Chapter-first segmentation
- Paragraph-aware chunking
- OpenAI and Gemini providers behind one interface
- Async chunk translation with bounded concurrency
- Exponential backoff on retryable failures
- Resume by default, `--force` for clean reruns
- Per-book workspace outputs:
  - `manifest.json`
  - `chunks.jsonl`
  - `translations.jsonl`
  - `error_log.json`
  - `run_summary.json`
  - `translated.txt`

## Version 1 Non-Goals

- OCR for scanned PDFs
- Publication-grade literary rewriting
- GUI
- Database-backed job management
