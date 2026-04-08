# Structured Publishing Audit And EPUB Design

Date: 2026-04-04

## Summary

Upgrade `publishing` mode from a staged translation pipeline into a structured editorial system that
can do three things the current implementation does not guarantee strongly enough:

- audit translated content against the English source for omissions, compression, and structural loss
- repair low- and medium-risk issues through a multi-agent consensus workflow
- generate both polished `PDF` and standard reflowable `EPUB` outputs from the same final content
  model

The current publishing pipeline already supports `draft -> lexicon -> revision -> proofread ->
final-review -> deep-review`, but it still treats the final manuscript primarily as flattened chapter
text plus renderer heuristics. The user now wants a stronger guarantee that content is not silently
lost, that structural elements such as numbered lists, callouts, citations, images, and captions are
preserved, and that output behavior is format-aware:

- `PDF` input defaults to `PDF` output
- `EPUB` input defaults to `EPUB` output
- cross-format output is optional and explicit

This design introduces a structured publishing book model, a multi-agent audit/review/arbitration
loop, stronger source-aware reporting, image/caption preservation policy, and a new reflowable EPUB
renderer built on the same final content representation used by the polished PDF renderer.

## Goals

- Preserve the current `publishing` command as the quality-first path.
- Add a structured internal book model rich enough to support auditing and dual-format output.
- Detect and report likely omissions, mistranslations, structural flattening, image/caption loss, and
  citation/reference drift.
- Add a multi-agent review loop with independent audit, independent review, arbitration, controlled
  repair, and one confirmation pass.
- Keep automatic fixes limited to low- and medium-risk issue classes.
- Restore or preserve structural elements that materially affect fidelity:
  - ordered/unordered lists
  - Q&A blocks
  - callout boxes and short highlighted quotations
  - citations and references
  - images, captions, and image anchors where recoverable
- Support default output behavior based on input format:
  - `PDF -> PDF`
  - `EPUB -> EPUB`
- Support explicit cross-format output:
  - `PDF -> PDF + EPUB`
  - `EPUB -> EPUB + PDF`
- Produce a reflowable standards-compliant EPUB suitable for common e-readers.
- Emit auditable machine-readable artifacts explaining what was found, how consensus was reached, and
  what was automatically repaired.

## Non-Goals

- No OCR or scanned-PDF support in this phase.
- No page-faithful reconstruction of every source page.
- No interactive human review UI or side-by-side editor in this phase.
- No fiction-specific literary rewriting system.
- No automatic high-risk prose rewrites, long-form restructuring, or voice transformation.
- No guarantee that all extracted source images can be recovered from every PDF.

## Current Problem

The current publishing path is materially stronger than engineering mode, but it still has three
architectural limitations:

1. **Final text is still too flattened.**
   Deep review can annotate or locally repair text, but the system does not yet treat images,
   captions, numbered list items, Q&A blocks, callouts, and citations as first-class structured
   content throughout the final output path.

2. **Audit confidence is not yet strong enough.**
   Source-aware review exists, but the system still cannot honestly claim that the manuscript was
   checked in a way that strongly minimizes omission risk across every content type.

3. **Output logic is still PDF-first.**
   EPUB input is supported for extraction, but there is no high-quality publishing EPUB renderer and
   no explicit separation between default output and optional cross-format conversion.

The user now wants a stricter standard:

- stronger proof that the source was fully and faithfully rendered
- stronger automatic detection and repair of structural errors
- richer image/caption handling
- clean separation between default output format and optional second output format
- a usable publication-style EPUB alongside the improved publishing PDF

## Product Shape

Keep the CLI anchored on the existing two-mode mental model:

```bash
book-translator engineering ...
book-translator publishing ...
```

This work extends `publishing`; it does not add a third top-level translation mode.

The public behavior should become:

- `engineering`
  - fast, scalable, chunk-level translation
  - current PDF-oriented polished output remains acceptable
- `publishing`
  - structured, source-aware, quality-first editorial workflow
  - default output format follows input format
  - optional cross-format output must be explicitly requested

The top-level compatibility alias should remain mapped to `engineering`.

