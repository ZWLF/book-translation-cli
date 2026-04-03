from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

from book_translator.chaptering.detect import detect_chapters
from book_translator.chaptering.manual_toc import load_manual_toc_titles
from book_translator.chunking.splitter import split_chapter_into_chunks
from book_translator.config import PUBLISHING_STAGES, PublishingRunConfig
from book_translator.models import Chapter, Manifest, PublishingChapterArtifact
from book_translator.output.assembler import assemble_publishing_output_text
from book_translator.output.polished_pdf import (
    build_printable_book_from_artifacts,
    render_polished_pdf,
)
from book_translator.output.title_enrichment import enrich_missing_titles
from book_translator.pipeline import _build_provider, _extract_book, _load_mapping
from book_translator.providers.base import BaseProvider
from book_translator.publishing.deep_review import (
    DEEP_REVIEW_STAGE_VERSION,
    run_deep_review,
)
from book_translator.publishing.final_review import (
    FINAL_REVIEW_STAGE_VERSION,
    apply_final_review,
)
from book_translator.publishing.lexicon import merge_lexicon_overrides, normalize_lexicon_records
from book_translator.publishing.proofread import PROOFREAD_STAGE_VERSION, proofread_chapter
from book_translator.publishing.revision import revise_chapter
from book_translator.state.workspace import Workspace
from book_translator.translation.orchestrator import translate_chunks
from book_translator.utils import file_fingerprint, slugify


