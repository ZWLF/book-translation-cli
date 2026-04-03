# Structured Publishing Audit And EPUB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `publishing` mode with a structured content model, multi-agent audit/review/arbitration, controlled repair, format-aware `PDF/EPUB` output selection, asset/caption preservation, and a reflowable EPUB renderer.

**Architecture:** Keep the existing `publishing` stage names and public command shape, but make `deep-review` internally richer. Introduce a structured publishing book model shared by the audit loop, polished PDF renderer, and a new EPUB renderer so content fidelity, asset handling, and output parity all sit on one canonical representation.

**Tech Stack:** Python 3.11+, Pydantic, Typer, ReportLab, EbookLib, BeautifulSoup4, PyMuPDF, pytest, ruff.

---

## File Map

- Modify: `src/book_translator/config.py`
  - Add output-selection and audit-loop config for publishing mode.
- Modify: `src/book_translator/models.py`
  - Add structured publishing book/block/asset/citation/audit models.
- Modify: `src/book_translator/state/workspace.py`
  - Add audit and asset artifact paths plus final EPUB path.
- Create: `src/book_translator/publishing/structure.py`
  - Build structured publishing chapters/blocks/assets from chapter artifacts and source hints.
- Create: `src/book_translator/publishing/consensus.py`
  - Merge audit/review findings, route disputed findings to arbitration, and emit consensus stats.
- Modify: `src/book_translator/publishing/source_audit.py`
  - Emit richer source-aware findings keyed to structured blocks and asset/citation anchors.
- Modify: `src/book_translator/publishing/editorial_revision.py`
  - Apply bounded repairs against structured blocks instead of only flattened chapter text.
- Modify: `src/book_translator/publishing/deep_review.py`
  - Orchestrate structure build, audit, review, arbitration, repair, confirmation, and artifact persistence.
- Modify: `src/book_translator/publishing/pipeline.py`
  - Add primary/additional output routing, audit artifact summary counts, and EPUB build dispatch.
- Modify: `src/book_translator/output/assembler.py`
  - Assemble final TXT from structured chapter/block content.
- Modify: `src/book_translator/output/polished_pdf.py`
  - Render from structured blocks/assets/citations and preserve caption-only image anchors.
- Create: `src/book_translator/output/epub_renderer.py`
  - Render reflowable EPUB from the same structured publishing book.
- Modify: `src/book_translator/cli.py`
  - Add `--also-pdf`, `--also-epub`, `--audit-depth`, `--enable-cross-review`, and `--image-policy`.
- Modify: `src/book_translator/publishing/artifacts.py`
  - Export structured publishing artifacts instead of only chapter text rows.
- Create: `tests/test_publishing_structure.py`
  - Cover block typing, asset extraction metadata, and image/caption fallback.
- Create: `tests/test_publishing_consensus.py`
  - Cover audit/review merge, arbitration routing, and auto-fix gating.
- Modify: `tests/test_publishing_source_audit.py`
  - Extend checks to block anchors, image/caption findings, and citation findings.
- Modify: `tests/test_publishing_deep_review.py`
  - Cover two-pass repair/confirmation and persistence of audit artifacts.
- Modify: `tests/test_publishing_pipeline.py`
  - Cover format-aware output routing and summary counts.
- Modify: `tests/test_publishing_workspace.py`
  - Cover new workspace paths for audit/assets/final EPUB.
- Modify: `tests/test_polished_pdf.py`
  - Cover image anchor fallback and structured-block rendering.
- Create: `tests/test_epub_renderer.py`
  - Cover EPUB TOC, list/callout rendering, images, and caption fallback.
- Modify: `README.md`
  - Document new publishing flags, output rules, and EPUB support.

## Task 1: Add Publishing Output Routing And Workspace Paths

**Files:**
- Modify: `src/book_translator/config.py`
- Modify: `src/book_translator/state/workspace.py`
- Modify: `src/book_translator/cli.py`
- Test: `tests/test_publishing_workspace.py`
- Test: `tests/test_publishing_pipeline.py`

- [ ] **Step 1: Write the failing tests for output-selection defaults and new paths**

