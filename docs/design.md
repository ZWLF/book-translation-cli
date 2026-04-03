# Design Notes

This repository implements two translation workflows on one shared foundation:

- `engineering`: accurate, resumable, chunk-based translation for bulk processing
- `publishing`: quality-first non-fiction translation with explicit editorial stages

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

## Publishing Workflow Guarantees

- Reuses the same extraction, chaptering, chunking, provider, and PDF infrastructure
- Keeps publishing artifacts under `out/<book>/publishing/` so engineering outputs stay isolated
- Runs six explicit stages:
  - `draft`
  - `lexicon`
  - `revision`
  - `proofread`
  - `final-review`
  - `deep-review`
- Produces auditable editorial artifacts:
  - `draft/chapters.jsonl`
  - `lexicon/glossary.json`
  - `lexicon/names.json`
  - `lexicon/decisions.json`
  - `revision/revised_chapters.jsonl`
  - `proofread/proofread_notes.jsonl`
  - `proofread/proofread_changes.jsonl`
  - `final/final_chapters.jsonl`
  - `final/translated.txt`
  - `final/translated.pdf`
  - `deep_review/findings.jsonl` when `--to-stage deep-review` runs
  - `deep_review/revised_chapters.jsonl` when `--to-stage deep-review` runs
  - `deep_review/decisions.json` when `--to-stage deep-review` runs
  - `editorial_log.json`
  - `run_summary.json`
- Supports stage-aware resume via `--from-stage` / `--to-stage`
- Lets `qa-pdf` target the publishing final PDF when the engineering PDF is absent

## Publishing Quality Profile

- Non-fiction first
- Fidelity first, elegance second
- Formal, restrained Chinese prose
- Whole-book term and proper-name consistency
- Automated proofreading, whole-book final review, and source-aware deep review before final acceptance
- No fiction-first rewriting and no human review UI in this phase

## Version 1 Non-Goals

- OCR for scanned PDFs
- Publication-grade literary rewriting
- GUI
- Database-backed job management
