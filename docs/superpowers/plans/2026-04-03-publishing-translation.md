# Publishing Translation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second `publishing` workflow that produces publication-grade non-fiction Chinese drafts with staged revision, proofreading, whole-book consistency review, and auditable artifacts.

**Architecture:** Keep the current engineering pipeline intact and introduce a separate publishing orchestration layer under `src/book_translator/publishing/`. Reuse extraction, chaptering, chunking, providers, polished PDF, and QA outputs, but isolate publishing state, stage outputs, and CLI entry points so the higher-quality workflow does not pollute engineering mode.

**Tech Stack:** Python, typer, pydantic, httpx, pytest, reportlab, rich

---

## File Structure Map

**Existing files to modify**

- `H:\AI_Apps\book-translation-cli\src\book_translator\cli.py`
  Adds explicit `engineering` and `publishing` command groups while keeping the top-level command as an alias to engineering mode.
- `H:\AI_Apps\book-translation-cli\src\book_translator\config.py`
  Adds publishing-specific configuration and stage controls.
- `H:\AI_Apps\book-translation-cli\src\book_translator\models.py`
  Adds publishing run and artifact models shared across stages.
- `H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py`
  Adds publishing workspace paths, stage fingerprints, and artifact read/write helpers.
- `H:\AI_Apps\book-translation-cli\src\book_translator\output\assembler.py`
  Reused to assemble final text from publishing final chapters.
- `H:\AI_Apps\book-translation-cli\src\book_translator\output\polished_pdf.py`
  Reused to render the publishing final manuscript PDF from stage outputs.
- `H:\AI_Apps\book-translation-cli\README.md`
  Documents the new publishing workflow and artifact layout.

**New files to create**

- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\__init__.py`
- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\style.py`
- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\draft.py`
- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\lexicon.py`
- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\revision.py`
- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\proofread.py`
- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\final_review.py`
- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\artifacts.py`
- `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\pipeline.py`
- `H:\AI_Apps\book-translation-cli\tests\test_publishing_config.py`
- `H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py`
- `H:\AI_Apps\book-translation-cli\tests\test_publishing_style.py`
- `H:\AI_Apps\book-translation-cli\tests\test_publishing_lexicon.py`
- `H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py`

The implementation should keep each publishing stage in its own file. No stage module should directly know about polished PDF internals; only the top-level publishing pipeline should trigger final rendering.

### Task 1: Add command and configuration scaffolding for explicit modes

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\cli.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\config.py`
- Create: `H:\AI_Apps\book-translation-cli\tests\test_publishing_config.py`
- Modify: `H:\AI_Apps\book-translation-cli\tests\test_cli_smoke.py`

- [ ] **Step 1: Write the failing tests**

Add tests that lock these behaviors:

```python
from typer.testing import CliRunner

from book_translator.cli import app
from book_translator.config import PublishingRunConfig


def test_cli_shows_engineering_and_publishing_commands() -> None:
    result = CliRunner().invoke(app, ["--help"], prog_name="book-translator")
    assert result.exit_code == 0
    assert "engineering" in result.stdout
    assert "publishing" in result.stdout


def test_publishing_config_has_stage_controls() -> None:
    config = PublishingRunConfig(provider="gemini", model="gemini-3.1-flash-lite-preview")
    assert config.style == "non-fiction-publishing"
    assert config.from_stage == "draft"
    assert config.to_stage == "final-review"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_cli_smoke.py H:\AI_Apps\book-translation-cli\tests\test_publishing_config.py -q
```

Expected:

- `ImportError` for `PublishingRunConfig`, or
- assertion failures because `engineering` / `publishing` commands do not exist yet

- [ ] **Step 3: Implement the minimal command/config scaffolding**

Add a dedicated publishing config model with stage controls and keep the old config for engineering:

```python
class PublishingRunConfig(RunConfig):
    style: str = "non-fiction-publishing"
    from_stage: str = "draft"
    to_stage: str = "final-review"
    mode: str = "publishing"
    max_concurrency: int = 3