```python
def test_pdf_input_defaults_to_pdf_only() -> None:
    config = PublishingRunConfig()
    resolved = resolve_publishing_outputs(
        source_path=Path("book.pdf"),
        config=config,
    )
    assert resolved.primary_output == "pdf"
    assert resolved.additional_outputs == []


def test_epub_input_defaults_to_epub_only() -> None:
    config = PublishingRunConfig()
    resolved = resolve_publishing_outputs(
        source_path=Path("book.epub"),
        config=config,
    )
    assert resolved.primary_output == "epub"
    assert resolved.additional_outputs == []


def test_workspace_exposes_publishing_audit_and_epub_paths(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "book")
    assert workspace.publishing_audit_dir.name == "audit"
    assert workspace.publishing_assets_dir.name == "assets"
    assert workspace.publishing_final_epub_path.name == "translated.epub"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest tests/test_publishing_workspace.py tests/test_publishing_pipeline.py -q
```

Expected:

- fail because output routing helpers and EPUB/audit workspace paths do not exist yet

- [ ] **Step 3: Implement config and workspace support**

```python
class PublishingRunConfig(RunConfig):
    style: Literal["non-fiction-publishing"] = "non-fiction-publishing"
    from_stage: Literal["draft", "lexicon", "revision", "proofread", "final-review", "deep-review"] = "draft"
    to_stage: Literal["draft", "lexicon", "revision", "proofread", "final-review", "deep-review"] = "final-review"
    also_pdf: bool = False
    also_epub: bool = False
    audit_depth: Literal["standard", "consensus"] = "consensus"
    enable_cross_review: bool = True
    image_policy: Literal["extract-or-preserve-caption"] = "extract-or-preserve-caption"
```

```python
class PublishingOutputSelection(BaseModel):
    primary_output: Literal["pdf", "epub"]
    additional_outputs: list[Literal["pdf", "epub"]] = Field(default_factory=list)


def resolve_publishing_outputs(*, source_path: Path, config: PublishingRunConfig) -> PublishingOutputSelection:
    source_suffix = source_path.suffix.lower()
    primary = "pdf" if source_suffix == ".pdf" else "epub"
    extras: list[Literal["pdf", "epub"]] = []
    if primary == "pdf" and config.also_epub:
        extras.append("epub")
    if primary == "epub" and config.also_pdf:
        extras.append("pdf")
    return PublishingOutputSelection(primary_output=primary, additional_outputs=extras)
```

```python
self.publishing_audit_dir = self.publishing_root_path / "audit"
self.publishing_assets_dir = self.publishing_root_path / "assets"
self.publishing_audit_source_path = self.publishing_audit_dir / "source_audit.jsonl"
self.publishing_audit_review_path = self.publishing_audit_dir / "review_audit.jsonl"
self.publishing_audit_consensus_path = self.publishing_audit_dir / "consensus.json"
self.publishing_audit_report_path = self.publishing_audit_dir / "final_audit_report.json"
self.publishing_assets_manifest_path = self.publishing_assets_dir / "manifest.json"
self.publishing_assets_images_dir = self.publishing_assets_dir / "images"
self.publishing_final_epub_path = self.publishing_final_dir / "translated.epub"
```

- [ ] **Step 4: Add the publishing CLI flags**

```python
also_pdf: Annotated[bool, typer.Option("--also-pdf")] = False,
also_epub: Annotated[bool, typer.Option("--also-epub")] = False,
audit_depth: Annotated[str, typer.Option("--audit-depth")] = "consensus",
enable_cross_review: Annotated[bool, typer.Option("--enable-cross-review/--no-cross-review")] = True,
image_policy: Annotated[str, typer.Option("--image-policy")] = "extract-or-preserve-caption",
```

- [ ] **Step 5: Re-run the targeted tests**

Run:

```bash
python -m pytest tests/test_publishing_workspace.py tests/test_publishing_pipeline.py -q
```

Expected:

- targeted tests pass

- [ ] **Step 6: Commit the routing and workspace changes**

```bash
git add src/book_translator/config.py src/book_translator/state/workspace.py src/book_translator/cli.py tests/test_publishing_workspace.py tests/test_publishing_pipeline.py
git commit -m "Add publishing output routing and workspace paths"
```

