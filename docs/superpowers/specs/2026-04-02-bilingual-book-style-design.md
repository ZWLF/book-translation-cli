# Bilingual Book-Style PDF Refinement Design

## Goal

Upgrade the polished PDF renderer so translated books read more like a carefully edited Chinese print edition while staying structurally aligned with the original English book.

## Scope

- Keep the existing translation pipeline, chapter extraction, resume logic, and workspace outputs intact.
- Refine only the polished PDF rendering layer and the printable-book normalization it depends on.
- Add bilingual presentation for `Part` and `Chapter` titles:
  - Chinese as the primary title
  - English original as a secondary subtitle
- Apply the same bilingual structure to the table of contents for `Part` and `Chapter` entries.
- Distinguish `Part` pages from `Chapter` pages in layout and spacing.
- Improve Chinese reading comfort through more deliberate typography, spacing, and page rhythm.
- Reduce non-book artifacts in the final PDF, especially model echo text that does not belong in a published page.

## Non-Goals

- Pixel-perfect recreation of every page of the source English PDF.
- Bilingual treatment for intra-chapter section headings.
- Re-translation of the book body.
- A new HTML/CSS rendering pipeline.
- Manual, title-by-title editorial curation for a single book.

## Design Target

The renderer should aim for a high-fidelity editorial feel rather than a loose "pretty PDF."

That means:

- preserve the original book's structural rhythm
- make `Part` and `Chapter` openings feel intentional and spacious
- keep running headers and page furniture restrained
- prefer reading comfort over decorative flourishes
- let Chinese typography carry the page while English remains supportive

## Approach

Use the existing `reportlab` pipeline, but raise the abstraction level of title handling and page templates.

The renderer should stop treating every chapter heading as a single plain string. Instead it should normalize printable chapters into a richer title model that can express:

- title kind: `part`, `chapter`, or plain chapter-like fallback
- Chinese display title
- English source title
- whether the title should appear bilingually in the table of contents
- whether the page should use a `part` opening template or a `chapter` opening template

This keeps the implementation inside the current project while giving enough structure to control TOC rendering, headers, and opening-page layout consistently.

## Architecture

### 1. Printable title normalization

Extend the printable-book build step so each `PrintableChapter` carries enough metadata for bilingual rendering.

The normalization layer should:

- preserve the current ordered grouping by `chapter_index`
- classify `source_title` as `part` or `chapter` when it matches source-book structure
- keep Chinese title extraction from translated content, but avoid collapsing the English source title into the same field
- store both:
  - `title_zh`
  - `title_en`
- provide a stable display mode:
  - bilingual for `Part`
  - bilingual for `Chapter`
  - single-language fallback when no reliable Chinese title exists

### 2. Bilingual TOC rendering

Replace the current single-line TOC entry model with a grouped bilingual entry for `Part` and `Chapter`.

Rules:

- Chinese title is the primary line.
- English original sits beneath it in smaller, quieter type.
- Page number stays aligned once per entry group, not once per line.
- `Part` entries get more vertical breathing room than `Chapter` entries.
- TOC pages keep page numbers but do not show running headers.

The TOC should still be generated automatically from flowables, but the content passed into the TOC must reflect the bilingual display text rather than the current single title string.

### 3. Opening-page templates

Split opening-page behavior into distinct editorial patterns.

#### Part openings

- start on a new page
- use more vertical whitespace
- place Chinese title first, large and calm
- place English subtitle beneath, smaller and lighter
- suppress running headers on the opening page
- keep body text from crowding the title block

#### Chapter openings

- also start on a new page
- use a tighter but still deliberate layout than `Part`
- show Chinese primary title and English subtitle as a stacked bilingual pair
- maintain a stable gap between title block and first paragraph
- suppress running headers on the opening page

### 4. Body typography refinement

Improve reading comfort without making the pages look like a web export.

Adjustments:

- slightly rebalance page margins and line length toward a print-book reading block
- refine body size, leading, and first-line indentation for long-form Chinese reading
- reduce paragraph blockiness by using steadier spacing and less abrupt rhythm
- tune mixed Chinese-English lines so English titles, URLs, and names feel less jarring
- keep references and back matter quieter and more editorial

Typography should prioritize:

- comfortable sustained reading
- graceful Chinese body rhythm
- restrained hierarchy
- low visual noise

### 5. Artifact cleanup

Strengthen the normalization pass to remove obvious LLM echo text when it appears in translated content.

This includes patterns such as:

- `本书：...`
- `章节：...`
- `分块索引：...`
- similar prompt-echo metadata lines that are not part of the source book itself

Cleanup should remain conservative. It should remove obviously synthetic wrapper text without deleting legitimate content.

## Implementation Boundaries

The work should stay localized to:

- printable-book normalization
- polished PDF rendering
- regression tests for TOC, title metadata, and layout behavior

The work should not expand into:

- translation prompt redesign
- workspace schema migration
- EPUB/PDF extraction changes unrelated to rendering
- manual title authoring for this single title

## Verification

### Automated

- unit test bilingual title normalization for `Part` and `Chapter`
- unit test TOC display content for bilingual entries
- unit test opening-page template behavior, including suppression of running headers
- regression test that artifact-cleanup removes synthetic metadata while preserving body text
- full `ruff` and `pytest` pass

### Manual

Regenerate the polished PDF for:

- `The Book of Elon A Guide to Purpose and Success (Eric Jorgenson).pdf`

Then inspect:

- TOC opening pages
- at least one `Part` opening
- at least two `Chapter` openings
- a continuous body-text spread
- a references/back-matter page

## Success Criteria

The refinement is successful when:

- `Part` and `Chapter` titles appear as Chinese-primary, English-secondary bilingual units
- the TOC reflects that same bilingual hierarchy cleanly
- opening pages feel closer to the original book's editorial rhythm
- body text is more comfortable and elegant to read in Chinese
- page furniture stays quiet and does not interfere with reading
- the output still renders automatically from an existing workspace with no manual intervention
