# Source-Aware Publishing Deep Review Design

Date: 2026-04-03

## Summary

Add a second-pass, whole-book editorial refinement workflow on top of the current `publishing`
pipeline for `The Book of Elon: A Guide to Purpose and Success`, then generalize the mechanism
so future non-fiction books can go through the same deeper review path. The current publishing
pipeline already produces a readable publication-style Chinese manuscript and polished PDF, but it
still leaves three quality gaps the user explicitly called out:

- some sections are not fully proofread against the English source
- some translated content still misses structure, emphasis, or editorial cues from the source
- some PDF pages remain under-refined in layout, mixed-script spacing, and source-aligned styling

This design introduces a source-aware audit and rewrite loop that sits above the existing
`draft -> lexicon -> revision -> proofread -> final-review` chain. The new pass must compare
source chapters against the Chinese publishing manuscript, detect omissions and structural drift,
apply corrective editorial rewrites, and then rerender the final PDF with more rigorous layout QA.

## Goals

- Audit the entire publishing manuscript against the original English source, not just selected pages.
- Detect omissions, mistranslations, structural flattening, and lost emphasis patterns.
- Apply corrections back into the publishing final text instead of only recording advisory notes.
- Tighten the Chinese prose toward a restrained, formally published non-fiction style.
- Improve source-aware layout fidelity for lists, Q&A blocks, callouts, inline citations, and other
  editorial markers already visible in the source book.
- Produce a refreshed publishing PDF after the deep review pass.
- Preserve traceability so each deep-review change can be inspected later.

## Non-Goals

- No OCR or scanned-PDF support.
- No fiction-specific literary style system.
- No page-faithful reproduction of every source page.
- No human-in-the-loop editor UI in this phase.
- No rewrite of the rendering stack away from the current `reportlab` pipeline.

## Problem Statement

The current `publishing` mode improved quality substantially, but it still behaves like a staged
translation pipeline with light editorial cleanup, not a full source-aware editorial review system.
That shows up in several failure classes:

- numbered lists can still collapse or partially flatten if not explicitly normalized
- some chapter titles or structural labels remain weaker than the source warrants
- mixed Chinese/English/numeric text can still produce visually awkward rhythm
- callouts, quotes, Q&A passages, and references are not yet audited systematically across the book
- proofreading logs exist, but they do not yet prove that each chapter was checked for omissions
  against the source text

The user now wants the opposite operating mode: the entire book must be rechecked and optimized
until the remaining issues are exceptions, not the default.

## Product Shape

Keep the existing public CLI shape:

```bash
book-translator publishing ...
```

but deepen the publishing pipeline internally with a new source-aware refinement layer. This should
not become a separate third top-level mode. The experience should remain:

- `engineering`: fast, faithful, scalable
- `publishing`: slow, quality-first, source-aware, deeply proofread

The new deep review logic becomes part of `publishing`, because the user expects publishing mode to
be the quality-maximal path.

## Editorial Standard

The target standard for this phase is:

- every chapter must be checked against the original English source
- no silent omissions are acceptable
- no major structural flattening is acceptable
- translated Chinese should read like a mature, restrained non-fiction publication
- styling signals present in the source should be preserved when they materially affect emphasis or
  reading rhythm

This is still not a legal guarantee of commercial publication readiness, but it should move the
manuscript from “good AI-generated publishing draft” toward “seriously edited publication candidate”.

## Architecture Overview

The current publishing stack already includes:

- source extraction
- chapter detection
- chunk translation
- lexicon normalization
- chapter revision
- chapter proofread
- whole-book final review
- polished PDF generation
- raster-based PDF QA

The new deep review layer should add four focused responsibilities:

- `publishing/source_audit.py`
  compares source chapters and final Chinese chapters to identify omissions, mistrendered structure,
  weakened emphasis, and suspect formatting zones
- `publishing/editorial_revision.py`
  consumes audit findings and rewrites chapter text deterministically enough to preserve fidelity
  while improving publication quality
- `publishing/layout_review.py`
  derives source-aware structural annotations for PDF rendering, especially for lists, callouts,
  Q&A passages, and reference markers
- `publishing/deep_review.py`
  orchestrates the new stage and persists artifacts

The existing renderer in `output/polished_pdf.py` remains the final rendering path, but it must gain
better support for the structural annotations emitted by the deep review stage.

## New Deep Review Stage

Insert a new stage after `final-review`:

- `deep-review`

The publishing stage order becomes:

- `draft`
- `lexicon`
- `revision`
- `proofread`
- `final-review`
- `deep-review`

`deep-review` responsibilities:

- align each final Chinese chapter with the English source chapter
- detect likely omissions and suspicious compression
- detect lost list structure, lost Q&A structure, lost callout opportunities, and weak headings
- generate actionable findings
- apply editorial rewrites where the finding is confident enough to fix automatically
- persist both findings and corrected chapter text
- assemble and rerender the final TXT and PDF from the corrected deep-review artifacts