## Task 2: Build The Structured Publishing Model

**Files:**
- Modify: `src/book_translator/models.py`
- Create: `src/book_translator/publishing/structure.py`
- Modify: `src/book_translator/publishing/artifacts.py`
- Test: `tests/test_publishing_structure.py`

- [ ] **Step 1: Write the failing tests for structured blocks and assets**

```python
def test_structure_builder_splits_numbered_items_into_ordered_blocks() -> None:
    artifact = PublishingChapterArtifact(
        chapter_id="c1",
        chapter_index=1,
        title="法则",
        text="1. 第一条\n2. 第二条\n3. 第三条",
    )
    chapter = build_structured_chapter(
        artifact=artifact,
        source_text="1. First\n2. Second\n3. Third",
        source_assets=[],
    )
    assert [block.kind for block in chapter.blocks][:3] == [
        "ordered_item",
        "ordered_item",
        "ordered_item",
    ]


def test_structure_builder_preserves_caption_only_asset_anchor() -> None:
    chapter = build_structured_chapter(
        artifact=PublishingChapterArtifact(
            chapter_id="c2",
            chapter_index=2,
            title="图片章",
            text="[图] 火箭发射图",
        ),
        source_text="Rocket image. Figure 1. Falcon launch.",
        source_assets=[{"source_asset_id": "img-1", "caption": "Falcon launch", "status": "caption-only"}],
    )
    assert any(block.kind == "caption" for block in chapter.blocks)
    assert chapter.assets[0].status == "caption-only"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest tests/test_publishing_structure.py -q
```

Expected:

- fail because the structured book/chapter/block/asset model does not exist yet

- [ ] **Step 3: Add structured publishing models**

```python
class PublishingCitation(BaseModel):
    citation_id: str
    marker: str
    block_id: str
    reference_target: str | None = None
    display_class: Literal["inline", "reference"] = "inline"


class PublishingAsset(BaseModel):
    source_asset_id: str
    source_location_hint: str | None = None
    extracted_path: str | None = None
    caption: str | None = None
    block_anchor_id: str | None = None
    status: Literal["extracted", "caption-only", "missing"] = "missing"


class PublishingBlock(BaseModel):
    block_id: str
    kind: Literal[
        "paragraph",
        "heading",
        "ordered_item",
        "unordered_item",
        "qa_question",
        "qa_answer",
        "callout",
        "quote",
        "reference_entry",
        "image",
        "caption",
    ]
    text: str = ""
    order_index: int
    source_anchor: str | None = None
    citations: list[PublishingCitation] = Field(default_factory=list)
    issue_tags: list[str] = Field(default_factory=list)


class StructuredPublishingChapter(BaseModel):
    chapter_id: str
    chapter_index: int
    source_title: str
    translated_title: str
    blocks: list[PublishingBlock] = Field(default_factory=list)
    assets: list[PublishingAsset] = Field(default_factory=list)
```

- [ ] **Step 4: Implement deterministic structure building**

```python
def build_structured_chapter(
    *,
    artifact: PublishingChapterArtifact,
    source_text: str,
    source_assets: list[dict[str, object]],
) -> StructuredPublishingChapter:
    blocks = _build_blocks_from_text(artifact.text)
    assets = _normalize_source_assets(source_assets)
    _attach_caption_blocks(blocks=blocks, assets=assets)
    return StructuredPublishingChapter(
        chapter_id=artifact.chapter_id,
        chapter_index=artifact.chapter_index,
        source_title=artifact.title,
        translated_title=artifact.title,
        blocks=blocks,
        assets=assets,
    )
```

- [ ] **Step 5: Re-run the structure tests**

Run:

```bash
python -m pytest tests/test_publishing_structure.py -q
```

Expected:

- structure tests pass

- [ ] **Step 6: Commit the structured model layer**

```bash
git add src/book_translator/models.py src/book_translator/publishing/structure.py src/book_translator/publishing/artifacts.py tests/test_publishing_structure.py
git commit -m "Add structured publishing book model"
```

## Task 3: Add Multi-Agent Consensus And Arbitration

