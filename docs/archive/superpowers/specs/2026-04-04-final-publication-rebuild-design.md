# Final Publication Rebuild And Zero-Unresolved Gate Design

Date: 2026-04-04

## Summary

Rebuild the current `publishing` output path so `The Book of Elon` can only be labeled as a final
edition when the machine editorial system can prove all tracked issues are closed. The current
`publishing` pipeline already reaches `deep-review`, renders both `PDF` and `EPUB`, and emits audit
artifacts, but it still allows a manuscript to be treated as "done" while the final audit report
contains unresolved findings.

The user has now set a harder standard:

- the rebuilt edition must be fully proofread against the English source
- the rebuilt edition must be aligned with the source book's editorial structure
- the final score must be at least `9.0`
- the edition is not allowed to pass if `unresolved_count > 0`
- if the rebuild does not pass, the system must roll back to a safer stage and try again rather
  than pretending the candidate is final

This design keeps the current `publishing draft` as the default rollback baseline, adds a staged
candidate/release separation, strengthens chapter-level audit and rollback logic, expands the final
gate, and requires both `PDF` and `EPUB` outputs to be rendered from the same gate-approved final
content.

## Goals

- Require `unresolved_count = 0` before any manuscript can be promoted to final release.
- Require high-severity audit findings, structural findings, citation/image findings, and visual
  blockers to be zero before release.
- Preserve the existing rule that input format determines default primary output:
  - `PDF -> PDF`
  - `EPUB -> EPUB`
- Preserve explicit optional cross-format output:
  - `PDF -> PDF + EPUB`
  - `EPUB -> EPUB + PDF`
- Rebuild from `publishing draft` by default instead of immediately re-translating the entire book.
- Allow chapter-scoped rollback and chapter-scoped retranslation escalation before escalating to a
  whole-book retranslation.
- Prevent failed rebuild attempts from overwriting the current shipped `publishing/final` output.
- Emit a machine-readable release gate report and a machine-readable score breakdown.
- Make the final score defensible instead of subjective.

## Non-Goals

- No OCR or scanned-PDF support in this phase.
- No pixel-perfect recreation of every original source page.
- No interactive human review UI.
- No unlimited auto-rewrite loop until a model "feels done."
- No fiction-oriented literary voice transformation.
- No automatic promotion of partially successful rebuilds.

## Hard Release Gate

The rebuilt manuscript may only be promoted from candidate to final release if all of the following
are true:

- `failed_chunks = 0`
- `unresolved_count = 0`
- `high_severity_count = 0`
- `structural_issue_count = 0`
- `citation_issue_count = 0`
- `image_or_caption_issue_count = 0`
- `visual_blocker_count = 0`
- `primary_output_validation_passed = true`
- `cross_output_validation_passed = true` when an additional output was requested
- `quality_score.overall >= 9.0`

If any condition fails:

- the candidate build is not promoted
- the previous shipped `publishing/final` release remains untouched
- the gate report must name the required rollback level

## Current Problem

The current implementation has three release-integrity problems:

1. **Completion and acceptance are too loosely coupled.**
   The pipeline can finish `deep-review` and render outputs even while the final audit report still
   records unresolved findings.

2. **Repair coverage is too shallow relative to detection coverage.**
   The system is better at finding `possible_omission` or structural drift than at reducing those
   findings to zero.

3. **Release writes are too eager.**
   Today the `publishing/final` tree represents both "latest generated output" and "approved final
   edition." Those are different concepts and must be separated.

## Product Decision

Keep the existing two top-level modes:

```bash
book-translator engineering ...
book-translator publishing ...
```

Do not add a third translation mode. This work upgrades `publishing` so that it can distinguish:

- `candidate rebuild`
- `approved final release`

The current `publishing/final` path remains the release path. Failed rebuilds must go to a separate
candidate area until they pass the gate.

## Candidate vs Release Model

Introduce two distinct output tiers inside `publishing`:

- `publishing/candidate/`
  - latest rebuild attempt
  - may contain unresolved issues
  - safe workspace for repeated repair and rerender cycles

