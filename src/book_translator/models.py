from __future__ import annotations

from datetime import UTC, datetime

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