```

Add explicit subcommands in `cli.py`:

```python
engineering_app = typer.Typer(help="Engineering-grade translation workflow.")
publishing_app = typer.Typer(help="Publication-grade non-fiction translation workflow.")
app.add_typer(engineering_app, name="engineering")
app.add_typer(publishing_app, name="publishing")
```

Keep the top-level callback as an alias to engineering mode for Phase 1.

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_cli_smoke.py H:\AI_Apps\book-translation-cli\tests\test_publishing_config.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add H:\AI_Apps\book-translation-cli\src\book_translator\cli.py H:\AI_Apps\book-translation-cli\src\book_translator\config.py H:\AI_Apps\book-translation-cli\tests\test_cli_smoke.py H:\AI_Apps\book-translation-cli\tests\test_publishing_config.py
git commit -m "feat: add publishing command scaffolding"
```

### Task 2: Add publishing workspace paths and artifact models

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\models.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py`
- Create: `H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py`

- [ ] **Step 1: Write the failing tests**

Add tests for publishing workspace structure and stage fingerprint invalidation:

```python
from pathlib import Path

from book_translator.state.workspace import Workspace


def test_workspace_exposes_publishing_paths(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    assert workspace.publishing_root_path == workspace.root / "publishing"
    assert workspace.publishing_draft_text_path == workspace.root / "publishing" / "draft" / "draft.txt"
    assert workspace.publishing_final_pdf_path == workspace.root / "publishing" / "final" / "translated.pdf"


def test_workspace_persists_publishing_stage_state(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    workspace.write_publishing_stage_state("lexicon", {"fingerprint": "abc", "status": "complete"})
    assert workspace.read_publishing_stage_state("lexicon") == {"fingerprint": "abc", "status": "complete"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py -q
```

Expected: FAIL because publishing paths and stage state helpers do not exist

- [ ] **Step 3: Implement the minimal models and workspace helpers**

Add lightweight models for publishing artifacts, for example:

```python
class PublishingStageState(BaseModel):
    stage: str
    fingerprint: str
    status: str


class PublishingChapterArtifact(BaseModel):
    chapter_id: str
    chapter_index: int
    title: str
    text: str
```

Add publishing paths and JSON helpers in `workspace.py`:

```python
self.publishing_root_path = self.root / "publishing"
self.publishing_state_dir = self.publishing_root_path / "state"
self.publishing_draft_text_path = self.publishing_root_path / "draft" / "draft.txt"
self.publishing_final_pdf_path = self.publishing_root_path / "final" / "translated.pdf"
```

and:

```python
def write_publishing_stage_state(self, stage: str, payload: dict[str, object]) -> None: ...
def read_publishing_stage_state(self, stage: str) -> dict[str, object]: ...
```

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add H:\AI_Apps\book-translation-cli\src\book_translator\models.py H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py
git commit -m "feat: add publishing workspace artifacts"
```

### Task 3: Add style rules and draft-stage helpers

**Files:**
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\__init__.py`
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\style.py`
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\draft.py`
- Create: `H:\AI_Apps\book-translation-cli\tests\test_publishing_style.py`

- [ ] **Step 1: Write the failing tests**

Add tests that lock the formal non-fiction style contract and draft request building:

```python
from book_translator.publishing.draft import build_draft_request
from book_translator.publishing.style import get_style_profile


def test_style_profile_is_formal_nonfiction() -> None:
    profile = get_style_profile("non-fiction-publishing")
    assert profile.name == "non-fiction-publishing"
    assert "formal" in profile.voice.lower()
    assert "no internet slang" in " ".join(profile.prohibited_patterns).lower()


def test_build_draft_request_includes_style_and_context() -> None:
    request = build_draft_request(
        book_title="Book",
        chapter_title="Chapter 1",
        chunk_text="Source text",
        style_name="non-fiction-publishing",
    )
    assert "Book" in request.book_title
    assert request.style_name == "non-fiction-publishing"
    assert "Source text" in request.source_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_style.py -q
```

Expected: FAIL because `publishing.style` and `publishing.draft` do not exist

- [ ] **Step 3: Implement minimal style and draft helpers**

Create a structured style profile instead of freeform prompt strings:

```python
class StyleProfile(BaseModel):
    name: str
    voice: str
    sentence_rules: list[str]
    prohibited_patterns: list[str]
```

and:

```python
def get_style_profile(name: str) -> StyleProfile:
    if name != "non-fiction-publishing":
        raise ValueError(...)
    return StyleProfile(
        name=name,
        voice="Formal non-fiction Chinese, restrained and publication-ready.",
        sentence_rules=[...],
        prohibited_patterns=[...],
    )
```

Then define a draft request helper that packages style, chapter metadata, and source text for the first-pass translation stage.

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_style.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add H:\AI_Apps\book-translation-cli\src\book_translator\publishing\__init__.py H:\AI_Apps\book-translation-cli\src\book_translator\publishing\style.py H:\AI_Apps\book-translation-cli\src\book_translator\publishing\draft.py H:\AI_Apps\book-translation-cli\tests\test_publishing_style.py
git commit -m "feat: add publishing style and draft helpers"
```

### Task 4: Add lexicon extraction and merge behavior

**Files:**
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\lexicon.py`
- Create: `H:\AI_Apps\book-translation-cli\tests\test_publishing_lexicon.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py`

- [ ] **Step 1: Write the failing tests**

Add tests for lexicon normalization and user overlay merging:

```python
from book_translator.publishing.lexicon import merge_lexicon_overrides, normalize_lexicon_records


def test_normalize_lexicon_records_deduplicates_terms() -> None:
    records = [
        {"source": "Mars", "translation": "火星"},
        {"source": "Mars", "translation": "火星"},
    ]
    normalized = normalize_lexicon_records(records)
    assert normalized == [{"source": "Mars", "translation": "火星"}]


def test_merge_lexicon_overrides_prefers_user_mapping() -> None:
    generated = {"Tesla": "特斯拉"}
    user_map = {"Tesla": "特斯拉公司"}
    assert merge_lexicon_overrides(generated, user_map) == {"Tesla": "特斯拉公司"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_lexicon.py -q
```

Expected: FAIL because lexicon helpers do not exist

- [ ] **Step 3: Implement minimal lexicon helpers and persistence**

Create focused helpers:

```python
def normalize_lexicon_records(records: list[dict[str, str]]) -> list[dict[str, str]]: ...
def merge_lexicon_overrides(generated: dict[str, str], overrides: dict[str, str]) -> dict[str, str]: ...
```

Add workspace writers for:

```python
publishing/lexicon/glossary.json
publishing/lexicon/names.json
publishing/lexicon/decisions.json
```

Keep extraction deterministic and data-oriented. Do not mix revision logic into this file.

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_lexicon.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add H:\AI_Apps\book-translation-cli\src\book_translator\publishing\lexicon.py H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py H:\AI_Apps\book-translation-cli\tests\test_publishing_lexicon.py
git commit -m "feat: add publishing lexicon helpers"
```

### Task 5: Add revision, proofreading, and final-review stage modules

**Files:**
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\revision.py`
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\proofread.py`
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\final_review.py`
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\artifacts.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\models.py`
- Create: `H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py`

- [ ] **Step 1: Write the failing stage tests**

Add tests that prove each stage returns explicit artifacts rather than raw strings:

```python
from book_translator.publishing.artifacts import PublishingChapterArtifact
from book_translator.publishing.final_review import apply_final_review
from book_translator.publishing.proofread import proofread_chapter
from book_translator.publishing.revision import revise_chapter


def test_revise_chapter_returns_artifact() -> None:
    result = revise_chapter(
        chapter_id="c1",
        title="Chapter 1",
        draft_text="Draft text",
        style_name="non-fiction-publishing",
        glossary={"Mars": "火星"},
        names={},
    )
    assert isinstance(result, PublishingChapterArtifact)


def test_proofread_chapter_returns_notes_and_text() -> None:
    revised = PublishingChapterArtifact(chapter_id="c1", chapter_index=0, title="Chapter 1", text="Revised text")
    final_artifact, notes = proofread_chapter(revised)
    assert final_artifact.text
    assert isinstance(notes, list)


def test_apply_final_review_keeps_chapter_order() -> None:
    artifacts = [
        PublishingChapterArtifact(chapter_id="c2", chapter_index=1, title="B", text="Two"),
        PublishingChapterArtifact(chapter_id="c1", chapter_index=0, title="A", text="One"),
    ]
    reviewed, editorial_log = apply_final_review(artifacts)
    assert [item.chapter_id for item in reviewed] == ["c1", "c2"]
    assert isinstance(editorial_log, list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py -q
```

Expected: FAIL because the stage modules and artifact helpers do not exist

- [ ] **Step 3: Implement minimal stage modules**

Create focused stage functions:

```python
def revise_chapter(...) -> PublishingChapterArtifact: ...
def proofread_chapter(...) -> tuple[PublishingChapterArtifact, list[dict[str, str]]]: ...
def apply_final_review(...) -> tuple[list[PublishingChapterArtifact], list[dict[str, str]]]: ...
```

Use placeholder-safe stage outputs that preserve chapter order and attach note/change structures even when the first implementation still uses simplified LLM behavior. The code should be ready to call providers later but not embed the full pipeline yet.

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add H:\AI_Apps\book-translation-cli\src\book_translator\publishing\revision.py H:\AI_Apps\book-translation-cli\src\book_translator\publishing\proofread.py H:\AI_Apps\book-translation-cli\src\book_translator\publishing\final_review.py H:\AI_Apps\book-translation-cli\src\book_translator\publishing\artifacts.py H:\AI_Apps\book-translation-cli\src\book_translator\models.py H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py
git commit -m "feat: add publishing revision and proofread stages"
```

### Task 6: Add end-to-end publishing pipeline orchestration

**Files:**
- Create: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\pipeline.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\cli.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\output\assembler.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\output\polished_pdf.py`
- Modify: `H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py`
- Modify: `H:\AI_Apps\book-translation-cli\tests\test_pdf_raster.py`

- [ ] **Step 1: Write the failing integration tests**

Extend `test_publishing_pipeline.py` with an end-to-end integration test using a fake provider:

```python
import pytest

from book_translator.config import PublishingRunConfig
from book_translator.publishing.pipeline import process_book_publishing


@pytest.mark.asyncio
async def test_process_book_publishing_writes_stage_artifacts(tmp_path: Path) -> None:
    summary = await process_book_publishing(
        input_path=sample_epub_path,
        output_root=tmp_path / "out",
        config=PublishingRunConfig(provider="openai", model="gpt-4o-mini"),
        provider=fake_provider,
    )
    book_dir = tmp_path / "out" / "sample" / "publishing"
    assert (book_dir / "draft" / "draft.txt").exists()
    assert (book_dir / "lexicon" / "glossary.json").exists()
    assert (book_dir / "final" / "translated.txt").exists()
    assert (book_dir / "final" / "translated.pdf").exists()
    assert (book_dir / "editorial_log.json").exists()
    assert summary["mode"] == "publishing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py -q
```

Expected: FAIL because `process_book_publishing` does not exist and final artifacts are not produced

- [ ] **Step 3: Implement the publishing pipeline**

In `publishing/pipeline.py`, orchestrate:

```python
async def process_book_publishing(*, input_path: Path, output_root: Path, config: PublishingRunConfig, provider: BaseProvider | None = None) -> dict[str, object]:
    ...
```

The minimal sequence must:

- extract book text
- detect chapters
- build draft artifacts
- build lexicon artifacts
- revise chapters
- proofread chapters
- apply final review
- assemble final text
- render the final PDF
- persist `run_summary.json` and `editorial_log.json`

Extend `qa-pdf` so a workspace path pointing at a book root prefers:

- `translated.pdf` for engineering outputs
- `publishing/final/translated.pdf` when the publishing final PDF exists and the engineering PDF is absent

Add a targeted test in `tests/test_pdf_raster.py` that creates a fake publishing workspace and asserts `qa-pdf --workspace <book-root>` writes screenshots under `publishing/qa/pages`.

Wire `book-translator publishing ...` to this function in `cli.py`.

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py H:\AI_Apps\book-translation-cli\tests\test_pdf_raster.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add H:\AI_Apps\book-translation-cli\src\book_translator\publishing\pipeline.py H:\AI_Apps\book-translation-cli\src\book_translator\cli.py H:\AI_Apps\book-translation-cli\src\book_translator\output\assembler.py H:\AI_Apps\book-translation-cli\src\book_translator\output\polished_pdf.py H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py H:\AI_Apps\book-translation-cli\tests\test_pdf_raster.py
git commit -m "feat: add publishing pipeline orchestration"
```

### Task 7: Add stage-aware resume controls and stale-stage invalidation

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\config.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py`
- Modify: `H:\AI_Apps\book-translation-cli\src\book_translator\publishing\pipeline.py`
- Modify: `H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py`
- Modify: `H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Add tests for stage invalidation:

```python
def test_revision_becomes_stale_when_lexicon_fingerprint_changes(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    workspace.write_publishing_stage_state("lexicon", {"fingerprint": "old", "status": "complete"})
    workspace.write_publishing_stage_state("revision", {"fingerprint": "old", "status": "complete"})
    assert workspace.stage_is_stale("revision", upstream_fingerprint="new")


@pytest.mark.asyncio
async def test_from_stage_revision_skips_draft_and_lexicon(tmp_path: Path) -> None:
    ...
    assert summary["started_stage"] == "revision"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py -q
```

Expected: FAIL because stale-stage logic and `from_stage` behavior are not implemented

- [ ] **Step 3: Implement minimal stage invalidation**

Add helpers like:

```python
def stage_is_stale(self, stage: str, upstream_fingerprint: str) -> bool: ...
def clear_publishing_stage_outputs(self, stage: str) -> None: ...
```

In `PublishingRunConfig`, validate `from_stage` and `to_stage` against:

```python
PUBLISHING_STAGES = ["draft", "lexicon", "revision", "proofread", "final-review"]
```

Update the publishing pipeline so each stage checks upstream fingerprints and respects `from_stage` / `to_stage`.

- [ ] **Step 4: Re-run the targeted tests**

Run:

```bash
python -m pytest H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add H:\AI_Apps\book-translation-cli\src\book_translator\config.py H:\AI_Apps\book-translation-cli\src\book_translator\state\workspace.py H:\AI_Apps\book-translation-cli\src\book_translator\publishing\pipeline.py H:\AI_Apps\book-translation-cli\tests\test_publishing_workspace.py H:\AI_Apps\book-translation-cli\tests\test_publishing_pipeline.py
git commit -m "feat: add publishing stage resume controls"
```

### Task 8: Document and verify the publishing workflow

**Files:**
- Modify: `H:\AI_Apps\book-translation-cli\README.md`
- Modify: `H:\AI_Apps\book-translation-cli\docs\design.md`

- [ ] **Step 1: Update the docs**

Document:

- `engineering` vs `publishing`
- publishing stage outputs
- `--from-stage` / `--to-stage`
- quality-first expectations and non-goals
- example commands

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m ruff check .
python -m pytest -q
```

Expected: PASS

- [ ] **Step 3: Run a real publishing pass on a small non-fiction sample**

Run:

```bash
python -m book_translator publishing --input H:\AI_Apps\book-translation-cli\tests\fixtures\sample.epub --output H:\AI_Apps\book-translation-cli\out --provider gemini --model gemini-3.1-flash-lite-preview --to-stage final-review
```

Expected artifacts:

- `H:\AI_Apps\book-translation-cli\out\sample\publishing\draft\draft.txt`
- `H:\AI_Apps\book-translation-cli\out\sample\publishing\lexicon\glossary.json`
- `H:\AI_Apps\book-translation-cli\out\sample\publishing\proofread\proofread_notes.jsonl`
- `H:\AI_Apps\book-translation-cli\out\sample\publishing\final\translated.pdf`

- [ ] **Step 4: Run visual QA on the publishing PDF**

Run:

```bash
python -m book_translator qa-pdf --workspace H:\AI_Apps\book-translation-cli\out\sample
```

Expected artifacts:

- `H:\AI_Apps\book-translation-cli\out\sample\publishing\qa\pages\page-001.png`
- `H:\AI_Apps\book-translation-cli\out\sample\publishing\qa\qa_summary.json`

- [ ] **Step 5: Commit**

```bash
git add H:\AI_Apps\book-translation-cli\README.md H:\AI_Apps\book-translation-cli\docs\design.md
git commit -m "docs: add publishing workflow documentation"
```

## Self-Review

### Spec coverage

- Explicit `engineering` and `publishing` commands: Task 1
- Publishing workspace and artifacts: Tasks 2, 6, 7
- Draft, lexicon, revision, proofread, final-review stages: Tasks 3, 4, 5, 6
- Stage-aware resume and invalidation: Task 7
- Final text, PDF, and QA integration: Tasks 6 and 8
- Documentation and real-run verification: Task 8

No major spec requirement is uncovered.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task includes concrete files, commands, and expected outcomes.

### Type consistency

- Publishing config type: `PublishingRunConfig`
- Core artifact type: `PublishingChapterArtifact`
- Main orchestration entry point: `process_book_publishing`
- Stage names: `draft`, `lexicon`, `revision`, `proofread`, `final-review`

These names are used consistently across tasks.
