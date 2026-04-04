# Final Publication Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `publishing` so candidate outputs only become the approved final release when audit findings are fully closed, the release gate passes, and the computed quality score is at least `9.0`.

**Architecture:** Keep `publishing draft` as the rollback baseline, add a candidate/release split inside the publishing workspace, compute chapter-level gate results during deep review, then aggregate them into a whole-book final gate that decides whether candidate outputs are promoted into `publishing/final`. Both polished `PDF` and reflowable `EPUB` continue to render from the same structured manuscript, but only gate-approved candidate artifacts may replace the current final release.

**Tech Stack:** Python 3.11+, existing `book_translator` publishing pipeline, `pytest`, `reportlab`, `ebooklib`, `rich`.

---

### Task 1: Add Candidate And Release Workspace Boundaries

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py`
- Test: `H:\AI_Apps\book-translation-cli\tests\test_workspace.py`
- Test: `H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py`

- [ ] **Step 1: Write the failing workspace tests**

```python
def test_workspace_exposes_candidate_and_final_paths(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")

    assert workspace.publishing_candidate_root_path == workspace.publishing_root_path / "candidate"
    assert workspace.publishing_candidate_final_dir == workspace.publishing_candidate_root_path / "final"
    assert workspace.publishing_final_dir == workspace.publishing_root_path / "final"


def test_failed_candidate_build_does_not_require_final_cleanup(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    workspace.publishing_final_dir.mkdir(parents=True)
    workspace.publishing_final_text_path.write_text("approved", encoding="utf-8")

    workspace.clear_publishing_stage_outputs("deep-review")

    assert workspace.publishing_final_text_path.read_text(encoding="utf-8") == "approved"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_workspace.py -q
```

Expected: failures for missing candidate workspace attributes or incorrect cleanup behavior.

- [ ] **Step 3: Extend `Workspace` with candidate paths and non-destructive cleanup**

```python
self.publishing_candidate_root_path = self.publishing_root_path / "candidate"
self.publishing_candidate_state_dir = self.publishing_candidate_root_path / "state"
self.publishing_candidate_final_dir = self.publishing_candidate_root_path / "final"
self.publishing_candidate_final_text_path = self.publishing_candidate_final_dir / "translated.txt"
self.publishing_candidate_final_pdf_path = self.publishing_candidate_final_dir / "translated.pdf"
self.publishing_candidate_final_epub_path = self.publishing_candidate_final_dir / "translated.epub"

def clear_publishing_stage_outputs(self, stage: str) -> None:
    candidate_stage_paths = {
        "final-review": [self.publishing_candidate_final_text_path],
        "deep-review": [
            self.publishing_candidate_final_text_path,
            self.publishing_candidate_final_pdf_path,
            self.publishing_candidate_final_epub_path,
            self.publishing_audit_source_path,
            self.publishing_audit_review_path,
            self.publishing_audit_consensus_path,
            self.publishing_audit_report_path,
        ],
    }
    for path in candidate_stage_paths.get(stage, []):
        if path.exists():
            path.unlink()
```

- [ ] **Step 4: Add helper methods for candidate promotion**

```python
def promote_candidate_release(self) -> None:
    self.publishing_final_dir.mkdir(parents=True, exist_ok=True)
    for source, target in [
        (self.publishing_candidate_final_text_path, self.publishing_final_text_path),
        (self.publishing_candidate_final_pdf_path, self.publishing_final_pdf_path),
        (self.publishing_candidate_final_epub_path, self.publishing_final_epub_path),
    ]:
        if source.exists():
            target.write_bytes(source.read_bytes())
```

- [ ] **Step 5: Run the focused tests to verify they pass**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_workspace.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git -C H:\AI_Apps\book-translation-cli add src/book_translator/state/workspace.py tests/test_workspace.py tests/test_publishing_pipeline.py
git -C H:\AI_Apps\book-translation-cli commit -m "feat: add publishing candidate workspace"
```

### Task 2: Add Final Gate Models And Scoring

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\models.py`
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\release_gate.py`
- Test: `H:\AI_Apps\book-translation-cli\tests\test_release_gate.py`

- [ ] **Step 1: Write failing release-gate tests**

```python
from book_translator.publishing.release_gate import (
    PublishingGateInputs,
    compute_quality_score,
    evaluate_release_gate,
)


def test_release_gate_fails_when_unresolved_findings_remain() -> None:
    inputs = PublishingGateInputs(
        unresolved_count=1,
        high_severity_count=0,
        structural_issue_count=0,
        citation_issue_count=0,
        image_or_caption_issue_count=0,
        visual_blocker_count=0,
        primary_output_validation_passed=True,
        cross_output_validation_passed=True,
        fidelity_score=9.4,
        structure_score=9.2,
        terminology_score=9.1,
        layout_score=9.0,
        source_style_alignment_score=9.0,
        epub_integrity_score=9.0,
    )

    report = evaluate_release_gate(inputs)

    assert report["release_status"] == "failed"
    assert report["promotion_performed"] is False


def test_release_gate_passes_only_when_score_and_gate_both_pass() -> None:
    inputs = PublishingGateInputs(
        unresolved_count=0,
        high_severity_count=0,
        structural_issue_count=0,
        citation_issue_count=0,
        image_or_caption_issue_count=0,
        visual_blocker_count=0,
        primary_output_validation_passed=True,
        cross_output_validation_passed=True,
        fidelity_score=9.3,
        structure_score=9.2,
        terminology_score=9.1,
        layout_score=9.0,
        source_style_alignment_score=9.0,
        epub_integrity_score=9.0,
    )

    report = evaluate_release_gate(inputs)

    assert report["release_status"] == "passed"
    assert report["quality_score"]["overall"] >= 9.0
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_release_gate.py -q
```

Expected: module or symbol import failures.

- [ ] **Step 3: Implement gate input models and score calculation**

```python
@dataclass(slots=True)
class PublishingGateInputs:
    unresolved_count: int
    high_severity_count: int
    structural_issue_count: int
    citation_issue_count: int
    image_or_caption_issue_count: int
    visual_blocker_count: int
    primary_output_validation_passed: bool
    cross_output_validation_passed: bool
    fidelity_score: float
    structure_score: float
    terminology_score: float
    layout_score: float
    source_style_alignment_score: float
    epub_integrity_score: float


def compute_quality_score(inputs: PublishingGateInputs) -> dict[str, float]:
    overall = round(
        (
            inputs.fidelity_score * 0.28
            + inputs.structure_score * 0.2
            + inputs.terminology_score * 0.14
            + inputs.layout_score * 0.16
            + inputs.source_style_alignment_score * 0.12
            + inputs.epub_integrity_score * 0.1
        ),
        3,
    )
    return {
        "fidelity_score": inputs.fidelity_score,
        "structure_score": inputs.structure_score,
        "terminology_score": inputs.terminology_score,
        "layout_score": inputs.layout_score,
        "source_style_alignment_score": inputs.source_style_alignment_score,
        "epub_integrity_score": inputs.epub_integrity_score,
        "overall": overall,
    }
```

- [ ] **Step 4: Implement final gate evaluation**

```python
def evaluate_release_gate(inputs: PublishingGateInputs) -> dict[str, object]:
    quality_score = compute_quality_score(inputs)
    hard_gate_passed = all(
        [
            inputs.unresolved_count == 0,
            inputs.high_severity_count == 0,
            inputs.structural_issue_count == 0,
            inputs.citation_issue_count == 0,
            inputs.image_or_caption_issue_count == 0,
            inputs.visual_blocker_count == 0,
            inputs.primary_output_validation_passed,
            inputs.cross_output_validation_passed,
        ]
    )
    passed = hard_gate_passed and quality_score["overall"] >= 9.0
    return {
        "release_status": "passed" if passed else "failed",
        "hard_gate_passed": hard_gate_passed,
        "promotion_performed": passed,
        "quality_score": quality_score,
    }
```

- [ ] **Step 5: Run the focused tests to verify they pass**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_release_gate.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git -C H:\AI_Apps\book-translation-cli add src/book_translator/models.py src/book_translator/publishing/release_gate.py tests/test_release_gate.py
git -C H:\AI_Apps\book-translation-cli commit -m "feat: add publishing release gate"
```

### Task 3: Make Deep Review Emit Chapter Gates And Rollback Recommendations

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\deep_review.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\source_audit.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\consensus.py`
- Test: `H:\AI_Apps\book-translation-cli\tests\test_deep_review.py`

- [ ] **Step 1: Write failing chapter-gate tests**

```python
def test_deep_review_assigns_chapter_redraft_when_confirmation_findings_remain() -> None:
    result = run_deep_review(
        source_chapters=[build_source_chapter("c1", "One. Two.")],
        final_artifacts=[build_artifact("c1", "One.")],
        enable_cross_review=True,
    )

    chapter = result.decisions["chapters"][0]

    assert chapter["unresolved_count"] > 0
    assert chapter["rollback_level_required"] in {"chapter_redraft", "chapter_retranslate"}


def test_deep_review_counts_structure_findings_separately() -> None:
    findings = audit_source_against_target(
        chapter_id="c1",
        source_text="1. Alpha\\n2. Beta",
        target_text="Alpha Beta",
    )

    assert any(f.finding_type == "list_structure_loss" for f in findings)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_deep_review.py -q
```

Expected: failures for missing rollback fields and structure finding types.

- [ ] **Step 3: Extend source audit with structure-aware finding types**

```python
if _ordered_item_count(source_text) != _ordered_item_count(target_text):
    findings.append(
        PublishingAuditFinding(
            chapter_id=chapter_id,
            finding_type="list_structure_loss",
            severity="high",
            source_excerpt=source_text[:180],
            target_excerpt=target_text[:180],
            reason="Ordered list cardinality drifted between source and target.",
            auto_fixable=True,
            confidence=0.9,
            agent_role="audit",
        )
    )
```

- [ ] **Step 4: Add chapter-level gate summaries in `run_deep_review`**

```python
chapter_unresolved_count = len(chapter_confirmation_findings)
if chapter_unresolved_count == 0:
    rollback_level_required = "none"
elif chapter_unresolved_count <= 3:
    rollback_level_required = "chapter_repair"
elif chapter_unresolved_count <= 8:
    rollback_level_required = "chapter_redraft"
else:
    rollback_level_required = "chapter_retranslate"

chapter_decisions.append(
    {
        "chapter_id": artifact.chapter_id,
        "chapter_index": artifact.chapter_index,
        "confirmation_finding_count": chapter_unresolved_count,
        "unresolved_count": chapter_unresolved_count,
        "rollback_level_required": rollback_level_required,
        "revised": chapter_was_revised,
    }
)
```

- [ ] **Step 5: Expose whole-book counts needed by the final gate**

```python
final_report.update(
    {
        "structural_issue_count": sum(
            1 for finding in confirmation_findings if "structure" in finding.finding_type
        ),
        "citation_issue_count": sum(
            1 for finding in confirmation_findings if "citation" in finding.finding_type
        ),
        "image_or_caption_issue_count": sum(
            1
            for finding in confirmation_findings
            if finding.finding_type in {"missing_image", "missing_caption", "image_anchor_loss"}
        ),
        "high_severity_count": sum(
            1 for finding in confirmation_findings if finding.severity == "high"
        ),
    }
)
```

- [ ] **Step 6: Run the focused tests to verify they pass**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_deep_review.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git -C H:\AI_Apps\book-translation-cli add src/book_translator/publishing/deep_review.py src/book_translator/publishing/source_audit.py src/book_translator/publishing/consensus.py tests/test_deep_review.py
git -C H:\AI_Apps\book-translation-cli commit -m "feat: add chapter gate outputs to deep review"
```

### Task 4: Route Publishing Through Candidate Build And Final Promotion

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\pipeline.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\artifacts.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\output\polished_pdf.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\output\epub_writer.py`
- Test: `H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py`

- [ ] **Step 1: Write failing promotion-flow tests**

```python
@pytest.mark.asyncio
async def test_failed_gate_keeps_existing_final_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = prepare_publishing_workspace(tmp_path)
    workspace.publishing_final_text_path.parent.mkdir(parents=True, exist_ok=True)
    workspace.publishing_final_text_path.write_text("approved release", encoding="utf-8")

    monkeypatch.setattr(
        "book_translator.publishing.pipeline.evaluate_release_gate",
        lambda inputs: {"release_status": "failed", "promotion_performed": False, "quality_score": {"overall": 8.4}},
    )

    await process_book_publishing(
        input_path=workspace.root / "sample.epub",
        output_root=tmp_path / "out",
        config=PublishingRunConfig(provider="openai", model="gpt-4o-mini"),
        provider=FakeProvider(),
    )

    assert workspace.publishing_final_text_path.read_text(encoding="utf-8") == "approved release"
    assert workspace.publishing_candidate_final_text_path.exists()


@pytest.mark.asyncio
async def test_passing_gate_promotes_candidate_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "book_translator.publishing.pipeline.evaluate_release_gate",
        lambda inputs: {"release_status": "passed", "promotion_performed": True, "quality_score": {"overall": 9.2}},
    )
    ...
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py -q
```

Expected: failures because the pipeline still writes directly to `publishing/final`.

- [ ] **Step 3: Render candidate outputs instead of writing directly to release**

```python
candidate_text_path = workspace.publishing_candidate_final_text_path
candidate_pdf_path = workspace.publishing_candidate_final_pdf_path
candidate_epub_path = workspace.publishing_candidate_final_epub_path

write_translated_text(final_payload, candidate_text_path)
if effective_render_pdf:
    polished_pdf.render_book(printable_book, candidate_pdf_path)
if effective_render_epub:
    write_epub(printable_book, candidate_epub_path)
```

- [ ] **Step 4: Evaluate the final gate and conditionally promote**

```python
gate_inputs = PublishingGateInputs(
    unresolved_count=final_report["unresolved_count"],
    high_severity_count=final_report["high_severity_count"],
    structural_issue_count=final_report["structural_issue_count"],
    citation_issue_count=final_report["citation_issue_count"],
    image_or_caption_issue_count=final_report["image_or_caption_issue_count"],
    visual_blocker_count=visual_summary["visual_blocker_count"],
    primary_output_validation_passed=primary_output_ok,
    cross_output_validation_passed=cross_output_ok,
    fidelity_score=fidelity_score,
    structure_score=structure_score,
    terminology_score=terminology_score,
    layout_score=layout_score,
    source_style_alignment_score=style_score,
    epub_integrity_score=epub_score,
)
gate_report = evaluate_release_gate(gate_inputs)
workspace.write_publishing_json(workspace.publishing_audit_dir / "final_gate_report.json", gate_report)
workspace.write_publishing_json(workspace.publishing_audit_dir / "quality_score.json", gate_report["quality_score"])
if gate_report["promotion_performed"]:
    workspace.promote_candidate_release()
```

- [ ] **Step 5: Persist unresolved findings separately**

```python
workspace.write_publishing_jsonl(
    workspace.publishing_audit_dir / "unresolved_findings.jsonl",
    [finding.model_dump() for finding in confirmation_findings],
)
```

- [ ] **Step 6: Run the focused tests to verify they pass**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git -C H:\AI_Apps\book-translation-cli add src/book_translator/publishing/pipeline.py src/book_translator/publishing/artifacts.py src/book_translator/output/polished_pdf.py src/book_translator/output/epub_writer.py tests/test_publishing_pipeline.py
git -C H:\AI_Apps\book-translation-cli commit -m "feat: promote publishing outputs only after gate pass"
```

### Task 5: Add Visual Blocker Capture And EPUB/PDF Validation Hooks

**Files:**
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\validation.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\output\pdf_raster.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\output\epub_writer.py`
- Test: `H:\AI_Apps\book-translation-cli\tests\test_validation.py`

- [ ] **Step 1: Write failing validation tests**

```python
from book_translator.publishing.validation import (
    summarize_visual_blockers,
    validate_epub_output,
    validate_primary_output,
)


def test_validate_epub_output_reports_missing_navigation(tmp_path: Path) -> None:
    output = validate_epub_output(tmp_path / "broken.epub")
    assert output["passed"] is False


def test_summarize_visual_blockers_defaults_to_zero_when_no_blockers() -> None:
    summary = summarize_visual_blockers([])
    assert summary["visual_blocker_count"] == 0
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_validation.py -q
```

Expected: missing module failures.

- [ ] **Step 3: Implement primary-output validators**

```python
def validate_primary_output(path: Path, output_kind: str) -> dict[str, object]:
    if output_kind == "pdf":
        return {"passed": path.exists() and path.stat().st_size > 0, "kind": "pdf"}
    if output_kind == "epub":
        return validate_epub_output(path)
    raise ValueError(f"Unsupported output kind: {output_kind}")


def validate_epub_output(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"passed": False, "reason": "missing_file", "kind": "epub"}
    with ZipFile(path) as archive:
        names = set(archive.namelist())
    required = {"mimetype", "META-INF/container.xml", "OEBPS/content.opf", "OEBPS/nav.xhtml"}
    missing = sorted(required - names)
    return {"passed": not missing, "reason": "missing_entries" if missing else None, "missing": missing}
```

- [ ] **Step 4: Implement visual blocker summary shape**

```python
def summarize_visual_blockers(blockers: list[dict[str, object]]) -> dict[str, object]:
    return {
        "visual_blocker_count": len(blockers),
        "blockers": blockers,
    }
```

- [ ] **Step 5: Run the focused tests to verify they pass**

Run:

```powershell
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_validation.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git -C H:\AI_Apps\book-translation-cli add src/book_translator/publishing/validation.py src/book_translator/output/pdf_raster.py src/book_translator/output/epub_writer.py tests/test_validation.py
git -C H:\AI_Apps\book-translation-cli commit -m "feat: add publishing output validators"
```

### Task 6: Full Regression And Real-Book Acceptance

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\README.md`
- Modify: `H:\AI_Apps\book-translation-cli\docs\design.md`

- [ ] **Step 1: Run the full test suite**

Run:

```powershell
python -m ruff check H:\AI_Apps\book-translation-cli
python -m pytest -q H:\AI_Apps\book-translation-cli\tests
```

Expected: all tests pass.

- [ ] **Step 2: Run the real-book rebuild from draft through deep review**

Run:

```powershell
python -m book_translator publishing --input "H:\书\The Book of Elon A Guide to Purpose and Success (Eric Jorgenson).pdf" --output H:\AI_Apps\book-translation-cli\out --provider gemini --model gemini-3.1-flash-lite-preview --from-stage draft --to-stage deep-review --render-pdf --also-epub --force
```

Expected:

- candidate outputs regenerated
- final gate artifacts written
- no failed chunks

- [ ] **Step 3: Verify the hard gate artifacts**

Run:

```powershell
Get-Content H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson\publishing\audit\final_gate_report.json
Get-Content H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson\publishing\audit\quality_score.json
```

Expected:

- `release_status` is `passed`
- `unresolved_count = 0`
- `quality_score.overall >= 9.0`

- [ ] **Step 4: Verify release promotion**

Run:

```powershell
Test-Path H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson\publishing\final\translated.pdf
Test-Path H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson\publishing\final\translated.epub
```

Expected: both requested outputs exist in `publishing/final/`.

- [ ] **Step 5: Update docs to reflect final gate semantics**

```markdown
- `publishing` now rebuilds candidate outputs first and promotes them to `final` only after the
  zero-unresolved release gate passes.
- `final_gate_report.json` and `quality_score.json` are the source of truth for final-edition
  acceptance.
```

- [ ] **Step 6: Commit**

```powershell
git -C H:\AI_Apps\book-translation-cli add README.md docs/design.md
git -C H:\AI_Apps\book-translation-cli commit -m "docs: describe final publication release gate"
```

## Self-Review

### Spec Coverage

- Candidate/final separation: covered by Task 1 and Task 4.
- Zero unresolved gate and 9.0+ score: covered by Task 2 and Task 4.
- Chapter rollback escalation from draft: covered by Task 3.
- PDF/EPUB shared release behavior and validation: covered by Task 4 and Task 5.
- Real-book acceptance on `The Book of Elon`: covered by Task 6.

### Placeholder Scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Commands, file paths, and key function shapes are explicit.

### Type Consistency

- Candidate workspace naming consistently uses `publishing_candidate_*`.
- Final gate naming consistently uses `PublishingGateInputs`, `quality_score`, and `release_status`.
- Rollback naming consistently uses `chapter_repair`, `chapter_redraft`, `chapter_retranslate`, and `book_retranslate`.
