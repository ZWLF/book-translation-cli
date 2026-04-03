# Source-Aware Publishing Deep Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a source-aware deep-review stage to `publishing`, then rerun `The Book of Elon: A Guide to Purpose and Success` so the final Chinese manuscript and PDF are rechecked for omissions, structural drift, and layout weaknesses against the English source.

**Architecture:** Extend the existing publishing pipeline with a new `deep-review` stage after `final-review`. The stage will compare source chapters and current publishing chapters, emit structured findings, apply bounded editorial repairs plus layout annotations, and then rebuild the stable `publishing/final/translated.txt` and `publishing/final/translated.pdf` outputs from the corrected artifacts.

**Tech Stack:** Python 3.11+, Pydantic, Typer, ReportLab, PyMuPDF, pytest, ruff.

---

## File Map

- Modify: `src/book_translator/config.py`
  - Add `deep-review` to publishing stage definitions and stage-window validation.
- Modify: `src/book_translator/models.py`
  - Add structured models for deep-review findings and layout annotations.
- Modify: `src/book_translator/state/workspace.py`
  - Add `publishing/deep_review/*` artifact paths and invalidation cleanup.
- Create: `src/book_translator/publishing/source_audit.py`
  - Compare source chapter text and publishing final chapter text; emit structured findings.
- Create: `src/book_translator/publishing/editorial_revision.py`
  - Apply bounded text repairs for omission-sensitive and structure-sensitive findings.
- Create: `src/book_translator/publishing/layout_review.py`
  - Convert findings and repaired text into renderer-facing structural annotations.
- Create: `src/book_translator/publishing/deep_review.py`
  - Orchestrate source audit, editorial repair, annotation generation, artifact persistence, and final output rebuild.
- Modify: `src/book_translator/publishing/pipeline.py`
  - Insert `deep-review` after `final-review`, update stage fingerprints, invalidation, summary counts, and PDF rebuild path.
- Modify: `src/book_translator/output/polished_pdf.py`
  - Consume deep-review annotations for callouts, Q&A blocks, list-heavy passages, and citation-sensitive paragraphs.
- Modify: `src/book_translator/output/assembler.py`
  - Assemble publishing text from deep-review artifacts when present.
- Modify: `src/book_translator/cli.py`
  - Expose `deep-review` as a valid `--from-stage` / `--to-stage` choice without changing the top-level command shape.
- Create: `tests/test_publishing_source_audit.py`
  - Cover omission, collapsed lists, weak callout detection, and Q&A structure findings.
- Create: `tests/test_publishing_deep_review.py`
  - Cover bounded editorial repairs, annotation generation, and deep-review artifact output.
- Modify: `tests/test_publishing_config.py`
  - Cover new stage ordering and stage-window validation.
- Modify: `tests/test_publishing_workspace.py`
  - Cover deep-review paths and cleanup behavior.
- Modify: `tests/test_publishing_pipeline.py`
  - Cover pipeline integration through `deep-review` and summary/artifact behavior.
- Modify: `tests/test_polished_pdf.py`
  - Cover renderer handling of deep-review structural annotations.
- Modify: `README.md`
  - Document the new deep-review stage and the recommended end-to-end publishing command.

### Task 1: Add Deep-Review Stage Plumbing

**Files:**
- Modify: `src/book_translator/config.py`
- Modify: `src/book_translator/models.py`
- Modify: `src/book_translator/state/workspace.py`
- Test: `tests/test_publishing_config.py`
- Test: `tests/test_publishing_workspace.py`

- [ ] **Step 1: Write the failing config and workspace tests**

```python
def test_publishing_stage_window_accepts_deep_review() -> None:
    config = PublishingRunConfig(from_stage="proofread", to_stage="deep-review")
    assert config.to_stage == "deep-review"


def test_workspace_exposes_deep_review_artifact_paths(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    assert workspace.publishing_deep_review_dir.name == "deep_review"
    assert workspace.publishing_deep_review_findings_path.name == "findings.jsonl"
    assert workspace.publishing_deep_review_chapters_path.name == "revised_chapters.jsonl"
```