async def process_book_publishing(
    *,
    input_path: Path,
    output_root: Path,
    config: PublishingRunConfig,
    provider: BaseProvider | None = None,
) -> dict[str, object]:
    started = time.perf_counter()
    book_id = slugify(input_path.stem)
    workspace = Workspace(output_root / book_id)

    if config.force and workspace.publishing_root_path.exists():
        shutil.rmtree(workspace.publishing_root_path)

    source_fingerprint = file_fingerprint(input_path)
    manifest = Manifest(
        book_id=book_id,
        source_path=str(input_path),
        source_fingerprint=source_fingerprint,
        provider=config.provider,
        model=config.resolved_model(),
        config_fingerprint=config.config_fingerprint(),
    )
    _initialize_publishing_manifest(workspace=workspace, manifest=manifest, config=config)

    extracted = _extract_book(input_path)
    manual_titles = (
        load_manual_toc_titles(config.manual_toc_path)
        if config.manual_toc_path and config.chapter_strategy == "manual"
        else None
    )
    chapters = detect_chapters(
        extracted,
        strategy=config.chapter_strategy,
        manual_titles=manual_titles,
    )
    chunks = [
        chunk
        for chapter in chapters
        for chunk in split_chapter_into_chunks(chapter, config.chunk_size)
    ]

    glossary_overrides = _load_mapping(config.glossary_path)
    name_overrides = _load_mapping(config.name_map_path)
    previous_summary = workspace.read_publishing_summary() if config.resume else {}
    metrics = {
        "successful_chunks": int(previous_summary.get("successful_chunks", 0)),
        "failed_chunks": int(previous_summary.get("failed_chunks", 0)),
        "estimated_input_tokens": int(previous_summary.get("estimated_input_tokens", 0)),
        "estimated_output_tokens": int(previous_summary.get("estimated_output_tokens", 0)),
        "estimated_cost_usd": float(previous_summary.get("estimated_cost_usd", 0.0)),
    }

    provider_instance = provider or _build_provider(config)
    try:
        draft_artifacts = await _ensure_draft_stage(
            workspace=workspace,
            manifest=manifest,
            extracted_title=extracted.title,
            chapters=chapters,
            chunks=chunks,
            glossary=glossary_overrides,
            name_map=name_overrides,
            provider=provider_instance,
            config=config,
            metrics=metrics,
        )
        glossary, names, decisions = _ensure_lexicon_stage(
            workspace=workspace,
            draft_artifacts=draft_artifacts,
            glossary_overrides=glossary_overrides,
            name_overrides=name_overrides,
            config=config,
        )
        revised_artifacts = _ensure_revision_stage(
            workspace=workspace,
            draft_artifacts=draft_artifacts,
            glossary=glossary,
            names=names,
            config=config,
        )
        proofread_artifacts, proofread_notes = _ensure_proofread_stage(
            workspace=workspace,
            revised_artifacts=revised_artifacts,
            config=config,
        )
        final_artifacts, editorial_log = await _ensure_final_review_stage(
            workspace=workspace,
            manifest=manifest,
            proofread_artifacts=proofread_artifacts,
            config=config,
            provider=provider,
            summary_metrics=metrics,
        )
        (
            deep_review_artifacts,
            deep_review_findings,
            deep_review_decisions,
            deep_review_revised_count,
        ) = (
            await _ensure_deep_review_stage(
                workspace=workspace,
                manifest=manifest,
                source_chapters=chapters,
                final_artifacts=final_artifacts,
                config=config,
                provider=provider,
                summary_metrics=metrics,
            )
        )

        completed_stage = config.to_stage
        if _stage_index("deep-review") > _stage_index(config.to_stage):
            deep_review_findings = []
            deep_review_decisions = {}
            deep_review_revised_count = 0
        if _stage_index("final-review") > _stage_index(config.to_stage):
            editorial_log = []
        if _stage_index("proofread") > _stage_index(config.to_stage):
            proofread_notes = []
        if _stage_index("lexicon") > _stage_index(config.to_stage):
            decisions = []

        summary = {
            "mode": "publishing",
            "style": config.style,
            "provider": config.provider,
            "model": config.resolved_model(),
            "source_path": str(input_path),
            "total_chapters": len(chapters),
            "total_chunks": len(chunks),
            "successful_chunks": metrics["successful_chunks"],
            "failed_chunks": metrics["failed_chunks"],
            "estimated_input_tokens": metrics["estimated_input_tokens"],
            "estimated_output_tokens": metrics["estimated_output_tokens"],
            "estimated_cost_usd": round(metrics["estimated_cost_usd"], 6),
            "duration_seconds": round(time.perf_counter() - started, 3),
            "started_stage": config.from_stage,
            "completed_stage": completed_stage,
            "render_pdf": bool(
                config.render_pdf and _stage_index(config.to_stage) >= _stage_index("final-review")
            ),
            "editorial_log_entries": len(editorial_log),
            "proofread_notes": len(proofread_notes),
            "decision_count": len(decisions),
            "deep_review_findings": len(deep_review_findings),
            "deep_review_revised_chapters": deep_review_revised_count,
            "deep_review_decisions": len(
                deep_review_decisions.get("chapters", [])
                if isinstance(deep_review_decisions, dict)
                else []
            ),
        }
        workspace.write_publishing_summary(summary)
        return summary
    finally:
        if provider is None:
            await provider_instance.aclose()


def _initialize_publishing_manifest(
    *,
    workspace: Workspace,
    manifest: Manifest,
    config: PublishingRunConfig,
) -> None:
    if workspace.publishing_manifest_path.exists() and config.resume and not config.force:
        existing = workspace.read_publishing_manifest()
        if (
            existing.source_fingerprint != manifest.source_fingerprint
            or existing.provider != manifest.provider
            or existing.model != manifest.model
            or existing.config_fingerprint != manifest.config_fingerprint
        ):
            raise ValueError("Existing publishing state is incompatible. Re-run with --force.")
    workspace.write_publishing_manifest(manifest)


