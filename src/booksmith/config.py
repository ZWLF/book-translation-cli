from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from booksmith.provider_catalog import (
    DEFAULT_PROVIDER_ID,
    get_provider_option,
    list_enabled_provider_options,
)

DEFAULT_MODELS = {
    option.provider_id: option.default_model for option in list_enabled_provider_options()
}

DEFAULT_KEY_ENV = {
    option.provider_id: option.api_key_env for option in list_enabled_provider_options()
}

PUBLISHING_STAGES = (
    "draft",
    "lexicon",
    "revision",
    "proofread",
    "final-review",
    "deep-review",
)


class RunConfig(BaseModel):
    provider: str = DEFAULT_PROVIDER_ID
    model: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None
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

    @model_validator(mode="after")
    def validate_provider(self) -> RunConfig:
        option = get_provider_option(self.provider)
        self.provider = option.provider_id
        return self

    @model_validator(mode="after")
    def validate_model(self) -> RunConfig:
        if self.model:
            option = get_provider_option(self.provider)
            if self.model not in option.models:
                allowed_models = ", ".join(option.models)
                raise ValueError(
                    f"Unsupported model for provider {self.provider}: {self.model}. "
                    f"Allowed models: {allowed_models}."
                )
        return self

    def resolved_model(self) -> str:
        return self.model or get_provider_option(self.provider).default_model

    def resolved_api_key_env(self) -> str:
        return self.api_key_env or get_provider_option(self.provider).api_key_env

    def resolved_api_key(self) -> str:
        if self.api_key:
            return self.api_key

        api_key_env = self.resolved_api_key_env()
        api_key = os.getenv(api_key_env) or _read_dotenv_value(Path.cwd() / ".env", api_key_env)
        if not api_key:
            raise ValueError(f"Missing API key in environment variable {api_key_env}.")
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
    from_stage: Literal[
        "draft",
        "lexicon",
        "revision",
        "proofread",
        "final-review",
        "deep-review",
    ] = "draft"
    to_stage: Literal[
        "draft",
        "lexicon",
        "revision",
        "proofread",
        "final-review",
        "deep-review",
    ] = (
        "final-review"
    )
    mode: Literal["publishing"] = "publishing"
    max_concurrency: int = Field(default=3, ge=1, le=16)
    also_pdf: bool = False
    also_epub: bool = False
    audit_depth: Literal["standard", "consensus"] = "consensus"
    enable_cross_review: bool = True
    image_policy: Literal["extract-or-preserve-caption"] = "extract-or-preserve-caption"

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
            "also_pdf": self.also_pdf,
            "also_epub": self.also_epub,
            "audit_depth": self.audit_depth,
            "enable_cross_review": self.enable_cross_review,
            "image_policy": self.image_policy,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class PublishingOutputSelection(BaseModel):
    primary_output: Literal["pdf", "epub"]
    additional_outputs: list[Literal["pdf", "epub"]] = []


def resolve_publishing_outputs(
    source_path: Path,
    config: PublishingRunConfig,
) -> PublishingOutputSelection:
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        primary_output = "pdf"
        additional_outputs = ["epub"] if config.also_epub else []
    elif suffix == ".epub":
        primary_output = "epub"
        additional_outputs = ["pdf"] if config.also_pdf else []
    else:
        raise ValueError(f"Unsupported publishing source format: {source_path}")
    return PublishingOutputSelection(
        primary_output=primary_output,
        additional_outputs=additional_outputs,
    )


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
