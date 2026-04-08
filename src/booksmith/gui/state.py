from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from booksmith.config import PublishingRunConfig, RunConfig

RunMode = Literal["engineering", "publishing"]
SourceKind = Literal["file", "directory"]
SourceFormat = Literal["pdf", "epub", "directory"]
OutputKind = Literal["txt", "pdf", "epub"]
RunStatus = Literal["idle", "ready", "running", "completed", "failed"]


@dataclass(slots=True)
class GuiFormState:
    mode: RunMode = "engineering"
    input_path: Path | None = None
    output_path: Path | None = None
    provider: str = "openai"
    model: str = ""
    api_key: str = ""
    persist_api_key: bool = False
    resume: bool = True
    force: bool = False
    glossary_path: Path | None = None
    name_map_path: Path | None = None
    chapter_strategy: str = "toc-first"
    manual_toc_path: Path | None = None
    chunk_size: int = 3000
    max_concurrency: int = 5
    request_timeout_seconds: float = 60.0
    max_attempts: int = 4
    render_pdf: bool = True
    style: str = "non-fiction-publishing"
    from_stage: str = "draft"
    to_stage: str = "final-review"
    also_pdf: bool = False
    also_epub: bool = False
    audit_depth: str = "consensus"
    enable_cross_review: bool = True
    image_policy: str = "extract-or-preserve-caption"


@dataclass(slots=True, frozen=True)
class GuiValidationIssue:
    field: str
    message: str


@dataclass(slots=True, frozen=True)
class GuiExpectedOutput:
    label: str
    kind: OutputKind
    path_hint: str
    required: bool = True
    source_path: Path | None = None


@dataclass(slots=True)
class GuiRuntimeRequest:
    mode: RunMode
    input_path: Path
    output_path: Path
    source_kind: SourceKind
    source_format: SourceFormat
    provider: str
    model: str
    config: RunConfig | PublishingRunConfig
    primary_output: OutputKind | None
    discovered_books: tuple[Path, ...] = ()
    additional_outputs: tuple[OutputKind, ...] = ()
    expected_outputs: tuple[GuiExpectedOutput, ...] = ()


@dataclass(slots=True)
class GuiRunState:
    status: RunStatus = "idle"
    current_book_name: str = ""
    current_stage: str = ""
    total_books: int = 0
    completed_books: int = 0
    successful_chunks: int = 0
    failed_chunks: int = 0
    estimated_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
    message: str = ""
    progress_fraction: float = 0.0
    logs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GuiResultState:
    summary: dict[str, object] | None = None
    output_paths: tuple[Path, ...] = ()
    audit_report_path: Path | None = None
    error: str | None = None
