from __future__ import annotations

import json
from pathlib import Path

from book_translator.models import (
    Chunk,
    Manifest,
    PublishingStageState,
    TranslationResult,
)


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest_path = self.root / "manifest.json"
        self.chunks_path = self.root / "chunks.jsonl"
        self.translations_path = self.root / "translations.jsonl"
        self.error_log_path = self.root / "error_log.json"
        self.summary_path = self.root / "run_summary.json"
        self.title_translations_path = self.root / "title_translations.json"
        self.output_path = self.root / "translated.txt"
        self.pdf_output_path = self.root / "translated.pdf"
        self.qa_root_path = self.root / "qa"
        self.qa_pages_path = self.qa_root_path / "pages"
        self.qa_summary_path = self.qa_root_path / "qa_summary.json"
        self.publishing_root_path = self.root / "publishing"
        self.publishing_state_dir = self.publishing_root_path / "state"
        self.publishing_lexicon_dir = self.publishing_root_path / "lexicon"
        self.publishing_draft_text_path = self.publishing_root_path / "draft" / "draft.txt"
        self.publishing_glossary_path = self.publishing_lexicon_dir / "glossary.json"
        self.publishing_names_path = self.publishing_lexicon_dir / "names.json"
        self.publishing_decisions_path = self.publishing_lexicon_dir / "decisions.json"
        self.publishing_final_pdf_path = self.publishing_root_path / "final" / "translated.pdf"

    def initialize(self, manifest: Manifest) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    def read_manifest(self) -> Manifest:
        return Manifest.model_validate_json(self.manifest_path.read_text(encoding="utf-8"))

    def assert_resume_compatible(
        self,
        *,
        source_fingerprint: str,
        provider: str,
        model: str,
        config_fingerprint: str,
    ) -> None:
        manifest = self.read_manifest()
        if (
            manifest.source_fingerprint != source_fingerprint
            or manifest.provider != provider
            or manifest.model != model
            or manifest.config_fingerprint != config_fingerprint
        ):
            raise ValueError("Existing run state is incompatible. Re-run with --force.")

    def write_chunks(self, chunks: list[Chunk]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.chunks_path.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(chunk.model_dump_json())
                handle.write("\n")

    def append_translation(self, result: TranslationResult) -> None:
        with self.translations_path.open("a", encoding="utf-8") as handle:
            handle.write(result.model_dump_json())
            handle.write("\n")

    def completed_chunk_ids(self) -> set[str]:
        if not self.translations_path.exists():
            return set()
        return {
            json.loads(line)["chunk_id"]
            for line in self.translations_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    def load_translations(self) -> dict[str, TranslationResult]:
        if not self.translations_path.exists():
            return {}
        results: dict[str, TranslationResult] = {}
        for line in self.translations_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = TranslationResult.model_validate(json.loads(line))
            results[record.chunk_id] = record
        return results

    def load_chunks(self) -> list[Chunk]:
        if not self.chunks_path.exists():
            return []
        chunks: list[Chunk] = []
        for line in self.chunks_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            chunks.append(Chunk.model_validate(json.loads(line)))
        return chunks

    def read_summary(self) -> dict[str, object]:
        if not self.summary_path.exists():
            return {}
        return json.loads(self.summary_path.read_text(encoding="utf-8"))

    def write_errors(self, errors: list[dict[str, object]]) -> None:
        self.error_log_path.write_text(
            json.dumps(errors, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def write_summary(self, summary: dict[str, object]) -> None:
        self.summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def read_title_translations(self) -> dict[str, str]:
        if not self.title_translations_path.exists():
            return {}
        data = json.loads(self.title_translations_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}

    def write_title_translations(self, translations: dict[str, str]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.title_translations_path.write_text(
            json.dumps(translations, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def write_publishing_stage_state(
        self,
        stage: str,
        payload: PublishingStageState | dict[str, object],
    ) -> None:
        self.publishing_state_dir.mkdir(parents=True, exist_ok=True)
        data = self._normalize_publishing_stage_state(stage=stage, payload=payload)
        self.publishing_state_dir.joinpath(f"{stage}.json").write_text(
            data.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def read_publishing_stage_state(self, stage: str) -> PublishingStageState | None:
        state_path = self.publishing_state_dir / f"{stage}.json"
        if not state_path.exists():
            return None
        return PublishingStageState.model_validate_json(state_path.read_text(encoding="utf-8"))

    def _normalize_publishing_stage_state(
        self,
        *,
        stage: str,
        payload: PublishingStageState | dict[str, object],
    ) -> PublishingStageState:
        if isinstance(payload, PublishingStageState):
            return payload.model_copy(update={"stage": stage})
        return PublishingStageState.model_validate({**payload, "stage": stage})

    def write_publishing_glossary(self, glossary: dict[str, str]) -> None:
        self._write_publishing_json(self.publishing_glossary_path, glossary)

    def write_publishing_names(self, names: dict[str, str]) -> None:
        self._write_publishing_json(self.publishing_names_path, names)

    def write_publishing_decisions(self, decisions: list[dict[str, object]]) -> None:
        self._write_publishing_json(self.publishing_decisions_path, decisions)

    def _write_publishing_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