async def _ensure_draft_stage(
    *,
    workspace: Workspace,
    manifest: Manifest,
    extracted_title: str,
    chapters: list[Any],
    chunks: list[Any],
    glossary: dict[str, str],
    name_map: dict[str, str],
    provider: BaseProvider,
    config: PublishingRunConfig,
    metrics: dict[str, float | int],
) -> list[PublishingChapterArtifact]:
    stage = "draft"
    fingerprint = _fingerprint_payload(
        {
            "source_fingerprint": manifest.source_fingerprint,
            "config_fingerprint": manifest.config_fingerprint,
            "style": config.style,
        }
    )
    if _stage_index(stage) < _stage_index(config.from_stage):
        artifacts = _load_publishing_artifacts(workspace.publishing_draft_chapters_path, workspace)
        if not artifacts:
            raise ValueError("Draft artifacts are missing. Re-run from the draft stage.")
        return artifacts

    required_paths = [
        workspace.publishing_draft_chapters_path,
        workspace.publishing_draft_text_path,
    ]
    if not _should_run_stage(
        workspace=workspace,
        stage=stage,
        fingerprint=fingerprint,
        config=config,
        required_paths=required_paths,
    ):
        return _load_publishing_artifacts(workspace.publishing_draft_chapters_path, workspace)

    _clear_stage_and_downstream(workspace, stage)
    results, errors = await translate_chunks(
        book_title=extracted_title,
        chunks=chunks,
        provider=provider,
        glossary=glossary,
        name_map=name_map,
        max_concurrency=config.max_concurrency,
        max_attempts=config.max_attempts,
    )
    translations = {result.chunk_id: result for result in results}
    artifacts = _build_chapter_artifacts_from_translations(
        chapters=chapters,
        chunks=chunks,
        translations=translations,
        failed_chunk_ids={str(item["chunk_id"]) for item in errors},
    )
    workspace.write_publishing_jsonl(
        workspace.publishing_draft_chapters_path,
        [artifact.model_dump() for artifact in artifacts],
    )
    workspace.publishing_draft_text_path.parent.mkdir(parents=True, exist_ok=True)
    workspace.publishing_draft_text_path.write_text(
        assemble_publishing_output_text(artifacts),
        encoding="utf-8",
    )
    workspace.write_publishing_stage_state(
        stage,
        {
            "fingerprint": fingerprint,
            "status": "complete",
        },
    )
    metrics["successful_chunks"] = len(results)
    metrics["failed_chunks"] = len(errors)
    metrics["estimated_input_tokens"] = sum(result.input_tokens for result in results)
    metrics["estimated_output_tokens"] = sum(result.output_tokens for result in results)
    metrics["estimated_cost_usd"] = float(sum(result.estimated_cost_usd for result in results))
    return artifacts


def _ensure_lexicon_stage(
    *,
    workspace: Workspace,
    draft_artifacts: list[PublishingChapterArtifact],
    glossary_overrides: dict[str, str],
    name_overrides: dict[str, str],
    config: PublishingRunConfig,
) -> tuple[dict[str, str], dict[str, str], list[dict[str, object]]]:
    stage = "lexicon"
    fingerprint = _fingerprint_payload(
        {
            "draft_stage": workspace.read_publishing_stage_state("draft").model_dump(),
            "style": config.style,
            "glossary_overrides": glossary_overrides,
            "name_overrides": name_overrides,
        }
    )
    if _stage_index(stage) < _stage_index(config.from_stage):
        glossary = _load_dict_file(workspace.publishing_glossary_path)
        names = _load_dict_file(workspace.publishing_names_path)
        decisions = _load_json_array(workspace.publishing_decisions_path)
        if not any(
            path.exists()
            for path in (
                workspace.publishing_glossary_path,
                workspace.publishing_names_path,
                workspace.publishing_decisions_path,
            )
        ):
            raise ValueError("Lexicon artifacts are missing. Re-run from the lexicon stage.")
        return glossary, names, decisions

    required_paths = [
        workspace.publishing_glossary_path,
        workspace.publishing_names_path,
        workspace.publishing_decisions_path,
    ]
    if not _should_run_stage(
        workspace=workspace,
        stage=stage,
        fingerprint=fingerprint,
        config=config,
        required_paths=required_paths,
    ):
        return (
            _load_dict_file(workspace.publishing_glossary_path),
            _load_dict_file(workspace.publishing_names_path),
            _load_json_array(workspace.publishing_decisions_path),
        )

    _clear_stage_and_downstream(workspace, stage)
    generated_glossary: dict[str, str] = {}
    generated_names: dict[str, str] = {}
    glossary = merge_lexicon_overrides(generated_glossary, glossary_overrides)
    names = merge_lexicon_overrides(generated_names, name_overrides)
    decisions = normalize_lexicon_records(
        [
            {"source": source, "translation": translation}
            for source, translation in {**glossary, **names}.items()
        ]
    )
    workspace.write_publishing_glossary(glossary)
    workspace.write_publishing_names(names)
    workspace.write_publishing_decisions(decisions)
    workspace.write_publishing_stage_state(
        stage,
        {
            "fingerprint": fingerprint,
            "status": "complete",
        },
    )
    return glossary, names, decisions