- [ ] **Step 2: Run the tests to verify they fail for the right reason**

Run:

```bash
python -m pytest tests/test_publishing_config.py tests/test_publishing_workspace.py -q
```

Expected:

- fail because `deep-review` is not yet a valid publishing stage
- fail because `Workspace` does not yet expose deep-review paths

- [ ] **Step 3: Implement the minimum stage/model/workspace changes**

```python
PUBLISHING_STAGES = (
    "draft",
    "lexicon",
    "revision",
    "proofread",
    "final-review",
    "deep-review",
)


class PublishingRunConfig(RunConfig):
    from_stage: Literal["draft", "lexicon", "revision", "proofread", "final-review", "deep-review"]
    to_stage: Literal["draft", "lexicon", "revision", "proofread", "final-review", "deep-review"]


class PublishingAuditFinding(BaseModel):
    chapter_id: str
    finding_type: str
    severity: str
    source_excerpt: str
    target_excerpt: str
    reason: str
    auto_fixable: bool = False


class PublishingLayoutAnnotation(BaseModel):
    kind: str
    payload: dict[str, str | int | bool] = Field(default_factory=dict)
```

```python
self.publishing_deep_review_dir = self.publishing_root_path / "deep_review"
self.publishing_deep_review_findings_path = self.publishing_deep_review_dir / "findings.jsonl"
self.publishing_deep_review_chapters_path = self.publishing_deep_review_dir / "revised_chapters.jsonl"
self.publishing_deep_review_decisions_path = self.publishing_deep_review_dir / "decisions.json"
```

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
python -m pytest tests/test_publishing_config.py tests/test_publishing_workspace.py -q
```

Expected:

- all targeted tests pass

- [ ] **Step 5: Commit the plumbing**

```bash
git add src/book_translator/config.py src/book_translator/models.py src/book_translator/state/workspace.py tests/test_publishing_config.py tests/test_publishing_workspace.py
git commit -m "Add publishing deep-review stage plumbing"
```

### Task 2: Build Source-Audit Detection

**Files:**
- Create: `src/book_translator/publishing/source_audit.py`
- Test: `tests/test_publishing_source_audit.py`

- [ ] **Step 1: Write the failing source-audit tests**

```python
def test_audit_detects_collapsed_numbered_list() -> None:
    findings = audit_source_against_target(
        chapter_id="c1",
        source_text="1. First idea.\n2. Second idea.\n3. Third idea.",
        target_text="第一条。 2. 第二条。 3. 第三条。",
    )
    assert any(item.finding_type == "collapsed_numbered_list" for item in findings)


def test_audit_detects_possible_omission_when_source_item_missing() -> None:
    findings = audit_source_against_target(
        chapter_id="c2",
        source_text="Alpha.\nBeta.\nGamma.",
        target_text="阿尔法。\n伽马。",
    )
    assert any(item.finding_type == "possible_omission" for item in findings)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
python -m pytest tests/test_publishing_source_audit.py -q
```

Expected:

- fail because `audit_source_against_target()` does not exist yet

- [ ] **Step 3: Implement deterministic audit heuristics first**

```python
def audit_source_against_target(*, chapter_id: str, source_text: str, target_text: str) -> list[PublishingAuditFinding]:
    findings: list[PublishingAuditFinding] = []
    if _looks_like_flattened_numbered_list(source_text, target_text):
        findings.append(
            PublishingAuditFinding(
                chapter_id=chapter_id,
                finding_type="collapsed_numbered_list",
                severity="high",
                source_excerpt=_excerpt(source_text),
                target_excerpt=_excerpt(target_text),
                reason="Ordered list markers in source are not preserved as block items in target.",
                auto_fixable=True,
            )
        )
    findings.extend(_detect_possible_omissions(chapter_id=chapter_id, source_text=source_text, target_text=target_text))
    findings.extend(_detect_callout_candidates(chapter_id=chapter_id, source_text=source_text, target_text=target_text))
    findings.extend(_detect_question_answer_structure(chapter_id=chapter_id, source_text=source_text, target_text=target_text))
    return findings
