from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from booksmith.app_services import (
    BookDiscoveryError,
    run_engineering_books_sync,
    run_publishing_books_sync,
)
from booksmith.config import PublishingRunConfig, RunConfig
from booksmith.output.pdf_raster import (
    choose_sample_pages,
    parse_page_spec,
    pdf_page_count,
    render_pdf_pages,
    write_qa_summary,
)
from booksmith.output.polished_pdf import build_printable_book, render_polished_pdf
from booksmith.output.title_enrichment import enrich_missing_titles
from booksmith.provider_catalog import (
    get_default_provider_option,
    list_enabled_provider_options,
)
from booksmith.state.workspace import Workspace

app = typer.Typer(
    name="booksmith",
    help="Booksmith translates text-based PDF and EPUB books into Simplified Chinese.",
    add_completion=False,
)
engineering_app = typer.Typer(help="Engineering workflows.")
publishing_app = typer.Typer(help="Publishing workflows.")
app.add_typer(engineering_app, name="engineering")
app.add_typer(publishing_app, name="publishing")
console = Console()
DEFAULT_OUTPUT_PATH = Path("out")

_ENABLED_PROVIDER_OPTIONS = tuple(list_enabled_provider_options())
_SUPPORTED_PROVIDER_IDS = ", ".join(option.provider_id for option in _ENABLED_PROVIDER_OPTIONS)


def _supports_spinner(target_console: Console) -> bool:
    encoding = getattr(target_console, "encoding", None) or "utf-8"
    try:
        "⠙".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _build_progress(*, description: str, total: int) -> tuple[Progress, int]:
    columns = []
    if _supports_spinner(console):
        columns.append(SpinnerColumn())
    columns.extend(
        [
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        ]
    )
    progress = Progress(*columns, console=console)
    task_id = progress.add_task(description, total=total)
    return progress, task_id


def _input_help_text() -> str:
    return "source file or directory scan root."


def _output_help_text() -> str:
    return "workspace root directory for generated artifacts and exports."


def _provider_help_text() -> str:
    default_provider = get_default_provider_option()
    return (
        f"Provider id from the shared catalog ({_SUPPORTED_PROVIDER_IDS}). "
        f"Default: {default_provider.provider_id}."
    )


def _model_help_text() -> str:
    return "Optional model override. Must match the selected provider catalog."


def _api_key_env_help_text() -> str:
    defaults = ", ".join(
        f"{option.provider_id}={option.api_key_env}" for option in _ENABLED_PROVIDER_OPTIONS
    )
    return (
        "Environment variable name for the provider API key. "
        f"Defaults follow the provider catalog ({defaults})."
    )


def _build_run_config(
    *,
    config_type: type[RunConfig] | type[PublishingRunConfig],
    provider: str,
    model: str | None,
    api_key_env: str | None,
    **config_kwargs: object,
) -> RunConfig | PublishingRunConfig:
    try:
        return config_type(
            provider=provider,
            model=model,
            api_key_env=api_key_env,
            **config_kwargs,
        )
    except ValidationError as exc:
        raise typer.BadParameter(_validation_error_message(exc)) from exc


def _validation_error_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid configuration."
    message = str(errors[0].get("msg", "Invalid configuration."))
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message


def _print_help_and_exit(ctx: typer.Context, *, use_console: bool) -> None:
    if ctx.resilient_parsing:
        return
    if use_console:
        console.print(ctx.get_help())
    else:
        typer.echo(ctx.get_help())
    raise typer.Exit(code=0)


def _run_cli_callback(
    *,
    ctx: typer.Context,
    input_path: Path | None,
    output_path: Path,
    provider: str,
    model: str | None,
    api_key_env: str | None,
    config_type: type[RunConfig] | type[PublishingRunConfig],
    config_kwargs: dict[str, object],
    description: str,
    runner: Callable[
        [RunConfig | PublishingRunConfig, Callable[[dict[str, object]], None] | None],
        list[dict[str, object]],
    ],
    summary_formatter: Callable[[str, dict[str, object]], str],
    use_console_for_help: bool,
) -> list[dict[str, object]] | None:
    if ctx.invoked_subcommand is not None:
        return None
    if input_path is None:
        _print_help_and_exit(ctx, use_console=use_console_for_help)

    config = _build_run_config(
        config_type=config_type,
        provider=provider,
        model=model,
        api_key_env=api_key_env,
        **config_kwargs,
    )
    return _run_books_with_cli_progress(
        description=description,
        runner=lambda event_listener: runner(config, event_listener),
        summary_formatter=summary_formatter,
    )