def _ensure_revision_stage(
    *,
    workspace: Workspace,
    draft_artifacts: list[PublishingChapterArtifact],
    glossary: dict[str, str],
    names: dict[str, str],
    config: PublishingRunConfig,
) -> list[PublishingChapterArtifact]:
    stage = "revision"
    fingerprint = _fingerprint_payload(
        {
            "lexicon_stage": workspace.read_publishing_stage_state("lexicon").model_dump(),
            "style": config.style,
        }
    )
    if _stage_index(stage) < _stage_index(config.from_stage):
        artifacts = _load_publishing_artifacts(
            workspace.publishing_revision_chapters_path,
            workspace,
        )
        if not artifacts:
            raise ValueError("Revision artifacts are missing. Re-run from the revision stage.")
        return artifacts

    required_paths = [workspace.publishing_revision_chapters_path]
    if not _should_run_stage(
        workspace=workspace,
        stage=stage,
        fingerprint=fingerprint,
        config=config,
        required_paths=required_paths,
    ):
        return _load_publishing_artifacts(workspace.publishing_revision_chapters_path, workspace)

    _clear_stage_and_downstream(workspace, stage)
    artifacts = [
        revise_chapter(
            chapter_id=chapter.chapter_id,
            chapter_index=chapter.chapter_index,
            title=chapter.title,
            draft_text=chapter.text,
            style_name=config.style,
            glossary=glossary,
            names=names,
        )
        for chapter in draft_artifacts
    ]
    workspace.write_publishing_jsonl(
        workspace.publishing_revision_chapters_path,
        [artifact.model_dump() for artifact in artifacts],
    )
    workspace.write_publishing_stage_state(
        stage,
        {
            "fingerprint": fingerprint,
            "status": "complete",
        },
    )
    return artifacts