## Source-Aware Audit Rules

The source audit must be conservative and evidence-driven. It should not treat every style
difference as a bug. It should focus on concrete risk classes:

- source paragraph or list item missing from the Chinese final chapter
- large source passage compressed into an implausibly short Chinese span
- ordered lists collapsed into prose
- Q&A markers or dialogue-like structure lost
- source-highlighted short quotations not represented as callouts or emphasized blocks where the
  surrounding structure strongly suggests they should be
- citation markers present in the source-side notes flow but not visible in the rendered result

Audit output per finding should include:

- `chapter_id`
- `finding_type`
- `severity`
- `source_excerpt`
- `target_excerpt`
- `reason`
- `auto_fixable`

## Editorial Rewrite Rules

Automatic rewrites in deep review must stay within explicit boundaries:

- restore missing list structure
- restore missing short quotations or emphasized statements when source structure is clear
- split over-compressed paragraphs when source pacing clearly supports it
- strengthen weak chapter or section labels when the source provides unambiguous guidance
- tighten mixed-script spacing and punctuation if it improves readability without changing meaning
- fix likely omission cases by restoring missing content from already translated upstream material,
  or by regenerating the affected span if necessary

Automatic rewrites must not:

- invent content not grounded in the source
- replace the whole chapter when only one local problem exists
- make the Chinese more literary at the expense of accuracy
- freely paraphrase to chase style points

## Layout Refinement Scope

This phase should tighten the renderer specifically in the places where source-aware structure
matters most:

- ordered and unordered lists
- chapter-opening summaries
- callout-style emphasized quotations
- Q&A passages
- inline citation numbers
- references and back matter
- mixed Chinese/English/numeric paragraphs

The renderer should consume layout annotations from deep review rather than relying only on
heuristics from already-flattened text.

## Workspace Artifacts

Add a new subtree under `publishing/`:

```text
publishing/
  deep_review/
    findings.jsonl
    revised_chapters.jsonl
    decisions.json
  final/
    translated.txt
    translated.pdf
```

Artifact meanings:

- `deep_review/findings.jsonl`
  structured source-aware findings, including omissions and structural drift
- `deep_review/revised_chapters.jsonl`
  corrected chapter text after deep editorial repair
- `deep_review/decisions.json`
  summary counters and high-level decisions taken during the pass

The existing `publishing/final/translated.txt` and `publishing/final/translated.pdf` should be
rebuilt from `deep_review/revised_chapters.jsonl` once the stage completes.

## Resume and Invalidation Rules

The new stage must be resumable, but strict invalidation is required. The deep-review state becomes
invalid if any of these change:

- source fingerprint
- publishing config fingerprint
- proofread stage version
- final-review stage version
- deep-review stage version
- source-audit rules or renderer layout annotation schema

If invalidated, `deep-review` and downstream rendered outputs must be recomputed.

## Testing Strategy

### Unit Tests

- source-audit detection for missing numbered list structure
- source-audit detection for obvious omission candidates
- editorial rewrite of inline numbered lists back into block structure
- layout annotation generation for callouts, Q&A blocks, and inline citations
- renderer consumption of deep-review structural annotations

### Integration Tests

- a synthetic chapter where the Chinese final text drops one source item should produce an omission
  finding
- a synthetic chapter with flattened `1. 2. 3.` text should be restored into block items
- a source chapter with a short quote block should yield a callout annotation when confidence rules
  are met
- full publishing pipeline with `--to-stage deep-review` should emit deep-review artifacts and
  regenerated `final/translated.txt`

### Real-Book Acceptance

For `The Book of Elon: A Guide to Purpose and Success`:

- rerun publishing through `deep-review`
- inspect multiple previously weak pages, not just the fixed “69 methods” chapter
- rasterize a representative QA set across front matter, TOC, chapter openings, list-heavy pages,
  callout-heavy pages, and references
- verify that omission-sensitive and layout-sensitive pages are materially improved

## Implementation Notes

- prefer deterministic normalization first, model-assisted repair second
- keep automatic fixes local and surgical
- treat deep review as an editorial correction pass, not a full retranlation pass
- preserve all existing publishing outputs until the deep-review pass has produced replacements
- keep the final `translated.pdf` path stable for the user

## Success Criteria

This design is successful when:

- the entire book has structured deep-review findings
- the pipeline can point to which chapters were checked and what was corrected
- previously weak structural pages are fixed without introducing new regressions
- the final PDF shows fewer mixed-script spacing errors, fewer flattened structures, and stronger
  source-aware styling
- omission risk is materially lower because the pipeline now checks source-vs-target structure