- `publishing/final/`
  - only updated when the release gate passes
  - always points to the current approved edition

Promotion rules:

- build candidate artifacts first
- run the final gate on candidate artifacts
- promote candidate files into `publishing/final/` only if the gate passes
- keep the existing final release untouched if the gate fails

This avoids destructive "final overwrite" behavior during a failed rebuild.

## Rebuild Baseline And Rollback Policy

Default rollback policy:

1. Start from `publishing/draft/` as the baseline.
2. Rebuild structure, audit, repair, and outputs on top of that draft.
3. If a chapter still has unresolved findings after repair and confirmation:
   - discard that chapter's candidate downstream artifacts
   - rebuild that chapter from draft
4. If the same chapter still cannot pass:
   - escalate to chapter-only retranslation from source
5. If multiple chapters continue to fail for the same systemic reason:
   - escalate to whole-book retranslation

This matches the user's requested priority:

- prefer a controlled rollback from `draft`
- only escalate to more expensive full retranslation when draft-based rebuilds cannot close the
  audit

## Architecture Overview

The rebuilt flow has five layers:

### 1. Draft Baseline Layer

Use the current `publishing/draft` output as the baseline source of translated content. This is the
starting point for all rebuild work unless chapter or whole-book retranslation is explicitly
triggered.

### 2. Structured Editorial Model Layer

Continue the move away from flattened chapter text. The candidate rebuild should operate on the
structured publishing model introduced in the structured audit design:

- chapters
- headings
- paragraphs
- ordered items
- unordered items
- Q&A blocks
- callouts
- quotes
- references
- citations
- images
- captions

Every audit, repair, rerender, and promotion step should consume this structured representation.

### 3. Chapter Audit And Repair Layer

For each chapter:

- run structure audit
- run source audit
- run independent review
- run arbitration for disputed findings
- apply only approved low- and medium-risk repairs
- rerun a confirmation audit

If the chapter still has unresolved findings after confirmation, it is not eligible for release and
must enter rollback escalation.

### 4. Candidate Render Layer

Render candidate outputs from the structured candidate manuscript:

- candidate `PDF`
- candidate `EPUB`

Render only the requested outputs, following the existing input/output rules.

### 5. Final Gate And Promotion Layer

Compute:

- unresolved findings
- severity totals
- structural totals
- citation/image totals
- visual blocker totals
- quality score

Only promote the candidate build if every hard gate passes.

## Chapter Audit Model

Each chapter must carry a chapter-scoped gate summary with at least:

- `chapter_id`
- `source_anchor`
- `audit_finding_count`
- `review_finding_count`
- `agreed_count`
- `disputed_count`
- `repaired_count`
- `confirmation_finding_count`
- `unresolved_count`
- `rollback_level_required`

`rollback_level_required` values:

- `none`
- `chapter_repair`
- `chapter_redraft`
- `chapter_retranslate`
- `book_retranslate`

The whole-book release gate aggregates these chapter results.

## Structural Integrity Requirements

The rebuild must treat the following as release-critical structures:

- chapter and part order
- numbered list cardinality and ordering
- Q&A structure
- callout blocks
- inline citation markers
- back-matter reference entries
- image anchors
- caption anchors

If the source contains one of these structures and the target loses it, that is not merely a style
issue. It is a release-blocking structure issue.

## Image, Caption, Callout, And Citation Rules

### Images

- If a source image can be recovered, attach it to the structured model and render it in requested
  outputs.
- If an image cannot be recovered, preserve at least:
  - placement anchor
  - caption text if recoverable
  - machine-readable missing-asset status
- A source image with neither image output nor caption/anchor preservation counts as unresolved.

### Captions

- Captions are first-class content blocks.
- Captions must stay associated with their source image anchor.
- Missing or detached captions count as release-blocking structure issues.

### Callouts

- Callout detection and rendering must be audited against source structure, not only style
  heuristics.
- If the source uses a callout-like editorial block and the candidate flattens it into a regular
  paragraph, that counts as a structural issue.

### Citations