def _ensure_proofread_stage(
    *,
    workspace: Workspace,
    revised_artifacts: list[PublishingChapterArtifact],
    config: PublishingRunConfig,
) -> tuple[list[PublishingChapterArtifact], list[dict[str, object]]]:
    stage = "proofread"
    fingerprint = _fingerprint_payload(
        {
            "revision_stage": workspace.read_publishing_stage_state("revision").model_dump(),
            "style": config.style,
            "proofread_stage_version": PROOFREAD_STAGE_VERSION,
        }
    )
    if _stage_index(stage) < _stage_index(config.from_stage):
        artifacts = _load_publishing_artifacts(
            workspace.publishing_proofread_changes_path,
            workspace,
        )
        notes = workspace.read_publishing_jsonl(workspace.publishing_proofread_notes_path)
        if not artifacts and not workspace.publishing_proofread_changes_path.exists():
            raise ValueError("Proofread artifacts are missing. Re-run from the proofread stage.")
        return artifacts, notes

    required_paths = [
        workspace.publishing_proofread_changes_path,
        workspace.publishing_proofread_notes_path,
    ]
    if not _should_run_stage(
        workspace=workspace,
        stage=stage,
        fingerprint=fingerprint,
        config=config,
        required_paths=required_paths,
    ):
        return (
            _load_publishing_artifacts(workspace.publishing_proofread_changes_path, workspace),
            workspace.read_publishing_jsonl(workspace.publishing_proofread_notes_path),
        )

    _clear_stage_and_downstream(workspace, stage)
    artifacts: list[PublishingChapterArtifact] = []
    notes: list[dict[str, object]] = []
    for chapter in revised_artifacts:
        final_artifact, chapter_notes = proofread_chapter(chapter)
        artifacts.append(final_artifact)
        for note in chapter_notes:
            notes.append({"chapter_id": chapter.chapter_id, **note})
    workspace.write_publishing_jsonl(
        workspace.publishing_proofread_changes_path,
        [artifact.model_dump() for artifact in artifacts],
    )
    workspace.write_publishing_jsonl(workspace.publishing_proofread_notes_path, notes)
    workspace.write_publishing_stage_state(
        stage,
        {
            "fingerprint": fingerprint,
            "status": "complete",
        },
    )
    return artifacts, notes


async def _ensure_final_review_stage(
    *,
    workspace: Workspace,
    manifest: Manifest,
    proofread_artifacts: list[PublishingChapterArtifact],
    config: PublishingRunConfig,
    provider: BaseProvider | None,
    summary_metrics: dict[str, float | int],
) -> tuple[list[PublishingChapterArtifact], list[dict[str, object]]]:
    stage = "final-review"
    if _stage_index(stage) > _stage_index(config.to_stage):
        return [], []

    fingerprint = _final_review_stage_fingerprint(
        workspace=workspace,
        config=config,
    )
    required_paths = [
        workspace.publishing_final_chapters_path,
        workspace.publishing_final_text_path,
        workspace.publishing_editorial_log_path,
    ]
    if config.render_pdf:
        required_paths.append(workspace.publishing_final_pdf_path)

    if not _should_run_stage(
        workspace=workspace,
        stage=stage,
        fingerprint=fingerprint,
        config=config,
        required_paths=required_paths,
    ):
        return (
            _load_publishing_artifacts(workspace.publishing_final_chapters_path, workspace),
            _load_json_array(workspace.publishing_editorial_log_path),
        )

    _clear_stage_and_downstream(workspace, stage)
    artifacts, editorial_log = apply_final_review(proofread_artifacts)
    workspace.write_publishing_jsonl(
        workspace.publishing_final_chapters_path,
        [artifact.model_dump() for artifact in artifacts],
    )
    workspace._write_publishing_json(workspace.publishing_editorial_log_path, editorial_log)
    await _rebuild_stable_publishing_outputs(
        workspace=workspace,
        manifest=manifest,
        chapters=artifacts,
        config=config,
        provider=provider,
        summary_metrics=summary_metrics,
    )
    completed_fingerprint = _final_review_stage_fingerprint(
        workspace=workspace,
        config=config,
    )

    workspace.write_publishing_stage_state(
        stage,
        {
            "fingerprint": completed_fingerprint,
            "status": "complete",
        },
    )
    return artifacts, editorial_log