```

- [ ] **Step 4: Re-run the audit tests**

Run:

```bash
python -m pytest tests/test_publishing_source_audit.py -q
```

Expected:

- all source-audit tests pass

- [ ] **Step 5: Commit the source-audit module**

```bash
git add src/book_translator/publishing/source_audit.py tests/test_publishing_source_audit.py
git commit -m "Add source-aware publishing audit heuristics"
```

### Task 3: Apply Editorial Repairs and Layout Annotations

**Files:**
- Create: `src/book_translator/publishing/editorial_revision.py`
- Create: `src/book_translator/publishing/layout_review.py`
- Modify: `src/book_translator/models.py`
- Test: `tests/test_publishing_deep_review.py`

- [ ] **Step 1: Write the failing repair and annotation tests**

```python
def test_apply_editorial_repairs_restores_numbered_items() -> None:
    findings = [
        PublishingAuditFinding(
            chapter_id="c1",
            finding_type="collapsed_numbered_list",
            severity="high",
            source_excerpt="1. One.\n2. Two.\n3. Three.",
            target_excerpt="一。 2. 二。 3. 三。",
            reason="list collapsed",
            auto_fixable=True,
        )
    ]
    repaired = apply_editorial_repairs(
        chapter_text="一。 2. 二。 3. 三。",
        source_text="1. One.\n2. Two.\n3. Three.",
        findings=findings,
    )
    assert "\n1. " in repaired or "\n1．" in repaired


def test_generate_layout_annotations_marks_callout_blocks() -> None:
    annotations = generate_layout_annotations(
        source_text="Life is too short for long-term grudges.",
        chapter_text="人生苦短，不值得长期记恨。",
        findings=[
            PublishingAuditFinding(
                chapter_id="c1",
                finding_type="callout_candidate",
                severity="medium",
                source_excerpt="Life is too short for long-term grudges.",
                target_excerpt="人生苦短，不值得长期记恨。",
                reason="short emphasized quotation",
                auto_fixable=True,
            )
        ],
    )
    assert any(item.kind == "callout" for item in annotations)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest tests/test_publishing_deep_review.py -q
```

Expected:

- fail because editorial-repair and layout-review helpers do not exist yet

- [ ] **Step 3: Implement bounded repair and annotation logic**

```python
def apply_editorial_repairs(*, chapter_text: str, source_text: str, findings: list[PublishingAuditFinding]) -> str:
    revised = chapter_text
    for finding in findings:
        if finding.finding_type == "collapsed_numbered_list" and finding.auto_fixable:
            revised = restore_numbered_list_blocks(revised, source_text)
        if finding.finding_type == "possible_omission" and finding.auto_fixable:
            revised = restore_missing_span(revised, source_text, finding)
    return normalize_editorial_spacing(revised)
```

```python
def generate_layout_annotations(*, source_text: str, chapter_text: str, findings: list[PublishingAuditFinding]) -> list[PublishingLayoutAnnotation]:
    annotations: list[PublishingLayoutAnnotation] = []
    for finding in findings:
        if finding.finding_type == "callout_candidate":
            annotations.append(PublishingLayoutAnnotation(kind="callout", payload={"text": finding.target_excerpt}))
        if finding.finding_type == "question_answer_structure":
            annotations.append(PublishingLayoutAnnotation(kind="qa_block", payload={"anchor": finding.target_excerpt}))
    return annotations