- Inline numeric markers become explicit `citation` nodes.
- Citation markers must preserve:
  - marker text
  - block association
  - ordering
  - display semantics
- Missing or malformed citation markers count as unresolved citation issues.

## PDF And EPUB Output Behavior

Maintain the existing behavior contract:

- `PDF` input defaults to primary `PDF` output
- `EPUB` input defaults to primary `EPUB` output
- `--also-pdf` and `--also-epub` remain explicit cross-format requests

Strengthen the implementation rule:

- both output formats must derive from the same gate-approved candidate manuscript
- do not allow `PDF` and `EPUB` to diverge semantically
- do not promote release unless the primary output passes validation
- if a secondary output was requested, it must also pass structural validation before promotion

## Quality Score Model

Introduce a machine-readable scorecard:

- `fidelity_score`
- `structure_score`
- `terminology_score`
- `layout_score`
- `source_style_alignment_score`
- `epub_integrity_score`
- `overall`

Scoring policy:

- If any hard gate fails, `overall` may still be computed, but release status must remain `failed`
  even if `overall >= 9.0`.
- `overall >= 9.0` is necessary but not sufficient.
- Hard gate pass is necessary and non-negotiable.

This prevents a superficially strong manuscript from being promoted while unresolved defects remain.

## New Artifacts

Add or strengthen these publishing artifacts:

- `publishing/candidate/final/translated.pdf`
- `publishing/candidate/final/translated.epub`
- `publishing/candidate/final/translated.txt`
- `publishing/audit/final_gate_report.json`
- `publishing/audit/quality_score.json`
- `publishing/audit/unresolved_findings.jsonl`
- `publishing/qa/visual_blockers.json`
- `publishing/candidate/state/*.json`

`final_gate_report.json` must include:

- release status (`passed` or `failed`)
- reason for failure if any
- unresolved totals
- severity totals
- structure/citation/image totals
- visual blocker totals
- rollback recommendation
- whether promotion occurred

## CLI Semantics

Do not add a new top-level mode.

The rebuilt behavior stays under:

```bash
book-translator publishing ...
```

No breaking CLI changes are required. Internal behavior changes only:

- use candidate workspace for rebuild output
- promote to final only when gate passes
- preserve default primary output by input format
- preserve explicit `--also-pdf` and `--also-epub`

## Testing Strategy

### Unit Tests

- chapter gate aggregation
- rollback recommendation logic
- hard gate evaluation
- score calculation
- candidate-to-final promotion rules
- unresolved finding serialization
- image/caption/citation unresolved classification
- input-format default output selection

### Integration Tests

- `draft -> audit -> review -> arbitration -> repair -> confirmation`
- failed candidate build does not overwrite existing final release
- passing candidate build promotes all requested outputs into final release
- `PDF -> PDF`
- `PDF -> PDF + EPUB`
- `EPUB -> EPUB`
- `EPUB -> EPUB + PDF`

### Real-Book Acceptance

Use `The Book of Elon` as the primary acceptance target.

The rebuild is not considered complete until the candidate and release system can produce:

- `unresolved_count = 0`
- no visual blockers in sampled key pages
- approved release `PDF`
- approved release `EPUB`
- `quality_score.overall >= 9.0`

## Risks

### Risk 1: Infinite Repair Thrash

Mitigation:

- chapter-scoped rollback levels
- no unlimited rewrite loops
- escalate from repair to redraft to retranslation using explicit thresholds

### Risk 2: Candidate/Final Drift

Mitigation:

- final release only updated by explicit promotion step
- candidate and final state files must remain separate

### Risk 3: Overclaiming Quality

Mitigation:

- no "final" labeling without gate pass
- score alone cannot bypass unresolved findings

## Decision Summary

This phase makes three core decisions:

1. **Use `publishing draft` as the default rollback baseline.**
2. **Separate candidate rebuild output from approved final release output.**
3. **Treat zero unresolved findings and a 9.0+ score as jointly required for release.**

The result is a stricter, more honest publishing pipeline that can fail safely, rebuild safely, and
only promote a manuscript when its own evidence supports the label "final edition."
