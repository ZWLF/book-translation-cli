from __future__ import annotations

import json
from pathlib import Path

from book_translator.models import Chunk, Manifest, TranslationResult


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest_path = self.root / "manifest.json"
        self.chunks_path = self.root / "chunks.jsonl"
        self.translations_path = self.root / "translations.jsonl"
        self.error_log_path = self.root / "error_log.json"
        self.summary_path = self.root / "run_summary.json"
        self.output_path = self.root / "translated.txt"

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