```

- [ ] **Step 4: Re-run the targeted deep-review tests**

Run:

```bash
python -m pytest tests/test_publishing_deep_review.py -q
```

Expected:

- all repair and annotation tests pass

- [ ] **Step 5: Commit the repair and annotation layer**

```bash
git add src/book_translator/publishing/editorial_revision.py src/book_translator/publishing/layout_review.py src/book_translator/models.py tests/test_publishing_deep_review.py
git commit -m "Add publishing editorial repair and layout annotation logic"
```

### Task 4: Integrate Deep Review Into the Publishing Pipeline

**Files:**
- Create: `src/book_translator/publishing/deep_review.py`
- Modify: `src/book_translator/publishing/pipeline.py`
- Modify: `src/book_translator/output/assembler.py`
- Test: `tests/test_publishing_pipeline.py`

- [ ] **Step 1: Write the failing pipeline integration tests**

```python
def test_publishing_pipeline_runs_through_deep_review(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    # arrange synthetic final-review artifacts here
    summary = run_publishing_pipeline_for_test(workspace=workspace, from_stage="final-review", to_stage="deep-review")
    assert summary["completed_stage"] == "deep-review"
    assert workspace.publishing_deep_review_findings_path.exists()
    assert workspace.publishing_final_text_path.exists()
```

- [ ] **Step 2: Run the pipeline test to verify it fails**

Run:

```bash
python -m pytest tests/test_publishing_pipeline.py -q -k "deep_review"
```

Expected:

- fail because `deep-review` is not yet wired into the pipeline

- [ ] **Step 3: Implement the stage orchestrator and pipeline hook**

```python
def run_deep_review_stage(*, source_chapters: list[Chapter], final_artifacts: list[PublishingChapterArtifact]) -> DeepReviewResult:
    findings = build_deep_review_findings(source_chapters=source_chapters, final_artifacts=final_artifacts)
    revised_artifacts = []
    for source_chapter, final_artifact in zip(source_chapters, final_artifacts, strict=False):
        chapter_findings = [item for item in findings if item.chapter_id == final_artifact.chapter_id]
        revised_text = apply_editorial_repairs(
            chapter_text=final_artifact.text,
            source_text=source_chapter.text,
            findings=chapter_findings,
        )
        annotations = generate_layout_annotations(
            source_text=source_chapter.text,
            chapter_text=revised_text,
            findings=chapter_findings,
        )
        revised_artifacts.append(final_artifact.model_copy(update={"text": revised_text, "layout_annotations": annotations}))
    return DeepReviewResult(findings=findings, chapters=revised_artifacts)
```

- [ ] **Step 4: Re-run the pipeline integration test**

Run:

```bash
python -m pytest tests/test_publishing_pipeline.py -q -k "deep_review"
```

Expected:

- the targeted pipeline test passes

- [ ] **Step 5: Commit the pipeline integration**

```bash
git add src/book_translator/publishing/deep_review.py src/book_translator/publishing/pipeline.py src/book_translator/output/assembler.py tests/test_publishing_pipeline.py
git commit -m "Integrate deep-review into publishing pipeline"
```

### Task 5: Teach the PDF Renderer to Use Deep-Review Structure

**Files:**
- Modify: `src/book_translator/output/polished_pdf.py`
- Test: `tests/test_polished_pdf.py`

- [ ] **Step 1: Write the failing renderer regression tests**

```python
def test_renderer_uses_callout_annotation_for_short_quote() -> None:
    chapter = PublishingChapterArtifact(
        chapter_id="c1",
        chapter_index=0,
        title="A Chapter",
        text="人生苦短，不值得长期记恨。",
        layout_annotations=[PublishingLayoutAnnotation(kind="callout", payload={"text": "人生苦短，不值得长期记恨。"})],
    )
    book = build_printable_book_from_artifacts(...)
    assert any(block.kind == "callout" for block in book.chapters[0].blocks)
```

- [ ] **Step 2: Run the renderer tests to verify they fail**

Run:

```bash
python -m pytest tests/test_polished_pdf.py -q -k "callout_annotation or qa_block"
```

Expected:

- fail because renderer ignores deep-review annotations

- [ ] **Step 3: Implement annotation-aware printable blocks**

```python
for annotation in artifact.layout_annotations:
    if annotation.kind == "callout":
        blocks.append(PrintableBlock(kind="callout", text=str(annotation.payload["text"])))
    elif annotation.kind == "qa_block":
        blocks.extend(_build_qa_blocks(annotation.payload, artifact.text))
```

- [ ] **Step 4: Re-run the targeted renderer tests**

Run:

```bash
python -m pytest tests/test_polished_pdf.py -q -k "callout_annotation or qa_block"
```

Expected:

- targeted renderer tests pass

- [ ] **Step 5: Commit the renderer changes**

```bash
git add src/book_translator/output/polished_pdf.py tests/test_polished_pdf.py
git commit -m "Render deep-review structural annotations in publishing PDF"
```

### Task 6: Document, Verify, and Reprocess the Elon Book

**Files:**
- Modify: `README.md`
- Modify: `tests/test_publishing_pipeline.py`
- Modify: `tests/test_polished_pdf.py`

- [ ] **Step 1: Update docs and add any missing end-to-end regression tests**

```markdown
book-translator publishing \
  --input "./books" \
  --output "./out" \
  --from-stage draft \
  --to-stage deep-review \
  --render-pdf
```

- [ ] **Step 2: Run full repository verification before touching the real book**

Run:

```bash
python -m ruff check .
python -m pytest -q
```

Expected:

- `ruff` passes with no errors
- full test suite passes

- [ ] **Step 3: Reprocess the Elon workspace through deep review**

Run:

```bash
python -m book_translator publishing \
  --input "H:\书\The Book of Elon A Guide to Purpose and Success (Eric Jorgenson).pdf" \
  --output H:\AI_Apps\book-translation-cli\out \
  --provider gemini \
  --model gemini-3.1-flash-lite-preview \
  --from-stage final-review \
  --to-stage deep-review \
  --render-pdf
```

Expected:

- `publishing/deep_review/findings.jsonl` exists
- `publishing/deep_review/revised_chapters.jsonl` exists
- `publishing/final/translated.txt` is rebuilt
- `publishing/final/translated.pdf` is rebuilt

- [ ] **Step 4: Raster QA representative pages and inspect the known weak zones**

Run:

```bash
python -m book_translator qa-pdf --workspace "H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson"
python -m book_translator render-pages \
  --pdf "H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson\publishing\final\translated.pdf" \
  --output-dir "H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson\publishing\qa_deep_review" \
  --pages 1,2,4,145,151,154,278,279
```

Expected:

- front matter still renders correctly
- list-heavy pages are no longer flattened
- callout and inline citation pages keep their styling
- no obvious mixed-script spacing regressions appear on sampled pages

- [ ] **Step 5: Commit the docs and acceptance-sweep updates**

```bash
git add README.md tests/test_publishing_pipeline.py tests/test_polished_pdf.py
git commit -m "Document and verify deep-review publishing workflow"
```

## Self-Review

- Spec coverage:
  - stage addition is covered by Task 1 and Task 4
  - source-aware auditing is covered by Task 2
  - corrective editorial rewrites are covered by Task 3
  - layout-aware PDF refinement is covered by Task 5
  - full-book rerun and acceptance on the Elon title are covered by Task 6
- Placeholder scan:
  - no `TBD` / `TODO` placeholders remain
  - every task includes explicit files, commands, and expected outcomes
- Type consistency:
  - `deep-review` is the canonical stage label throughout
  - new models use `PublishingAuditFinding` and `PublishingLayoutAnnotation` consistently
  - pipeline outputs reference `publishing/deep_review/*` consistently

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-03-source-aware-publishing-deep-review.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