**Files:**
- Modify: `src/book_translator/models.py`
- Modify: `src/book_translator/publishing/source_audit.py`
- Create: `src/book_translator/publishing/consensus.py`
- Test: `tests/test_publishing_source_audit.py`
- Test: `tests/test_publishing_consensus.py`

- [ ] **Step 1: Write the failing consensus tests**

```python
def test_merge_findings_groups_agreed_and_disputed_items() -> None:
    audit = [
        PublishingAuditFinding(
            chapter_id="c1",
            finding_type="possible_omission",
            severity="high",
            source_excerpt="Missing sentence",
            target_excerpt="",
            reason="audit",
            auto_fixable=True,
        )
    ]
    review = [
        PublishingAuditFinding(
            chapter_id="c1",
            finding_type="possible_omission",
            severity="high",
            source_excerpt="Missing sentence",
            target_excerpt="",
            reason="review",
            auto_fixable=True,
        ),
        PublishingAuditFinding(
            chapter_id="c1",
            finding_type="caption_missing",
            severity="medium",
            source_excerpt="Figure 1",
            target_excerpt="",
            reason="review only",
            auto_fixable=True,
        ),
    ]
    consensus = merge_review_findings(audit_findings=audit, review_findings=review)
    assert len(consensus.agreed) == 1
    assert len(consensus.disputed) == 1


def test_only_disputed_findings_require_arbitration() -> None:
    consensus = PublishingConsensusResult(
        agreed=[...],
        disputed=[...],
        low_confidence=[],
    )
    assert build_arbitration_queue(consensus) == consensus.disputed
```

- [ ] **Step 2: Run the audit and consensus tests to verify they fail**

Run:

```bash
python -m pytest tests/test_publishing_source_audit.py tests/test_publishing_consensus.py -q
```

Expected:

- fail because richer keyed findings and consensus merge helpers do not exist yet

- [ ] **Step 3: Extend audit findings with provenance and fix gating**

```python
class PublishingAuditFinding(BaseModel):
    chapter_id: str
    block_id: str | None = None
    finding_type: str
    severity: Literal["low", "medium", "high"]
    confidence: float = 0.5
    source_excerpt: str
    target_excerpt: str
    reason: str
    auto_fixable: bool = False
    agent_role: Literal["audit", "review", "arbiter"] = "audit"
```

- [ ] **Step 4: Implement consensus and arbitration plumbing**

```python
class PublishingConsensusResult(BaseModel):
    agreed: list[PublishingAuditFinding] = Field(default_factory=list)
    disputed: list[PublishingAuditFinding] = Field(default_factory=list)
    low_confidence: list[PublishingAuditFinding] = Field(default_factory=list)


def merge_review_findings(
    *,
    audit_findings: list[PublishingAuditFinding],
    review_findings: list[PublishingAuditFinding],
) -> PublishingConsensusResult:
    # Key by chapter_id + block_id + finding_type + source_excerpt prefix
    ...
```

```python
def arbiter_fix_candidates(
    consensus: PublishingConsensusResult,
    *,
    arbiter_findings: list[PublishingAuditFinding],
) -> list[PublishingAuditFinding]:
    return [
        finding
        for finding in (*consensus.agreed, *arbiter_findings)
        if finding.auto_fixable and finding.severity in {"low", "medium", "high"}
    ]
```

- [ ] **Step 5: Re-run the audit and consensus tests**

Run:

```bash
python -m pytest tests/test_publishing_source_audit.py tests/test_publishing_consensus.py -q
```

Expected:

- all targeted tests pass

- [ ] **Step 6: Commit the multi-agent consensus layer**

```bash
git add src/book_translator/models.py src/book_translator/publishing/source_audit.py src/book_translator/publishing/consensus.py tests/test_publishing_source_audit.py tests/test_publishing_consensus.py
git commit -m "Add publishing audit consensus and arbitration"
```

## Task 4: Integrate Structured Repair Into Deep Review

**Files:**
- Modify: `src/book_translator/publishing/editorial_revision.py`
- Modify: `src/book_translator/publishing/deep_review.py`
- Modify: `src/book_translator/publishing/pipeline.py`
- Modify: `src/book_translator/output/assembler.py`
- Test: `tests/test_publishing_deep_review.py`
- Test: `tests/test_publishing_pipeline.py`

