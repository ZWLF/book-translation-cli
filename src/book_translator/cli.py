from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from book_translator.config import RunConfig
from book_translator.output.pdf_raster import (
    choose_sample_pages,
    parse_page_spec,
    pdf_page_count,
    render_pdf_pages,
    write_qa_summary,
)
from book_translator.output.polished_pdf import build_printable_book, render_polished_pdf
from book_translator.output.title_enrichment import enrich_missing_titles
from book_translator.pipeline import discover_books, process_book
from book_translator.state.workspace import Workspace

app = typer.Typer(
    name="book-translator",
    help="Translate text-based PDF and EPUB books into Simplified Chinese.",
    add_completion=False,
)
console = Console()
DEFAULT_OUTPUT_PATH = Path("out")


def _run_async_sync(awaitable):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(awaitable)).result()


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    input_path: Annotated[
        Path | None,
        typer.Option("--input", exists=True, file_okay=True, dir_okay=True),
    ] = None,
    output_path: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT_PATH,
    provider: Annotated[str, typer.Option("--provider")] = "openai",
    model: Annotated[str | None, typer.Option("--model")] = None,
    api_key_env: Annotated[str | None, typer.Option("--api-key-env")] = None,
    max_concurrency: Annotated[int, typer.Option("--max-concurrency", min=1)] = 5,
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = True,
    force: Annotated[bool, typer.Option("--force")] = False,
    glossary: Annotated[
        Path | None,
        typer.Option("--glossary", exists=True, file_okay=True, dir_okay=False),
    ] = None,
    name_map: Annotated[
        Path | None,
        typer.Option("--name-map", exists=True, file_okay=True, dir_okay=False),
    ] = None,
    chapter_strategy: Annotated[str, typer.Option("--chapter-strategy")] = "toc-first",
    manual_toc: Annotated[
        Path | None,
        typer.Option("--manual-toc", exists=True, file_okay=True, dir_okay=False),
    ] = None,
    chunk_size: Annotated[int, typer.Option("--chunk-size", min=100)] = 3000,
    render_pdf: Annotated[bool, typer.Option("--render-pdf/--no-render-pdf")] = True,
) -> None:
    """Translate text-based PDF and EPUB books into Simplified Chinese."""
    if ctx.invoked_subcommand is not None:
        return
    if input_path is None:
        if ctx.resilient_parsing:
            return
        console.print(ctx.get_help())
        raise typer.Exit(code=0)

    config = RunConfig(
        provider=provider,
        model=model,
        api_key_env=api_key_env,
        max_concurrency=max_concurrency,
        resume=resume,
        force=force,
        glossary_path=glossary,
        name_map_path=name_map,
        chapter_strategy=chapter_strategy,
        manual_toc_path=manual_toc,
        chunk_size=chunk_size,
        render_pdf=render_pdf,
    )
    asyncio.run(_run_cli(input_path=input_path, output_path=output_path, config=config))


async def _run_cli(*, input_path: Path, output_path: Path, config: RunConfig) -> None:
    books = discover_books(input_path)
    if not books:
        raise typer.BadParameter(f"No supported .pdf or .epub files found under {input_path}.")

    output_path.mkdir(parents=True, exist_ok=True)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Processing books", total=len(books))
        for book in books:
            summary = await process_book(input_path=book, output_root=output_path, config=config)
            progress.advance(task_id)
            console.print(
                f"[green]{book.name}[/green] "
                f"chunks={summary.successful_chunks}/{summary.total_chunks} "
                f"failed={summary.failed_chunks} cost~=${summary.estimated_cost_usd:.6f}"
            )


def main() -> None:
    app()


@app.command("render-pdf")
def render_pdf_command(
    workspace_path: Annotated[
        Path,
        typer.Option("--workspace", exists=True, file_okay=False, dir_okay=True),
    ],
    output_path: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    """Render a polished PDF from an existing translation workspace."""
    workspace = Workspace(workspace_path)
    manifest = workspace.read_manifest()
    chunks = workspace.load_chunks()
    translations = workspace.load_translations()
    summary = workspace.read_summary()
    printable_book = build_printable_book(
        manifest=manifest,
        summary=summary,
        chunks=chunks,
        translations=translations,
    )
    api_key: str | None = None
    try:
        api_key = RunConfig(provider=manifest.provider, model=manifest.model).resolved_api_key()
    except ValueError:
        api_key = None
    printable_book = _run_async_sync(
        enrich_missing_titles(
            book=printable_book,
            workspace=workspace,
            provider_name=manifest.provider,
            model=manifest.model,
            api_key=api_key,
        )
    )
    target_path = output_path or workspace.pdf_output_path
    render_polished_pdf(printable_book, target_path)
    console.print(f"[green]Rendered polished PDF[/green] {target_path}")


@app.command("render-pages")
def render_pages_command(
    pdf_path: Annotated[
        Path,
        typer.Option("--pdf", exists=True, file_okay=True, dir_okay=False),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir")] ,
    pages: Annotated[str | None, typer.Option("--pages")] = None,
    dpi: Annotated[int, typer.Option("--dpi", min=72)] = 144,
) -> None:
    """Rasterize selected PDF pages into PNG files."""
    total_pages = pdf_page_count(pdf_path)
    selected_pages = (
        parse_page_spec(pages, total_pages=total_pages)
        if pages
        else list(range(1, total_pages + 1))
    )
    rendered = render_pdf_pages(
        pdf_path=pdf_path,
        output_dir=output_dir,
        pages=selected_pages,
        dpi=dpi,
    )
    console.print(
        f"[green]Rendered {len(rendered)} page(s)[/green] from {pdf_path} into {output_dir}"
    )


@app.command("qa-pdf")
def qa_pdf_command(
    workspace_path: Annotated[
        Path,
        typer.Option("--workspace", exists=True, file_okay=False, dir_okay=True),
    ],
    pages: Annotated[str | None, typer.Option("--pages")] = None,
    all_pages: Annotated[bool, typer.Option("--all-pages")] = False,
    dpi: Annotated[int, typer.Option("--dpi", min=72)] = 144,
    output_dir: Annotated[Path | None, typer.Option("--output-dir")] = None,
) -> None:
    """Generate PNG screenshots for visual QA from a rendered workspace PDF."""
    workspace = Workspace(workspace_path)
    pdf_path = workspace.pdf_output_path
    if not pdf_path.exists():
        raise typer.BadParameter(f"Workspace PDF does not exist: {pdf_path}")

    total_pages = pdf_page_count(pdf_path)
    if pages:
        selected_pages = parse_page_spec(pages, total_pages=total_pages)
    elif all_pages:
        selected_pages = list(range(1, total_pages + 1))
    else:
        selected_pages = choose_sample_pages(total_pages)

    target_dir = output_dir or workspace.qa_pages_path
    rendered = render_pdf_pages(
        pdf_path=pdf_path,
        output_dir=target_dir,
        pages=selected_pages,
        dpi=dpi,
    )
    summary_path = workspace.qa_summary_path
    write_qa_summary(
        pdf_path=pdf_path,
        summary_path=summary_path,
        output_dir=target_dir,
        total_pages=total_pages,
        rendered_pages=rendered,
        dpi=dpi,
    )
    console.print(
        f"[green]Generated {len(rendered)} QA page(s)[/green] in {target_dir} "
        f"(summary: {summary_path})"
    )