def _run_async_sync(awaitable):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(awaitable)).result()


def _engineering_command(
    ctx: typer.Context,
    input_path: Annotated[
        Path | None,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=True,
            help=_input_help_text(),
        ),
    ] = None,
    output_path: Annotated[
        Path,
        typer.Option("--output", help=_output_help_text()),
    ] = DEFAULT_OUTPUT_PATH,
    provider: Annotated[
        str,
        typer.Option("--provider", help=_provider_help_text()),
    ] = get_default_provider_option().provider_id,
    model: Annotated[
        str | None,
        typer.Option("--model", help=_model_help_text()),
    ] = None,
    api_key_env: Annotated[
        str | None,
        typer.Option("--api-key-env", help=_api_key_env_help_text()),
    ] = None,
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
    _run_cli_callback(
        ctx=ctx,
        input_path=input_path,
        output_path=output_path,
        provider=provider,
        model=model,
        api_key_env=api_key_env,
        config_type=RunConfig,
        config_kwargs={
            "max_concurrency": max_concurrency,
            "resume": resume,
            "force": force,
            "glossary_path": glossary,
            "name_map_path": name_map,
            "chapter_strategy": chapter_strategy,
            "manual_toc_path": manual_toc,
            "chunk_size": chunk_size,
            "render_pdf": render_pdf,
        },
        description="Processing books",
        runner=lambda config, event_listener: run_engineering_books_sync(
            input_path=input_path,
            output_path=output_path,
            config=config,
            event_listener=event_listener,
        ),
        summary_formatter=_format_engineering_summary,
        use_console_for_help=True,
    )


app.callback(invoke_without_command=True)(_engineering_command)
engineering_app.callback(invoke_without_command=True)(_engineering_command)
run = _engineering_command


@publishing_app.callback(invoke_without_command=True)
def publishing(
    ctx: typer.Context,
    input_path: Annotated[
        Path | None,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=True,
            help=_input_help_text(),
        ),
    ] = None,
    output_path: Annotated[
        Path,
        typer.Option("--output", help=_output_help_text()),
    ] = DEFAULT_OUTPUT_PATH,
    provider: Annotated[
        str,
        typer.Option("--provider", help=_provider_help_text()),
    ] = get_default_provider_option().provider_id,
    model: Annotated[
        str | None,
        typer.Option("--model", help=_model_help_text()),
    ] = None,
    api_key_env: Annotated[
        str | None,
        typer.Option("--api-key-env", help=_api_key_env_help_text()),
    ] = None,
    max_concurrency: Annotated[int, typer.Option("--max-concurrency", min=1)] = 3,
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
    style: Annotated[str, typer.Option("--style")] = "non-fiction-publishing",
    from_stage: Annotated[str, typer.Option("--from-stage")] = "draft",
    to_stage: Annotated[str, typer.Option("--to-stage")] = "final-review",
    also_pdf: Annotated[bool, typer.Option("--also-pdf")] = False,
    also_epub: Annotated[bool, typer.Option("--also-epub")] = False,
    audit_depth: Annotated[str, typer.Option("--audit-depth")] = "consensus",
    enable_cross_review: Annotated[
        bool,
        typer.Option("--enable-cross-review/--no-cross-review"),
    ] = True,
    image_policy: Annotated[str, typer.Option("--image-policy")] = (
        "extract-or-preserve-caption"
    ),
) -> None:
    """Publishing workflows."""
    if ctx.invoked_subcommand is not None:
        return
    if input_path is None:
        _print_help_and_exit(ctx, use_console=False)

    config = _build_run_config(
        config_type=PublishingRunConfig,
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
        style=style,
        from_stage=from_stage,
        to_stage=to_stage,
        also_pdf=also_pdf,
        also_epub=also_epub,
        audit_depth=audit_depth,
        enable_cross_review=enable_cross_review,
        image_policy=image_policy,
    )
    _run_async_sync(
        _run_publishing_cli(
            input_path=input_path,
            output_path=output_path,
            config=config,
        )
    )