## Editorial Standard

The target standard for this phase is not merely “publication-like formatting.” It is:

- conservative fidelity to the English source
- strong resistance to silent omissions
- preservation of content structure where structure carries meaning
- restrained, formal non-fiction Chinese
- recoverable editorial traceability
- output parity across `PDF` and `EPUB` from the same final content basis

This is still not a substitute for a final human copy editor or legal publishing review. It is a
much stronger machine editorial system than the current publishing implementation.

## Architecture Overview

The system should evolve into four layers:

### 1. Source Ingestion Layer

Already present and still reusable:

- `extractors/pdf.py`
- `extractors/epub.py`
- chapter detection
- chunking
- provider transport

This layer continues to recover source chapters and raw text, but it must also expose any available
asset and caption clues needed by downstream structure building.

### 2. Structured Publishing Model Layer

New core internal representation added for publishing mode. Every publishing stage after initial
extraction should be able to consume or emit this richer model instead of relying only on flattened
chapter strings.

### 3. Multi-Agent Audit And Repair Layer

New orchestration above the current deep-review system:

- `audit agent`
- `review agent`
- `arbiter agent`
- repair engine
- acceptance pass

This layer is responsible for fidelity checking, issue consensus, repair decisions, and post-repair
confirmation.

### 4. Output Layer

Two renderers fed from the same final structured book:

- polished PDF renderer
- reflowable EPUB renderer

This is the key separation that prevents `PDF` and `EPUB` from diverging semantically.

## Structured Publishing Book Model

Introduce a publishing-specific structured book representation with at least these concepts:

### Book

- source metadata
- source format (`pdf` or `epub`)
- target primary output (`pdf` or `epub`)
- requested additional outputs
- title metadata
- chapter order
- global glossary/name decisions
- asset manifest
- review status metadata

### Chapter

- stable chapter id
- source title
- translated title
- level / kind (`part`, `chapter`, appendix-like)
- source anchor info
- ordered blocks

### Block

A block is the smallest editorially meaningful output unit. Types should include:

- `paragraph`
- `heading`
- `ordered_item`
- `unordered_item`
- `qa_question`
- `qa_answer`
- `callout`
- `quote`
- `reference_entry`
- `image`
- `caption`
- `spacer` only if strictly necessary in renderer-local logic, not as semantic content

Each block should preserve:

- source excerpt or source anchor reference
- translated content
- inline citations / footnote markers where applicable
- block-level issue annotations
- repair history / provenance where changed by the audit loop

### Asset

- source asset id
- source location hint
- extracted binary path if available
- caption text if known
- placement anchor
- availability status:
  - extracted
  - caption-only
  - missing

### Citation

- local marker text / numeric marker
- block association
- target reference association if known
- display class (inline marker, reference note, back-matter citation)

This structured model becomes the canonical representation for `publishing` after the initial draft
phase.

## Multi-Agent Audit Loop

The new audit framework should be additive to the current `deep-review` idea, but more explicit and
more reliable.

### Pass 1: Chapter-Level Audit

The `audit agent` receives:

- source chapter text
- current translated chapter text
- structured block model
- glossary/name decisions
- image/caption/citation metadata

It emits issue candidates such as:

- likely omission
- likely mistranslation
- list flattening
- Q&A flattening
- callout-worthy quote not preserved
- citation drift
- reference drift
- image present in source path but missing in target
- caption detached from image
- title inconsistency

### Pass 2: Independent Review

The `review agent` receives the same source materials but should not receive the first agent’s prose
conclusion. It independently evaluates the same chapter/problem space.

This separation is required to reduce correlated hallucinated findings.

### Pass 3: Consensus And Arbitration

The system merges findings into three buckets:

- `agreed`
  - both agents identify the same or materially overlapping issue
- `disputed`
  - one agent flags an issue and the other does not, or they disagree on severity/fixability
- `low_confidence`
  - localization is weak or evidence is too noisy

Only `disputed` findings go to the `arbiter agent`.

The `arbiter agent` decides:

- valid issue vs invalid issue
- severity
- fixability
- preferred repair strategy

