from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from book_translator.chaptering.detect import detect_chapters
from book_translator.chaptering.manual_toc import load_manual_toc_titles
from book_translator.chunking.splitter import split_chapter_into_chunks
from book_translator.config import RunConfig
from book_translator.extractors.epub import extract_epub
from book_translator.extractors.pdf import extract_pdf
from book_translator.models import BookRunSummary, Manifest
from book_translator.output.assembler import assemble_output_text
from book_translator.output.polished_pdf import build_printable_book, render_polished_pdf
from book_translator.output.title_enrichment import enrich_missing_titles
from book_translator.providers.base import BaseProvider
from book_translator.providers.gemini_provider import GeminiProvider
from book_translator.providers.openai_provider import OpenAIProvider
from book_translator.state.workspace import Workspace
from book_translator.translation.orchestrator import translate_chunks
from book_translator.utils import file_fingerprint, slugify


def discover_books(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    supported: list[Path] = []
    for path in input_path.rglob("*"):
        if path.suffix.lower() in {".pdf", ".epub"}:
            supported.append(path)
    return sorted(supported)


async def process_book(
    *,
    input_path: Path,
    output_root: Path,
    config: RunConfig,
    provider: BaseProvider | None = None,
) -> BookRunSummary:
    started = time.perf_counter()
    book_id = slugify(input_path.stem)
    workspace = Workspace(output_root / book_id)

    if config.force and workspace.root.exists():
        shutil.rmtree(workspace.root)

    fingerprint = file_fingerprint(input_path)
    manifest = Manifest(
        book_id=book_id,
        source_path=str(input_path),
        source_fingerprint=fingerprint,
        provider=config.provider,
        model=config.resolved_model(),
        config_fingerprint=config.config_fingerprint(),
    )

    if workspace.manifest_path.exists() and config.resume and not config.force:
        workspace.assert_resume_compatible(
            source_fingerprint=fingerprint,
            provider=config.provider,
            model=config.resolved_model(),
            config_fingerprint=config.config_fingerprint(),
        )
    else:
        workspace.initialize(manifest)

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
    workspace.write_chunks(chunks)

    completed = workspace.completed_chunk_ids() if config.resume and not config.force else set()
    pending_chunks = [chunk for chunk in chunks if chunk.chunk_id not in completed]

    glossary = _load_mapping(config.glossary_path)
    name_map = _load_mapping(config.name_map_path)
    provider_instance = provider or _build_provider(config)
    try:
        results, errors = await translate_chunks(
            book_title=extracted.title,
            chunks=pending_chunks,
            provider=provider_instance,
            glossary=glossary,
            name_map=name_map,
            max_concurrency=config.max_concurrency,
            max_attempts=config.max_attempts,
        )
        for result in results:
            workspace.append_translation(result)
        workspace.write_errors(errors)

        translations = workspace.load_translations()
        output_text = assemble_output_text(
            chapters=chapters,
            chunks=chunks,
            translations=translations,
            failed_chunk_ids={str(error["chunk_id"]) for error in errors},
        )
        workspace.output_path.write_text(output_text, encoding="utf-8")

        successful_chunks = len(translations)
        failed_chunks = len(errors)
        input_tokens = sum(result.input_tokens for result in translations.values())
        output_tokens = sum(result.output_tokens for result in translations.values())
        total_cost = sum(result.estimated_cost_usd for result in translations.values())
        duration_seconds = time.perf_counter() - started
        avg_latency = (
            sum(result.latency_ms for result in translations.values()) / successful_chunks
            if successful_chunks
            else 0.0
        )
        summary = BookRunSummary(
            source_path=str(input_path),
            provider=config.provider,
            model=config.resolved_model(),
            total_chapters=len(chapters),
            total_chunks=len(chunks),
            successful_chunks=successful_chunks,
            failed_chunks=failed_chunks,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost_usd=round(total_cost, 6),
            duration_seconds=round(duration_seconds, 3),
            avg_chunk_latency_ms=round(avg_latency, 3),
        )
        workspace.write_summary(summary.model_dump())
        if config.render_pdf and successful_chunks:
            printable_book = build_printable_book(
                manifest=workspace.read_manifest(),
                summary=summary.model_dump(),
                chunks=chunks,
                translations=translations,
            )
            printable_book = await enrich_missing_titles(
                book=printable_book,
                workspace=workspace,
                provider_name=config.provider,
                model=config.resolved_model(),
                api_key=config.resolved_api_key() if provider is None else None,
                max_concurrency=config.max_concurrency,
                max_attempts=config.max_attempts,
            )
            render_polished_pdf(printable_book, workspace.pdf_output_path)
        return summary
    finally:
        if provider is None:
            await provider_instance.aclose()


def _extract_book(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".epub":
        return extract_epub(path)
    raise ValueError(f"Unsupported input file type: {path.suffix}")


def _load_mapping(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Mapping file {path} must contain a JSON object.")
    return {str(key): str(value) for key, value in data.items()}


def _build_provider(config: RunConfig) -> BaseProvider:
    if config.provider == "openai":
        return OpenAIProvider(api_key=config.resolved_api_key(), model=config.resolved_model())
    if config.provider == "gemini":
        return GeminiProvider(api_key=config.resolved_api_key(), model=config.resolved_model())
    raise ValueError(f"Unsupported provider: {config.provider}")