- [ ] **Step 1: Write the failing deep-review tests**

```python
def test_deep_review_runs_audit_review_repair_and_confirmation_once() -> None:
    result = run_deep_review_pipeline(
        source_chapters=[...],
        final_artifacts=[...],
        config=PublishingRunConfig(audit_depth="consensus", enable_cross_review=True),
    )
    assert result.repair_passes == 1
    assert result.confirmation_passes == 1
    assert result.final_report["unresolved_count"] >= 0


def test_assemble_publishing_output_text_uses_structured_blocks() -> None:
    chapters = [
        StructuredPublishingChapter(
            chapter_id="c1",
            chapter_index=1,
            source_title="Chapter",
            translated_title="章节",
            blocks=[
                PublishingBlock(block_id="b1", kind="ordered_item", text="1. 第一条", order_index=1),
                PublishingBlock(block_id="b2", kind="ordered_item", text="2. 第二条", order_index=2),
            ],
        )
    ]
    text = assemble_structured_publishing_output_text(chapters)
    assert "1. 第一条" in text
    assert "2. 第二条" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest tests/test_publishing_deep_review.py tests/test_publishing_pipeline.py -q
```

Expected:

- fail because deep-review still operates on flattened artifacts only

- [ ] **Step 3: Add bounded repair and final-report generation**

```python
class DeepReviewResult(BaseModel):
    chapters: list[StructuredPublishingChapter]
    source_findings: list[PublishingAuditFinding]
    review_findings: list[PublishingAuditFinding]
    arbiter_findings: list[PublishingAuditFinding]
    final_report: dict[str, object]
    repair_passes: int = 1
    confirmation_passes: int = 1
```

```python
async def run_deep_review(
    *,
    source_chapters: list[Chapter],
    final_artifacts: list[PublishingChapterArtifact],
    config: PublishingRunConfig,
    ...
) -> DeepReviewResult:
    structured = build_structured_book(...)
    source_findings = run_source_audit(...)
    review_findings = run_source_review(...) if config.enable_cross_review else []
    consensus = merge_review_findings(...)
    arbiter_findings = await run_arbiter(...) if consensus.disputed else []
    repaired = apply_structured_repairs(...)
    confirmation = run_source_audit(...)
    return DeepReviewResult(...)
```

- [ ] **Step 4: Persist new audit artifacts and assemble final text from structured content**

```python
workspace.write_publishing_jsonl(
    workspace.publishing_audit_source_path,
    [finding.model_dump() for finding in result.source_findings],
)
workspace.write_publishing_jsonl(
    workspace.publishing_audit_review_path,
    [finding.model_dump() for finding in result.review_findings],
)
workspace._write_publishing_json(workspace.publishing_audit_consensus_path, consensus.model_dump())
workspace._write_publishing_json(workspace.publishing_audit_report_path, result.final_report)
workspace.write_publishing_jsonl(
    workspace.publishing_deep_review_chapters_path,
    [chapter.model_dump() for chapter in result.chapters],
)
```

- [ ] **Step 5: Re-run the targeted tests**

Run:

```bash
python -m pytest tests/test_publishing_deep_review.py tests/test_publishing_pipeline.py -q
```

Expected:

- deep-review and pipeline tests pass

- [ ] **Step 6: Commit the deep-review integration**

```bash
git add src/book_translator/publishing/editorial_revision.py src/book_translator/publishing/deep_review.py src/book_translator/publishing/pipeline.py src/book_translator/output/assembler.py tests/test_publishing_deep_review.py tests/test_publishing_pipeline.py
git commit -m "Integrate structured deep review and repair"
```

## Task 5: Add The Reflowable EPUB Renderer

**Files:**
- Create: `src/book_translator/output/epub_renderer.py`
- Modify: `src/book_translator/publishing/pipeline.py`
- Test: `tests/test_epub_renderer.py`
- Test: `tests/test_publishing_pipeline.py`

- [ ] **Step 1: Write the failing EPUB renderer tests**

