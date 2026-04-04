from __future__ import annotations

import json
import shutil
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
        self.publishing_candidate_root_path = self.publishing_root_path / "candidate"
        self.publishing_manifest_path = self.publishing_root_path / "manifest.json"
        self.publishing_state_dir = self.publishing_root_path / "state"
        self.publishing_candidate_state_dir = self.publishing_candidate_root_path / "state"
        self.publishing_draft_dir = self.publishing_root_path / "draft"
        self.publishing_lexicon_dir = self.publishing_root_path / "lexicon"
        self.publishing_revision_dir = self.publishing_root_path / "revision"
        self.publishing_proofread_dir = self.publishing_root_path / "proofread"
        self.publishing_final_dir = self.publishing_root_path / "final"
        self.publishing_candidate_final_dir = self.publishing_candidate_root_path / "final"
        self.publishing_deep_review_dir = self.publishing_root_path / "deep_review"
        self.publishing_audit_dir = self.publishing_root_path / "audit"
        self.publishing_assets_dir = self.publishing_root_path / "assets"
        self.publishing_draft_chapters_path = self.publishing_draft_dir / "chapters.jsonl"
        self.publishing_draft_text_path = self.publishing_draft_dir / "draft.txt"
        self.publishing_glossary_path = self.publishing_lexicon_dir / "glossary.json"
        self.publishing_names_path = self.publishing_lexicon_dir / "names.json"
        self.publishing_decisions_path = self.publishing_lexicon_dir / "decisions.json"
        self.publishing_revision_chapters_path = (
            self.publishing_revision_dir / "revised_chapters.jsonl"
        )
        self.publishing_proofread_notes_path = (
            self.publishing_proofread_dir / "proofread_notes.jsonl"
        )
        self.publishing_proofread_changes_path = (
            self.publishing_proofread_dir / "proofread_changes.jsonl"
        )
        self.publishing_final_chapters_path = self.publishing_final_dir / "final_chapters.jsonl"
        self.publishing_final_text_path = self.publishing_final_dir / "translated.txt"
        self.publishing_candidate_final_text_path = (
            self.publishing_candidate_final_dir / "translated.txt"
        )
        self.publishing_final_pdf_path = self.publishing_final_dir / "translated.pdf"
        self.publishing_candidate_final_pdf_path = (
            self.publishing_candidate_final_dir / "translated.pdf"
        )
        self.publishing_final_epub_path = self.publishing_final_dir / "translated.epub"
        self.publishing_candidate_final_epub_path = (
            self.publishing_candidate_final_dir / "translated.epub"
        )
        self.publishing_deep_review_findings_path = (
            self.publishing_deep_review_dir / "findings.jsonl"
        )
        self.publishing_deep_review_chapters_path = (
            self.publishing_deep_review_dir / "revised_chapters.jsonl"
        )
        self.publishing_deep_review_decisions_path = (
            self.publishing_deep_review_dir / "decisions.json"
        )
        self.publishing_editorial_log_path = self.publishing_root_path / "editorial_log.json"
        self.publishing_summary_path = self.publishing_root_path / "run_summary.json"
        self.publishing_qa_root_path = self.publishing_root_path / "qa"
        self.publishing_qa_pages_path = self.publishing_qa_root_path / "pages"
        self.publishing_qa_summary_path = self.publishing_qa_root_path / "qa_summary.json"
        self.publishing_audit_source_path = self.publishing_audit_dir / "source_audit.jsonl"
        self.publishing_audit_review_path = self.publishing_audit_dir / "review_audit.jsonl"
        self.publishing_audit_consensus_path = self.publishing_audit_dir / "consensus.json"
        self.publishing_audit_report_path = self.publishing_audit_dir / "final_audit_report.json"
        self.publishing_final_gate_report_path = (
            self.publishing_audit_dir / "final_gate_report.json"
        )
        self.publishing_quality_score_path = self.publishing_audit_dir / "quality_score.json"
        self.publishing_unresolved_findings_path = (
            self.publishing_audit_dir / "unresolved_findings.jsonl"
        )
        self.publishing_assets_manifest_path = self.publishing_assets_dir / "manifest.json"
        self.publishing_assets_images_dir = self.publishing_assets_dir / "images"

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
        state_dir = self._publishing_state_dir_for(stage)
        state_dir.mkdir(parents=True, exist_ok=True)
        data = self._normalize_publishing_stage_state(stage=stage, payload=payload)
        state_dir.joinpath(f"{stage}.json").write_text(
            data.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def read_publishing_stage_state(self, stage: str) -> PublishingStageState | None:
        state_path = self._publishing_state_path(stage)
        if not state_path.exists():
            legacy_path = self.publishing_state_dir / f"{stage}.json"
            if legacy_path == state_path or not legacy_path.exists():
                return None
            state_path = legacy_path
        return PublishingStageState.model_validate_json(state_path.read_text(encoding="utf-8"))

    def stage_is_stale(self, stage: str, *, upstream_fingerprint: str) -> bool:
        current = self.read_publishing_stage_state(stage)
        if current is None:
            return True
        return current.status != "complete" or current.fingerprint != upstream_fingerprint

    def clear_publishing_stage_outputs(self, stage: str) -> None:
        stage_paths = {
            "draft": [
                self.publishing_draft_chapters_path,
                self.publishing_draft_text_path,
            ],
            "lexicon": [
                self.publishing_glossary_path,
                self.publishing_names_path,
                self.publishing_decisions_path,
            ],
            "revision": [self.publishing_revision_chapters_path],
            "proofread": [
                self.publishing_proofread_notes_path,
                self.publishing_proofread_changes_path,
            ],
            "final-review": [
                self.publishing_final_chapters_path,
                self.publishing_editorial_log_path,
                self.publishing_candidate_final_text_path,
                self.publishing_candidate_final_pdf_path,
                self.publishing_candidate_final_epub_path,
            ],
            "deep-review": [
                self.publishing_deep_review_findings_path,
                self.publishing_deep_review_chapters_path,
                self.publishing_deep_review_decisions_path,
                self.publishing_audit_source_path,
                self.publishing_audit_review_path,
                self.publishing_audit_consensus_path,
                self.publishing_audit_report_path,
                self.publishing_final_gate_report_path,
                self.publishing_quality_score_path,
                self.publishing_unresolved_findings_path,
                self.publishing_candidate_final_text_path,
                self.publishing_candidate_final_pdf_path,
                self.publishing_candidate_final_epub_path,
            ],
        }
        for path in stage_paths.get(stage, []):
            if path.exists():
                path.unlink()

        self._clear_publishing_stage_state(stage)

    def promote_candidate_release(self) -> None:
        candidate_to_final = [
            (self.publishing_candidate_final_text_path, self.publishing_final_text_path),
            (self.publishing_candidate_final_pdf_path, self.publishing_final_pdf_path),
            (self.publishing_candidate_final_epub_path, self.publishing_final_epub_path),
        ]
        for source, destination in candidate_to_final:
            if source.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            elif destination.exists():
                destination.unlink()

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

    def write_publishing_manifest(self, manifest: Manifest) -> None:
        self.publishing_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.publishing_manifest_path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def read_publishing_manifest(self) -> Manifest:
        return Manifest.model_validate_json(
            self.publishing_manifest_path.read_text(encoding="utf-8")
        )

    def write_publishing_summary(self, summary: dict[str, object]) -> None:
        self._write_publishing_json(self.publishing_summary_path, summary)

    def read_publishing_summary(self) -> dict[str, object]:
        if not self.publishing_summary_path.exists():
            return {}
        return json.loads(self.publishing_summary_path.read_text(encoding="utf-8"))

    def write_publishing_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")

    def read_publishing_jsonl(self, path: Path) -> list[dict[str, object]]:
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _publishing_state_dir_for(self, stage: str) -> Path:
        if stage in {"final-review", "deep-review"}:
            return self.publishing_candidate_state_dir
        return self.publishing_state_dir

    def _publishing_state_path(self, stage: str) -> Path:
        return self._publishing_state_dir_for(stage) / f"{stage}.json"

    def _clear_publishing_stage_state(self, stage: str) -> None:
        state_paths = [self._publishing_state_path(stage)]
        legacy_path = self.publishing_state_dir / f"{stage}.json"
        if legacy_path not in state_paths:
            state_paths.append(legacy_path)
        for path in state_paths:
            if path.exists():
                path.unlink()
