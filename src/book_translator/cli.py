from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from book_translator.config import RunConfig
from book_translator.pipeline import discover_books, process_book

app = typer.Typer(
    name="book-translator",
    help="Translate text-based PDF and EPUB books into Simplified Chinese.",
    add_completion=False,
)
console = Console()
DEFAULT_OUTPUT_PATH = Path("out")


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
) -> None:
    """Translate text-based PDF and EPUB books into Simplified Chinese."""
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
