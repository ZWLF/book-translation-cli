from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-3.1-flash-lite-preview",
}

DEFAULT_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

PUBLISHING_STAGES = (
    "draft",
    "lexicon",
    "revision",
    "proofread",
    "final-review",
)


class RunConfig(BaseModel):
    provider: str = "openai"
    model: str | None = None
    api_key_env: str | None = None
    max_concurrency: int = 5
    resume: bool = True
    force: bool = False
    glossary_path: Path | None = None
    name_map_path: Path | None = None
    chapter_strategy: str = "toc-first"
    manual_toc_path: Path | None = None
    chunk_size: int = 3000
    render_pdf: bool = True
    request_timeout_seconds: float = 60.0
    max_attempts: int = 4

    def resolved_model(self) -> str:
        return self.model or DEFAULT_MODELS[self.provider]

    def resolved_api_key_env(self) -> str:
        return self.api_key_env or DEFAULT_KEY_ENV[self.provider]

    def resolved_api_key(self) -> str:
        api_key = os.getenv(self.resolved_api_key_env()) or _read_dotenv_value(
            Path.cwd() / ".env",
            self.resolved_api_key_env(),
        )
        if not api_key:
            raise ValueError(
                f"Missing API key in environment variable {self.resolved_api_key_env()}."
            )
        return api_key

    def config_fingerprint(self) -> str:
        payload = {
            "provider": self.provider,
            "model": self.resolved_model(),
            "chapter_strategy": self.chapter_strategy,
            "chunk_size": self.chunk_size,
            "glossary_path": str(self.glossary_path) if self.glossary_path else None,
            "name_map_path": str(self.name_map_path) if self.name_map_path else None,
            "manual_toc_path": str(self.manual_toc_path) if self.manual_toc_path else None,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class PublishingRunConfig(RunConfig):
    style: Literal["non-fiction-publishing"] = "non-fiction-publishing"
    from_stage: Literal["draft", "lexicon", "revision", "proofread", "final-review"] = "draft"
    to_stage: Literal["draft", "lexicon", "revision", "proofread", "final-review"] = (
        "final-review"
    )
    mode: Literal["publishing"] = "publishing"
    max_concurrency: int = Field(default=3, ge=1, le=16)

    @model_validator(mode="after")
    def validate_stage_window(self) -> PublishingRunConfig:
        if PUBLISHING_STAGES.index(self.from_stage) > PUBLISHING_STAGES.index(self.to_stage):
            raise ValueError("from_stage must not come after to_stage.")
        return self

    def config_fingerprint(self) -> str:
        payload = {
            "provider": self.provider,
            "model": self.resolved_model(),
            "chapter_strategy": self.chapter_strategy,
            "chunk_size": self.chunk_size,
            "glossary_path": str(self.glossary_path) if self.glossary_path else None,
            "name_map_path": str(self.name_map_path) if self.name_map_path else None,
            "manual_toc_path": str(self.manual_toc_path) if self.manual_toc_path else None,
            "style": self.style,
            "mode": self.mode,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def _read_dotenv_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != key:
            continue
        return value.strip().strip("\"'")
    return None