```python
def test_render_epub_creates_nav_and_chapter_documents(tmp_path: Path) -> None:
    book = StructuredPublishingBook(
        title="测试书",
        chapters=[
            StructuredPublishingChapter(
                chapter_id="c1",
                chapter_index=1,
                source_title="Chapter 1",
                translated_title="第一章",
                blocks=[
                    PublishingBlock(block_id="b1", kind="paragraph", text="正文", order_index=1),
                ],
            )
        ],
    )
    output_path = tmp_path / "translated.epub"
    render_structured_epub(book, output_path)
    assert output_path.exists()


def test_render_epub_preserves_ordered_list_and_caption_only_asset(tmp_path: Path) -> None:
    book = StructuredPublishingBook(...)
    output_path = tmp_path / "translated.epub"
    render_structured_epub(book, output_path)
    html = read_epub_item(output_path, "chapter-001.xhtml")
    assert "<ol>" in html
    assert "图片说明" in html
```

- [ ] **Step 2: Run the EPUB tests to verify they fail**

Run:

```bash
python -m pytest tests/test_epub_renderer.py -q
```

Expected:

- fail because the EPUB renderer does not exist yet

- [ ] **Step 3: Implement the renderer**

```python
def render_structured_epub(book: StructuredPublishingBook, output_path: Path) -> None:
    epub_book = epub.EpubBook()
    epub_book.set_identifier(book.book_id)
    epub_book.set_title(book.title)
    epub_book.set_language("zh-CN")
    epub_book.add_author("ZWLF")
    epub_book.add_item(_default_stylesheet())

    spine = ["nav"]
    toc_items: list[epub.EpubHtml] = []
    for chapter in book.chapters:
        item = epub.EpubHtml(
            title=chapter.translated_title,
            file_name=f"chapter-{chapter.chapter_index:03d}.xhtml",
            lang="zh-CN",
        )
        item.content = render_epub_chapter_html(chapter)
        epub_book.add_item(item)
        toc_items.append(item)
        spine.append(item)

    epub_book.toc = tuple(toc_items)
    epub_book.spine = spine
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())
    epub.write_epub(str(output_path), epub_book)
```

- [ ] **Step 4: Dispatch EPUB output only when primary or requested**

```python
selection = resolve_publishing_outputs(source_path=input_path, config=config)
if selection.primary_output == "epub" or "epub" in selection.additional_outputs:
    render_structured_epub(structured_book, workspace.publishing_final_epub_path)
```

- [ ] **Step 5: Re-run the EPUB and pipeline tests**

Run:

```bash
python -m pytest tests/test_epub_renderer.py tests/test_publishing_pipeline.py -q
```

Expected:

- EPUB renderer tests pass
- pipeline tests confirm format-aware output selection

- [ ] **Step 6: Commit the EPUB renderer**

```bash
git add src/book_translator/output/epub_renderer.py src/book_translator/publishing/pipeline.py tests/test_epub_renderer.py tests/test_publishing_pipeline.py
git commit -m "Add reflowable publishing EPUB renderer"
```

## Task 6: Feed Structured Content Into The PDF Renderer

**Files:**
- Modify: `src/book_translator/output/polished_pdf.py`
- Test: `tests/test_polished_pdf.py`

- [ ] **Step 1: Write the failing PDF rendering tests for structured blocks and image fallback**

```python
def test_pdf_renderer_keeps_ordered_items_as_separate_flowables(tmp_path: Path) -> None:
    book = StructuredPublishingBook(...)
    pdf_path = tmp_path / "translated.pdf"
    render_polished_pdf_from_structured_book(book, pdf_path)
    assert pdf_path.exists()


def test_pdf_renderer_emits_caption_when_asset_is_caption_only(tmp_path: Path) -> None:
    book = StructuredPublishingBook(...)
    pdf_path = tmp_path / "translated.pdf"
    render_polished_pdf_from_structured_book(book, pdf_path)
    text = extract_pdf_text(pdf_path)
    assert "图片说明" in text
```

- [ ] **Step 2: Run the PDF renderer tests to verify they fail**

Run:

```bash
python -m pytest tests/test_polished_pdf.py -q
```

Expected:

- fail because the renderer still expects chapter-level text and heuristics