async def _run_publishing_cli(
    *,
    input_path: Path,
    output_path: Path,
    config: PublishingRunConfig,
) -> list[dict[str, object]]:
    return _run_books_with_cli_progress(
        description="Processing publishing books",
        runner=lambda event_listener: run_publishing_books_sync(
            input_path=input_path,
            output_path=output_path,
            config=config,
            event_listener=event_listener,
        ),
        summary_formatter=_format_publishing_summary,
    )


def _resolve_qa_target(workspace: Workspace) -> tuple[Path, Path, Path]:
    if workspace.pdf_output_path.exists():
        return workspace.pdf_output_path, workspace.qa_pages_path, workspace.qa_summary_path
    if workspace.publishing_final_pdf_path.exists():
        return (
            workspace.publishing_final_pdf_path,
            workspace.publishing_qa_pages_path,
            workspace.publishing_qa_summary_path,
        )
    raise typer.BadParameter(
        "Workspace PDF does not exist: "
        f"{workspace.pdf_output_path} or {workspace.publishing_final_pdf_path}"
    )


def main() -> None:
    app()


def _run_books_with_cli_progress(
    *,
    description: str,
    runner: Callable[[Callable[[dict[str, object]], None] | None], list[dict[str, object]]],
    summary_formatter: Callable[[str, dict[str, object]], str],
) -> list[dict[str, object]]:
    progress: Progress | None = None
    task_id: int | None = None

    def listener(event: dict[str, object]) -> None:
        nonlocal progress, task_id
        event_type = event["type"]
        if event_type == "run_started":
            progress, task_id = _build_progress(
                description=description,
                total=int(event["total_books"]),
            )
            progress.__enter__()
            return
        if event_type != "book_completed" or progress is None or task_id is None:
            return
        progress.advance(task_id)
        book_name = str(event["book_name"])
        summary = event["summary"]
        if not isinstance(summary, dict):
            raise TypeError(f"Expected dict summary, got {type(summary)!r}")
        console.print(summary_formatter(book_name=book_name, summary=summary))

    exc_info: tuple[type[BaseException] | None, BaseException | None, object | None] = (
        None,
        None,
        None,
    )
    try:
        return runner(listener)
    except BookDiscoveryError as exc:
        exc_info = (type(exc), exc, exc.__traceback__)
        raise typer.BadParameter(str(exc)) from exc
    except Exception as exc:
        exc_info = (type(exc), exc, exc.__traceback__)
        raise
    finally:
        if progress is not None:
            progress.__exit__(*exc_info)


def _format_engineering_summary(*, book_name: str, summary: dict[str, object]) -> str:
    return (
        f"[green]{book_name}[/green] "
        f"chunks={int(summary['successful_chunks'])}/{int(summary['total_chunks'])} "
        f"failed={int(summary['failed_chunks'])} "
        f"cost~=${float(summary['estimated_cost_usd']):.6f}"
    )


def _format_publishing_summary(*, book_name: str, summary: dict[str, object]) -> str:
    return (
        f"[green]{book_name}[/green] "
        f"stage={summary['completed_stage']} "
        f"chunks={int(summary['successful_chunks'])}/{int(summary['total_chunks'])} "
        f"failed={int(summary['failed_chunks'])} "
        f"cost~=${float(summary['estimated_cost_usd']):.6f}"
    )


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
    output_dir: Annotated[Path, typer.Option("--output-dir")],
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
    pdf_path, default_output_dir, summary_path = _resolve_qa_target(workspace)

    total_pages = pdf_page_count(pdf_path)
    if pages:
        selected_pages = parse_page_spec(pages, total_pages=total_pages)
    elif all_pages:
        selected_pages = list(range(1, total_pages + 1))
    else:
        selected_pages = choose_sample_pages(total_pages)

    target_dir = output_dir or default_output_dir
    rendered = render_pdf_pages(
        pdf_path=pdf_path,
        output_dir=target_dir,
        pages=selected_pages,
        dpi=dpi,
    )
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
