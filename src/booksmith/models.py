from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class TocEntry(BaseModel):
    title: str
    page_index: int | None = None


class ExtractedBook(BaseModel):
    title: str
    raw_text: str
    toc: list[TocEntry] = Field(default_factory=list)
    pages: list[str] = Field(default_factory=list)


class Chapter(BaseModel):
    chapter_id: str
    chapter_index: int
    title: str
    text: str


class Chunk(BaseModel):
    chunk_id: str
    chapter_id: str
    chapter_index: int
    chunk_index: int
    chapter_title: str
    source_text: str
    source_token_estimate: int


class Manifest(BaseModel):
    book_id: str
    source_path: str
    source_fingerprint: str
    provider: str
    model: str
    config_fingerprint: str
    total_chapters: int = 0
    total_chunks: int = 0
    status: str = "initialized"
    started_at: str = Field(default_factory=utc_now_iso)
    finished_at: str | None = None


class TranslationRequest(BaseModel):
    book_title: str
    chapter_title: str
    chunk_index: int
    source_text: str
    chunk_id: str = ""
    glossary: dict[str, str] = Field(default_factory=dict)
    name_map: dict[str, str] = Field(default_factory=dict)


class TranslationResult(BaseModel):
    chunk_id: str
    translated_text: str
    provider: str
    model: str
    attempt_count: int
    latency_ms: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    timestamp: str = Field(default_factory=utc_now_iso)


class BookRunSummary(BaseModel):
    source_path: str
    provider: str
    model: str
    total_chapters: int
    total_chunks: int
    successful_chunks: int
    failed_chunks: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    duration_seconds: float
    avg_chunk_latency_ms: float


class PublishingStageState(BaseModel):
    stage: str
    fingerprint: str
    status: str


class PublishingChapterArtifact(BaseModel):
    chapter_id: str
    chapter_index: int
    title: str
    text: str


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
    source_title: str | None = None
    translated_title: str
    blocks: list[PublishingBlock] = Field(default_factory=list)
    assets: list[PublishingAsset] = Field(default_factory=list)


class StructuredPublishingBook(BaseModel):
    title: str = ""
    chapters: list[StructuredPublishingChapter] = Field(default_factory=list)


class PublishingAuditFinding(BaseModel):
    chapter_id: str
    block_id: str | None = None
    source_signature: str | None = None
    finding_type: str
    severity: Literal["low", "medium", "high"]
    source_excerpt: str
    target_excerpt: str
    reason: str
    auto_fixable: bool = False
    confidence: float = 0.5
    agent_role: Literal["audit", "review", "arbiter"] = "audit"


class PublishingLayoutAnnotation(BaseModel):
    kind: str
    payload: dict[str, str | int | bool] = Field(default_factory=dict)


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
    redline_blocker_count: int = 0