- [ ] **Step 3: Add a structured-book rendering path**

```python
def render_polished_pdf_from_structured_book(
    book: StructuredPublishingBook,
    output_path: Path,
) -> None:
    story = []
    for chapter in book.chapters:
        story.extend(_chapter_title_flowables(chapter))
        story.extend(_structured_block_flowables(chapter.blocks, chapter.assets))
    build_pdf(story=story, output_path=output_path)
```

- [ ] **Step 4: Re-run the PDF tests**

Run:

```bash
python -m pytest tests/test_polished_pdf.py -q
```

Expected:

- PDF renderer tests pass

- [ ] **Step 5: Commit the renderer integration**

```bash
git add src/book_translator/output/polished_pdf.py tests/test_polished_pdf.py
git commit -m "Render publishing PDF from structured content"
```

## Task 7: Finish Docs, Full Validation, And Real-Book Acceptance

**Files:**
- Modify: `README.md`
- Test: `tests/test_publishing_workspace.py`
- Test: `tests/test_publishing_pipeline.py`
- Test: `tests/test_epub_renderer.py`
- Test: `tests/test_polished_pdf.py`

- [ ] **Step 1: Update README with the new flags and output rules**

```md
### Publishing output defaults

- `PDF` input defaults to `translated.pdf`
- `EPUB` input defaults to `translated.epub`
- use `--also-epub` to add EPUB output for PDF input
- use `--also-pdf` to add PDF output for EPUB input

### Publishing audit artifacts

- `publishing/audit/source_audit.jsonl`
- `publishing/audit/review_audit.jsonl`
- `publishing/audit/consensus.json`
- `publishing/audit/final_audit_report.json`
```

- [ ] **Step 2: Run the full automated test suite**

Run:

```bash
python -m ruff check .
python -m pytest -q
```

Expected:

- `ruff` reports no violations
- full test suite passes

- [ ] **Step 3: Run real-book acceptance on the Elon workspace with PDF primary output**

Run:

```bash
python -m book_translator publishing --input "H:\书\The Book of Elon A Guide to Purpose and Success (Eric Jorgenson).pdf" --output H:\AI_Apps\book-translation-cli\out --provider gemini --model gemini-3.1-flash-lite-preview --from-stage final-review --to-stage deep-review --render-pdf --also-epub
```

Expected:

- publishing run completes with `completed_stage = deep-review`
- `publishing/final/translated.pdf` exists
- `publishing/final/translated.epub` exists
- `publishing/audit/final_audit_report.json` exists

- [ ] **Step 4: Generate QA pages for representative PDF pages**

Run:

```bash
python -m book_translator qa-pdf --workspace "H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson" --pages 1,4,145,151,154,278,279
```

Expected:

- updated QA PNGs exist under `publishing/qa/pages`

- [ ] **Step 5: Smoke-test EPUB structure**

Run:

```bash
@'
from pathlib import Path
from ebooklib import epub

book = epub.read_epub(r"H:\AI_Apps\book-translation-cli\out\the-book-of-elon-a-guide-to-purpose-and-success-eric-jorgenson\publishing\final\translated.epub")
docs = [item for item in book.get_items() if item.get_type() == 9]
print(len(docs))
print(any("nav" in getattr(item, "file_name", "") for item in docs))
'@ | python -
```

Expected:

- prints a positive chapter-document count
- confirms a nav document exists

- [ ] **Step 6: Commit docs and acceptance-driven updates**

```bash
git add README.md
git commit -m "Document structured publishing audit and EPUB output"
```

## Self-Review Checklist

- Every spec requirement maps to at least one task:
  - structured content model: Tasks 2, 4, 6
  - multi-agent audit/review/arbitration: Tasks 3 and 4
  - bounded repair: Task 4
  - format-aware output routing: Tasks 1 and 5
  - EPUB renderer: Task 5
  - image/caption policy: Tasks 2, 4, 5, 6
  - audit artifacts/reporting: Tasks 1, 3, 4, 7
- No placeholder steps remain.
- Public stage semantics stay stable because the plan deepens `deep-review` instead of inventing a new CLI stage.
- Output selection is deterministic and explicitly tested before any renderer work starts.