### Pass 4: Controlled Repair

The repair engine only auto-applies low- and medium-risk fixes:

- restore missing translated content
- repair obvious mistranslations in a bounded span
- restore list item boundaries
- repair numbering or item ordering
- restore Q&A structure
- restore citation markers or caption linkage
- repair title inconsistency
- enforce glossary/name consistency
- reclassify paragraph vs callout when source evidence is strong

The repair engine must not:

- rewrite whole chapters for style
- invent images or captions not grounded in source evidence
- apply high-risk voice transformations
- continue mutating content after one repair cycle plus one verification cycle

### Pass 5: Confirmation

The repaired structured content is re-audited once.

Default stop rule:

- one repair cycle
- one confirmation cycle

No infinite self-editing loop.

## Audit Depth And Granularity

The audit system should run in mixed granularity mode:

- chapter-level scan first
- problem-fragment review and arbitration second

This avoids paying high cost for full fragment-level review when a chapter is already healthy, while
still allowing precise local repairs where risk is detected.

## Source-Aware Detection Rules

The system should combine LLM judgment with mechanical checks instead of relying on one alone.

### Structural Checks

- source vs target chapter count/order
- heading count and hierarchy drift
- ordered list counts and numbering continuity
- Q&A marker counts
- callout block count where source cues exist
- citation marker counts
- reference entry counts
- image asset count and caption-anchor count

### Risk Signals

- source block count vs target block count anomalies
- very high source compression into unusually short target spans
- dense numeric/instructional source spans collapsed into prose
- list-heavy source sections missing item boundaries
- image/caption references in source but not in target

### Agent Findings

Each finding should include:

- chapter id
- block or source anchor id when available
- issue type
- severity
- confidence
- source excerpt
- target excerpt
- agent verdicts
- arbitration result if needed
- auto-fix eligibility
- repair status

## Image And Caption Policy

The user selected this boundary:

- extract and restore images where feasible
- if extraction fails, preserve caption and placement anchor

So the renderer behavior should be:

- if source image asset is recoverable, include it in final `PDF` and `EPUB`
- if not recoverable but caption or placement is known, preserve the caption and an explicit image
  anchor marker in the structured model
- report missing assets in the final audit report

The first phase does not promise perfect source-layout image reconstruction. It promises recoverable
asset handling with explicit reporting of what could and could not be restored.

## Output Format Rules

The output system must strictly separate default behavior from optional cross-format output.

### Default Output By Input Format

- source input `PDF`
  - primary output defaults to `PDF`
- source input `EPUB`
  - primary output defaults to `EPUB`

### Optional Cross-Format Output

- `PDF` input may additionally produce `EPUB` only when explicitly requested
- `EPUB` input may additionally produce `PDF` only when explicitly requested

The system should not silently emit both formats by default.

## EPUB Product Requirements

The EPUB output must be a standard reflowable EPUB, not a fixed-layout pseudo-PDF.

Required properties:

- valid table of contents/navigation
- chapter and subchapter navigation
- readable CSS tuned for long-form Chinese reading
- preserved heading hierarchy
- preserved lists and Q&A structures
- preserved callouts and quotations in e-reader-friendly styling
- inline citations and references represented sensibly within EPUB constraints
- images included when recoverable
- captions preserved

The EPUB renderer should prioritize compatibility with common readers over CSS cleverness.

## CLI Shape

Keep the public workflow simple:

```bash
book-translator publishing --input ./book.pdf --output ./out
```

Default result:

- `translated.pdf`

Explicit additional EPUB:

```bash
book-translator publishing --input ./book.pdf --output ./out --also-epub
```

Default EPUB behavior:

```bash
book-translator publishing --input ./book.epub --output ./out
```

Default result:

- `translated.epub`

Explicit additional PDF:

```bash
book-translator publishing --input ./book.epub --output ./out --also-pdf
```

New or clarified publishing options:

- `--also-pdf`
- `--also-epub`
- `--audit-depth`
- `--enable-cross-review/--no-cross-review`
- `--image-policy`

Recommended defaults:

- `--audit-depth consensus`
- `--enable-cross-review`
- `--image-policy extract-or-preserve-caption`

## Workspace Artifacts

Add or strengthen these publishing artifacts:

```text
publishing/
  audit/
    source_audit.jsonl
    review_audit.jsonl
    consensus.json
    final_audit_report.json
  assets/
    manifest.json
    images/...
  deep_review/
    findings.jsonl
    revised_chapters.jsonl
    decisions.json
  final/
    translated.txt
    translated.pdf
    translated.epub
```

Artifact meanings:

- `audit/source_audit.jsonl`
  - primary audit agent findings
- `audit/review_audit.jsonl`
  - independent review agent findings
- `audit/consensus.json`
  - merged agreement/dispute/arbitration statistics and outcomes
- `audit/final_audit_report.json`
  - final machine-readable audit summary for omissions, mistranslations, structural loss, image
    issues, citation issues, repaired items, and unresolved items
- `assets/manifest.json`
  - extracted and unresolved image/caption inventory
- `final/translated.pdf`
  - primary or optional PDF output
- `final/translated.epub`
  - primary or optional EPUB output

If a format is not requested and not the primary default for the source format, its artifact should
not be created.

## Publishing Stage Evolution

The current publishing stages remain:

- `draft`
- `lexicon`
- `revision`
- `proofread`
- `final-review`
- `deep-review`

This design does not add another public stage name yet. Instead, `deep-review` becomes internally
richer and consumes the new audit subpipeline:

- structure build
- audit agent
- review agent
- consensus/arbitration
- controlled repair
- confirmation pass
- final text assembly
- requested PDF/EPUB rendering

That keeps CLI stage semantics stable while still allowing a large internal upgrade.

## Testing Strategy

### Unit Tests

- structured block classification
- list, Q&A, citation, and caption preservation
- audit finding merge and arbitration logic
- auto-fix gating for low/medium risk only
- input-format-driven primary output selection
- `--also-pdf` and `--also-epub` behavior
- EPUB generation for headings, lists, callouts, images, and navigation

### Integration Tests

- `PDF -> PDF`
- `PDF -> PDF + EPUB`
- `EPUB -> EPUB`
- `EPUB -> EPUB + PDF`
- multi-agent audit agreement path
- dispute path requiring arbitration
- repair + confirmation path
- image extracted vs caption-only fallback path

### Real-Book Acceptance

Run the upgraded publishing pipeline on:

- `The Book of Elon: A Guide to Purpose and Success`

Acceptance checks:

- no regression in current PDF production
- stronger audit artifacts generated
- improved handling of list-heavy pages and mixed-structure pages
- audit report includes image/caption findings where relevant
- EPUB output opens and navigates correctly

### Visual QA

Continue using rasterized page QA for PDF and add EPUB-level structural verification:

- TOC navigation
- chapter starts
- list-heavy pages
- image/caption pages
- citation/reference pages

## Risks And Guardrails

### Risk: Overfitting to one book

Guardrail:

- build issue classes and structure types generically
- use the Elon book as acceptance material, not as a one-off hardcoded template

### Risk: Multi-agent loops drift into uncontrolled rewriting

Guardrail:

- cap the system at one repair pass and one confirmation pass
- block high-risk rewrites
- require arbitration for disagreement-driven fixes

### Risk: EPUB renderer diverges from PDF manuscript content

Guardrail:

- both renderers consume the same final structured chapter/block model
- no renderer-specific ad hoc content transformations

### Risk: Image extraction coverage is inconsistent

Guardrail:

- explicit asset status reporting
- caption preservation fallback
- unresolved assets surfaced in final audit report

## Implementation Boundary

This is a major publishing-mode upgrade and should not be treated as a small patch. The work should
be executed as a new implementation plan with staged tasks covering:

- structured publishing model
- multi-agent audit/review/arbitration plumbing
- repair engine
- asset and caption preservation
- EPUB renderer
- CLI and workspace updates
- regression and acceptance tests

The next step after this approved spec is to write a detailed implementation plan, not to begin
coding directly.
