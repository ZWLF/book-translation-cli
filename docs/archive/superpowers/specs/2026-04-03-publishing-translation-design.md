# Publishing Translation Pipeline Design

Date: 2026-04-03

## Summary

Add a second, explicitly higher-quality translation mode to the existing `book-translation-cli` project. The current `engineering` mode remains optimized for faithful, scalable, engineering-grade translation. The new `publishing` mode targets non-fiction books and produces a publication-grade Chinese draft through a staged editorial pipeline: full-book draft translation, whole-book lexicon normalization, chapter revision, chapter proofread, and final whole-book consistency review.

The project remains a single repository and a single CLI product. The user experience should present two clear choices:

- `engineering`: accurate, fast, lower-cost translation for bulk processing
- `publishing`: slower, more expensive, multi-stage translation and proofreading for publication-quality non-fiction output

This is not a page-faithful publishing tool and not a substitute for a human editorial department. It is a traceable, resumable, quality-first editorial pipeline built on top of the current extraction, chaptering, state, output, and PDF infrastructure.

## Goals

- Keep the current engineering workflow intact and easy to use.
- Add a separate publishing workflow with clear command boundaries.
- Target non-fiction books first: biography, business, ideas, memoir, reportage, essays.
- Prioritize faithful, restrained, formally published Chinese prose.
- Add whole-book terminology and proper-name consistency.
- Add automated proofreading and whole-book final review.
- Preserve process artifacts so decisions and changes can be audited.
- Reuse the current repo, state model, PDF generation, and QA tools where practical.

## Non-Goals

- No OCR or scanned-PDF support in this phase.
- No fiction-first or literary-novel-specific style system.
- No interactive human review UI in this phase.
- No sentence-aligned bilingual editor in this phase.
- No page-faithful recreation of the source English PDF.
- No attempt to replace final human legal/editorial approval for commercial publication.

## Product Shape

The CLI should evolve from a single default workflow into two explicit modes:

```bash
book-translator engineering ...
book-translator publishing ...
```

Compatibility rule:

- Phase 1 keeps the existing top-level translation behavior as an alias to `engineering`.
- New help output and new documentation should foreground `engineering` and `publishing` as the two canonical modes.
- The publishing pipeline must never be hidden behind the engineering command via a mode flag.

## Target Quality Profile

The `publishing` pipeline targets:

- non-fiction publishing style
- fidelity first, elegance second
- natural but restrained Chinese
- no network slang, no AI-explainer tone, no over-smoothing
- consistent treatment of names, terms, institutional references, and title conventions
- translated quotations, notes, references, appendices, and back matter preserved wherever feasible

The desired result is a publication-grade Chinese manuscript candidate, not merely a polished chunk translation.

## Architecture Overview

The current stack already contains reusable foundation pieces:

- `extractors`: PDF/EPUB text extraction
- `chaptering`: chapter detection and structure recovery
- `chunking`: chapter chunk splitting
- `providers`: OpenAI/Gemini transport and retries
- `state`: workspace persistence
- `output`: text assembly, polished PDF generation, page-raster QA

The new publishing mode should reuse those components where they still fit, then add a publishing-specific orchestration layer:

- `publishing/draft.py`
- `publishing/lexicon.py`
- `publishing/revision.py`
- `publishing/proofread.py`
- `publishing/final_review.py`
- `publishing/style.py`
- `publishing/artifacts.py`
- `publishing/pipeline.py`

The engineering and publishing pipelines should share low-level primitives, but their orchestration logic must stay separate. Publishing behavior should not be piled onto the engineering orchestrator through mode conditionals spread across unrelated modules.

## Publishing Pipeline Stages

### Stage 1: Book Draft

Purpose:

- translate the whole book into a faithful first Chinese draft
- preserve chapter structure and all substantive content
- optimize for completeness and accuracy, not final prose quality

Rules:

- keep the current extraction and chapter order behavior
- translate full text including quotations, notes, references, and appendices when possible
- capture per-chapter and per-chunk outputs in structured files, not only assembled text
- preserve enough metadata to revisit a chunk later in revision/proofreading stages

Output:

- `draft/chapters.jsonl`
- `draft/draft.txt`

### Stage 2: Book Lexicon

Purpose:

- build whole-book consistency constraints before stylistic revision

Artifacts to extract:

- proper names
- organizations
- product names
- place names
- recurring technical or thematic terms
- title conventions
- translation decisions that must stay stable throughout the manuscript

Rules:

- this stage is global, not chapter-local
- it must combine source evidence and draft evidence
- it must prefer determinism and consistency over creativity
- it must allow optional user-supplied glossary/name-map overlays

Output:

- `lexicon/glossary.json`
- `lexicon/names.json`
- `lexicon/decisions.json`

### Stage 3: Chapter Revision

Purpose:

- transform each chapter draft into publication-style non-fiction Chinese

Responsibilities:

- enforce lexicon decisions
- improve sentence rhythm and clause ordering
- reduce translation stiffness
- preserve authorial tone without introducing translator voice drift
- improve headings and structural text where needed
- keep quotations, references, and notes readable and consistent

Rules:

- revision is chapter-scoped but must receive whole-book style and lexicon context
- it must not silently drop information
- it must not convert the text into a localized rewrite detached from the original

Output:

- `revision/revised_chapters.jsonl`

### Stage 4: Chapter Proofread

Purpose:

- run an independent editorial pass over each revised chapter

Checks:

- omissions
- mistranslations
- repeated text
- logic breaks
- terminology drift
- punctuation and numeral formatting
- quote and reference formatting problems

Rules:

- proofreading should be role-separated from revision logic
- the proofreader should evaluate against explicit criteria, not freeform “improve the text”
- changes and findings must be logged

Output:

- `proofread/proofread_notes.jsonl`
- `proofread/proofread_changes.jsonl`

### Stage 5: Book Final Review

Purpose:

- perform whole-book consistency review after all chapter work is done

Checks:

- cross-chapter term drift
- title inconsistency
- tone inconsistency
- inconsistent handling of references, appendices, and back matter
- unresolved whole-book editorial decisions

Rules:

- this stage should modify final text only where it improves whole-book consistency
- it should emit a compact editorial log explaining major interventions

Output:

- `final/final_chapters.jsonl`
- `final/translated.txt`
- `final/translated.pdf`
- `editorial_log.json`

## Working Directory Layout

Each publishing run should live alongside, not inside, the engineering run state. The simplest shape is:

```text
out/
  book-name/
    engineering/...
    publishing/
      manifest.json
      draft/
        chapters.jsonl
        draft.txt
      lexicon/
        glossary.json
        names.json
        decisions.json
      revision/
        revised_chapters.jsonl
      proofread/
        proofread_notes.jsonl
        proofread_changes.jsonl
      final/
        final_chapters.jsonl
        translated.txt
        translated.pdf
      qa/
        pages/
        qa_summary.json
      editorial_log.json
      run_summary.json
```

This keeps engineering and publishing outputs isolated while preserving a shared root identity for the same source book.

## State and Resume Semantics

Publishing mode should be resumable, but stage-aware.

Rules:

- each stage must persist its outputs explicitly
- later stages may depend on hashes/fingerprints of earlier artifacts
- if the draft changes, lexicon/revision/proofread/final-review become stale
- if lexicon or style config changes, revision/proofread/final-review become stale
- if revision changes, proofread/final-review become stale

Required controls:

- `--resume` by default
- `--force` to rerun the entire publishing workflow
- `--from-stage <stage>` to restart from a stage boundary
- `--to-stage <stage>` to stop early for debugging or manual inspection

Stage names:

- `draft`
- `lexicon`
- `revision`
- `proofread`
- `final-review`

## CLI Design

High-level command:

```bash
book-translator publishing --input ./books --output ./out --provider gemini --model gemini-3.1-flash-lite-preview
```

Core options:

- `--input`
- `--output`
- `--provider`
- `--model`
- `--api-key-env`
- `--resume/--no-resume`
- `--force`
- `--from-stage`
- `--to-stage`
- `--glossary`
- `--name-map`
- `--style` with default `non-fiction-publishing`
- `--render-pdf/--no-render-pdf`
- `--max-concurrency`

The publishing command should default to a more conservative concurrency profile than engineering mode, because quality-first staged workflows benefit less from wide fan-out and often pass larger contextual payloads.

## Provider and Model Strategy

The system should support both OpenAI and Gemini, but the pipeline must not assume a single model is responsible for every stage.

Design principle:

- draft generation, lexicon extraction, revision, and proofreading are different tasks
- the code structure must make future stage-level model routing straightforward
- Phase 1 uses one provider/model configuration per publishing run to keep scope controlled

Quality rule:

- better results come from stage separation and explicit editorial roles, not from simply paying for a larger model and using one prompt

## Style System

The publishing mode needs explicit style guidance, not ad-hoc prompt prose.

Required baseline style:

- formal non-fiction Chinese
- natural and controlled syntax
- fidelity over flourish
- no chatty explanation tone
- no internet phrasing
- no unnecessary amplification

The style system should be represented as structured guidance, not only a long prompt string. At minimum, it should define:

- target voice
- sentence restraint rules
- quotation handling
- numeral/date/title conventions
- prohibited patterns

## Artifact and Audit Requirements

The publishing pipeline should preserve enough information to answer:

- what was the draft?
- what terms were normalized?
- what changed during revision?
- what did proofreading flag or rewrite?
- what whole-book decisions were applied late?

This does not require token-by-token diffs, but it does require stage outputs and editorial notes to be preserved as machine-readable artifacts.

## PDF and QA Integration

The final publishing manuscript should reuse the current polished PDF and raster QA facilities.

Rules:

- publishing mode should produce `final/translated.pdf`
- `qa-pdf` should be able to operate on the publishing final PDF
- publishing final PDF generation should not fork into a separate renderer in this phase

## Testing Strategy

### Unit Tests

- stage boundary invalidation and resume logic
- lexicon extraction and merge rules
- revision/proofread artifact schema
- style rule helpers
- publishing workspace path resolution

### Integration Tests

- small synthetic EPUB/PDF publishing run using mocked provider responses
- end-to-end artifact production across stages
- `--from-stage` and `--to-stage` behavior
- stale-stage invalidation when lexicon/style changes
- final assembled text and PDF generation

### Acceptance Tests

- run publishing mode on a real non-fiction workspace
- inspect draft, lexicon, final text, editorial log, and final PDF
- use `qa-pdf` against the final publishing PDF for visual review

## Risks and Constraints

### Quality Risk

Publication quality will still vary by source text and model behavior. The design reduces variance through staged editorial control, but cannot guarantee commercial publication readiness in every case.

### Cost and Latency Risk

This pipeline is intentionally expensive relative to engineering mode. Quality is the priority. The architecture should preserve measurement and reporting so cost remains visible even if it is not the primary optimization target.

### Scope Risk

If the first implementation also tries to support fiction, OCR, interactive editing, and sentence-level comparison, the pipeline will sprawl and stall. First implementation must stay focused on non-fiction publication-quality output.

## Recommended Implementation Scope

Phase 1 should include:

- explicit `engineering` and `publishing` commands
- publishing draft/lexicon/revision/proofread/final-review stages
- publishing workspace structure
- resumable stage-aware state
- final text and PDF output
- editorial notes and lexicon artifacts

Phase 1 should exclude:

- scanned PDF support
- fiction-specific style packs
- interactive review UI
- sentence-aligned bilingual editing
- human approval checkpoints inside the CLI flow

## Decision

Build publication-quality translation as a second, explicit pipeline inside the existing repository. Reuse the current foundation where it is stable, but keep publishing orchestration separate from engineering translation to preserve clarity, maintainability, and quality control.