async def _ensure_deep_review_stage(
    *,
    workspace: Workspace,
    manifest: Manifest,
    source_chapters: list[Chapter],
    final_artifacts: list[PublishingChapterArtifact],
    config: PublishingRunConfig,
    provider: BaseProvider | None,
    summary_metrics: dict[str, float | int],
) -> tuple[
    list[PublishingChapterArtifact],
    list[dict[str, object]],
    dict[str, object],
    int,
]:
    stage = "deep-review"
    if _stage_index(stage) > _stage_index(config.to_stage):
        return [], [], {}, 0
    if not final_artifacts and not workspace.publishing_final_chapters_path.exists():
        raise ValueError("Final-review artifacts are missing. Re-run from the final-review stage.")
    final_review_state = workspace.read_publishing_stage_state("final-review")
    if final_review_state is None:
        raise ValueError("Final-review state is missing. Re-run from the final-review stage.")

    fingerprint = _deep_review_stage_fingerprint(
        workspace=workspace,
        final_review_state=final_review_state,
        config=config,
    )
    required_paths = [
        workspace.publishing_deep_review_findings_path,
        workspace.publishing_deep_review_chapters_path,
        workspace.publishing_deep_review_decisions_path,
        workspace.publishing_final_text_path,
    ]
    if config.render_pdf:
        required_paths.append(workspace.publishing_final_pdf_path)

    if not _should_run_stage(
        workspace=workspace,
        stage=stage,
        fingerprint=fingerprint,
        config=config,
        required_paths=required_paths,
    ):
        decisions = _load_json_object(workspace.publishing_deep_review_decisions_path)
        return (
            _load_publishing_artifacts(workspace.publishing_deep_review_chapters_path, workspace),
            workspace.read_publishing_jsonl(workspace.publishing_deep_review_findings_path),
            decisions,
            int(decisions.get("revised_chapter_count", 0)),
        )

    _clear_stage_and_downstream(workspace, stage)
    result = run_deep_review(source_chapters=source_chapters, final_artifacts=final_artifacts)
    workspace.write_publishing_jsonl(
        workspace.publishing_deep_review_findings_path,
        [finding.model_dump() for finding in result.findings],
    )
    workspace.write_publishing_jsonl(
        workspace.publishing_deep_review_chapters_path,
        [artifact.model_dump() for artifact in result.revised_chapters],
    )
    workspace._write_publishing_json(
        workspace.publishing_deep_review_decisions_path,
        result.decisions,
    )
    await _rebuild_stable_publishing_outputs(
        workspace=workspace,
        manifest=manifest,
        chapters=final_artifacts,
        deep_review_chapters=result.revised_chapters,
        config=config,
        provider=provider,
        summary_metrics=summary_metrics,
    )
    completed_fingerprint = _deep_review_stage_fingerprint(
        workspace=workspace,
        final_review_state=final_review_state,
        config=config,
    )
    workspace.write_publishing_stage_state(
        stage,
        {
            "fingerprint": completed_fingerprint,
            "status": "complete",
        },
    )
    return (
        result.revised_chapters,
        [finding.model_dump() for finding in result.findings],
        result.decisions,
        result.revised_chapter_count,
    )


def _should_run_stage(
    *,
    workspace: Workspace,
    stage: str,
    fingerprint: str,
    config: PublishingRunConfig,
    required_paths: list[Path],
) -> bool:
    if _stage_index(stage) < _stage_index(config.from_stage):
        return False
    if _stage_index(stage) > _stage_index(config.to_stage):
        return False
    if config.force or not config.resume:
        return True
    if any(not path.exists() for path in required_paths):
        return True
    return workspace.stage_is_stale(stage, upstream_fingerprint=fingerprint)


def _clear_stage_and_downstream(workspace: Workspace, stage: str) -> None:
    for candidate in PUBLISHING_STAGES[_stage_index(stage) :]:
        workspace.clear_publishing_stage_outputs(candidate)


def _load_publishing_artifacts(
    path: Path,
    workspace: Workspace,
) -> list[PublishingChapterArtifact]:
    return [
        PublishingChapterArtifact.model_validate(record)
        for record in workspace.read_publishing_jsonl(path)
    ]


def _load_dict_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _load_json_array(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _load_json_object(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def _build_chapter_artifacts_from_translations(
    *,
    chapters: list[Any],
    chunks: list[Any],
    translations: dict[str, Any],
    failed_chunk_ids: set[str],
) -> list[PublishingChapterArtifact]:
    chunks_by_chapter: dict[str, list[Any]] = {}
    for chunk in chunks:
        chunks_by_chapter.setdefault(chunk.chapter_id, []).append(chunk)

    artifacts: list[PublishingChapterArtifact] = []
    for chapter in chapters:
        chapter_chunks = sorted(
            chunks_by_chapter.get(chapter.chapter_id, []),
            key=lambda item: item.chunk_index,
        )
        if not chapter_chunks:
            continue

        parts: list[str] = []
        for chunk in chapter_chunks:
            result = translations.get(chunk.chunk_id)
            if result is not None and str(result.translated_text).strip():
                parts.append(str(result.translated_text).strip())
            elif chunk.chunk_id in failed_chunk_ids:
                parts.append(f"[[翻译失败: {chapter.title} / chunk {chunk.chunk_index}]]")

        if not parts:
            continue
        artifacts.append(
            PublishingChapterArtifact(
                chapter_id=chapter.chapter_id,
                chapter_index=chapter.chapter_index,
                title=chapter.title,
                text="\n\n".join(parts).strip(),
            )
        )
    return artifacts


def _fingerprint_payload(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _stage_index(stage: str) -> int:
    return PUBLISHING_STAGES.index(stage)


def _title_translations_fingerprint(workspace: Workspace) -> str:
    return _fingerprint_payload(workspace.read_title_translations())


def _final_review_stage_fingerprint(
    *,
    workspace: Workspace,
    config: PublishingRunConfig,
) -> str:
    return _fingerprint_payload(
        {
            "proofread_stage": workspace.read_publishing_stage_state("proofread").model_dump(),
            "style": config.style,
            "final_review_stage_version": FINAL_REVIEW_STAGE_VERSION,
            "pdf_front_matter_version": "publishing-edition-v6",
            "title_translations_fingerprint": _title_translations_fingerprint(workspace),
        }
    )


def _deep_review_stage_fingerprint(
    *,
    workspace: Workspace,
    final_review_state: Any,
    config: PublishingRunConfig,
) -> str:
    return _fingerprint_payload(
        {
            "final_review_stage": final_review_state.model_dump(),
            "style": config.style,
            "deep_review_stage_version": DEEP_REVIEW_STAGE_VERSION,
            "title_translations_fingerprint": _title_translations_fingerprint(workspace),
        }
    )


async def _rebuild_stable_publishing_outputs(
    *,
    workspace: Workspace,
    manifest: Manifest,
    chapters: list[PublishingChapterArtifact],
    config: PublishingRunConfig,
    provider: BaseProvider | None,
    summary_metrics: dict[str, float | int],
    deep_review_chapters: list[PublishingChapterArtifact] | None = None,
) -> None:
    workspace.publishing_final_text_path.parent.mkdir(parents=True, exist_ok=True)
    workspace.publishing_final_text_path.write_text(
        assemble_publishing_output_text(
            chapters,
            deep_review_chapters=deep_review_chapters,
        ),
        encoding="utf-8",
    )

    if not config.render_pdf:
        return

    printable_book = build_printable_book_from_artifacts(
        manifest=manifest,
        summary={
            "estimated_cost_usd": summary_metrics["estimated_cost_usd"],
        },
        chapters=deep_review_chapters or chapters,
        title_overrides=workspace.read_title_translations(),
    )
    api_key: str | None = None
    try:
        api_key = config.resolved_api_key() if provider is None else None
    except ValueError:
        api_key = None
    printable_book = await enrich_missing_titles(
        book=printable_book,
        workspace=workspace,
        provider_name=config.provider,
        model=config.resolved_model(),
        api_key=api_key,
        max_concurrency=config.max_concurrency,
        max_attempts=config.max_attempts,
    )
    render_polished_pdf(
        printable_book,
        workspace.publishing_final_pdf_path,
        edition_label="publishing",
    )
