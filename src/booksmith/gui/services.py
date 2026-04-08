from __future__ import annotations

from pathlib import Path
from typing import cast

from pydantic import ValidationError

from booksmith.config import (
    DEFAULT_MODELS,
    PublishingOutputSelection,
    PublishingRunConfig,
    RunConfig,
    resolve_publishing_outputs,
)
from booksmith.utils import slugify

from .state import (
    GuiExpectedOutput,
    GuiFormState,
    GuiRuntimeRequest,
    GuiValidationIssue,
    OutputKind,
)

SUPPORTED_SOURCE_SUFFIXES = {".pdf", ".epub"}


class GuiFormValidationError(ValueError):
    def __init__(self, issues: list[GuiValidationIssue]) -> None:
        self.issues = tuple(issues)
        message = "; ".join(f"{issue.field}: {issue.message}" for issue in self.issues)
        super().__init__(message)


def validate_form_state(form: GuiFormState) -> None:
    issues = _collect_preview_issues(form)

    output_path = form.output_path
    if output_path is None:
        issues.append(GuiValidationIssue(field="output_path", message="output_path is required"))

    provider = form.provider.strip()
    if not provider:
        issues.append(GuiValidationIssue(field="provider", message="provider is required"))
    elif provider not in DEFAULT_MODELS:
        issues.append(
            GuiValidationIssue(
                field="provider",
                message=f"unsupported provider: {provider}",
            )
        )

    model = form.model.strip()
    if not model:
        issues.append(GuiValidationIssue(field="model", message="model is required"))

    if issues:
        raise GuiFormValidationError(issues)


def build_runtime_request(form: GuiFormState) -> GuiRuntimeRequest:
    validate_form_state(form)
    assert form.input_path is not None
    assert form.output_path is not None

    discovered_books = _discover_books_for_input(form.input_path)
    source_kind = _source_kind(form.input_path)
    source_format = _source_format(form.input_path)

    if form.mode == "engineering":
        config = RunConfig(
            provider=form.provider.strip(),
            model=form.model.strip(),
            api_key=form.api_key.strip() or None,
            resume=form.resume,
            force=form.force,
            glossary_path=form.glossary_path,
            name_map_path=form.name_map_path,
            chapter_strategy=form.chapter_strategy,
            manual_toc_path=form.manual_toc_path,
            chunk_size=form.chunk_size,
            render_pdf=form.render_pdf,
            request_timeout_seconds=form.request_timeout_seconds,
            max_attempts=form.max_attempts,
            max_concurrency=form.max_concurrency,
        )
        if source_kind == "file":
            primary_output = _engineering_primary_output(form.input_path, form.render_pdf)
            additional_outputs = _engineering_additional_outputs(form.input_path, form.render_pdf)
        else:
            primary_output = None
            additional_outputs = ()
        expected_outputs = _engineering_expected_outputs(
            discovered_books,
            form.output_path,
            render_pdf=form.render_pdf,
        )
        return GuiRuntimeRequest(
            mode="engineering",
            input_path=form.input_path,
            output_path=form.output_path,
            source_kind=source_kind,
            source_format=source_format,
            discovered_books=discovered_books,
            provider=config.provider,
            model=config.resolved_model(),
            config=config,
            primary_output=primary_output,
            additional_outputs=additional_outputs,
            expected_outputs=expected_outputs,
        )

    config = _build_publishing_config(form)
    if source_kind == "file":
        selection = resolve_publishing_outputs(form.input_path, config)
        primary_output: str | None = selection.primary_output
        additional_outputs = tuple(selection.additional_outputs)
        file_mode = True
    else:
        primary_output = None
        additional_outputs = ()
        file_mode = False
    expected_outputs = _publishing_expected_outputs(
        discovered_books,
        form.output_path,
        also_pdf=config.also_pdf,
        also_epub=config.also_epub,
        file_mode=file_mode,
    )
    return GuiRuntimeRequest(
        mode="publishing",
        input_path=form.input_path,
        output_path=form.output_path,
        source_kind=source_kind,
        source_format=source_format,
        discovered_books=discovered_books,
        provider=config.provider,
        model=config.resolved_model(),
        config=config,
        primary_output=primary_output,
        additional_outputs=additional_outputs,
        expected_outputs=expected_outputs,
    )


def expected_outputs_for_form(form: GuiFormState) -> tuple[GuiExpectedOutput, ...]:
    _validate_preview_form_state(form)
    assert form.input_path is not None
    assert form.output_path is not None

    discovered_books = _discover_books_for_input(form.input_path)
    if form.mode == "engineering":
        return _engineering_expected_outputs(
            discovered_books,
            form.output_path,
            render_pdf=form.render_pdf,
        )
    return _publishing_expected_outputs(
        discovered_books,
        form.output_path,
        also_pdf=form.also_pdf,
        also_epub=form.also_epub,
        file_mode=form.input_path.is_file(),
    )


def _source_format(input_path: Path) -> str:
    if input_path.is_dir():
        return "directory"
    return input_path.suffix.lower().lstrip(".")


def _source_kind(input_path: Path) -> str:
    return "directory" if input_path.is_dir() else "file"


def _discover_books_for_input(input_path: Path) -> tuple[Path, ...]:
    if input_path.is_file():
        return (input_path,)
    discovered: list[Path] = []
    for path in input_path.rglob("*"):
        if path.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES:
            discovered.append(path)
    return tuple(sorted(discovered))


def _engineering_primary_output(book_path: Path, render_pdf: bool) -> str:
    if book_path.suffix.lower() == ".pdf" and render_pdf:
        return "pdf"
    return "txt"


def _engineering_additional_outputs(book_path: Path, render_pdf: bool) -> tuple[str, ...]:
    if book_path.suffix.lower() == ".pdf" and render_pdf:
        return ("txt",)
    if render_pdf:
        return ("pdf",)
    return ()


def _engineering_expected_outputs(
    books: tuple[Path, ...],
    output_root: Path,
    *,
    render_pdf: bool,
) -> tuple[GuiExpectedOutput, ...]:
    outputs: list[GuiExpectedOutput] = []
    for book in books:
        book_root = output_root / slugify(book.stem)
        primary = _engineering_primary_output(book, render_pdf)
        outputs.append(
            _make_expected_output(
                kind=primary,
                label=_label_for_output_kind(primary),
                book_path=book,
                path_hint=_engineering_output_path(book_root, primary),
            )
        )
        for extra_kind in _engineering_additional_outputs(book, render_pdf):
            outputs.append(
                _make_expected_output(
                    kind=extra_kind,
                    label=_label_for_output_kind(extra_kind),
                    book_path=book,
                    path_hint=_engineering_output_path(book_root, extra_kind),
                )
            )
    return tuple(outputs)


def _engineering_output_path(book_root: Path, kind: str) -> str:
    if kind == "txt":
        return str(book_root / "translated.txt")
    if kind == "pdf":
        return str(book_root / "translated.pdf")
    raise ValueError(f"Unsupported engineering output kind: {kind}")


def _publishing_expected_outputs(
    books: tuple[Path, ...],
    output_root: Path,
    *,
    also_pdf: bool,
    also_epub: bool,
    file_mode: bool,
) -> tuple[GuiExpectedOutput, ...]:
    outputs: list[GuiExpectedOutput] = []
    for book in books:
        book_root = output_root / slugify(book.stem) / "publishing" / "final"
        if file_mode:
            selection = _preview_publishing_selection(
                book,
                also_pdf=also_pdf,
                also_epub=also_epub,
            )
        else:
            selection = resolve_publishing_outputs(
                book,
                _publishing_config_for_selection(also_pdf=also_pdf, also_epub=also_epub),
            )
        for kind in [selection.primary_output, *selection.additional_outputs]:
            outputs.append(
                _make_expected_output(
                    kind=str(kind),
                    label=_label_for_output_kind(str(kind)),
                    book_path=book,
                    path_hint=_publishing_output_path(book_root, str(kind)),
                )
            )
    return tuple(outputs)


def _preview_publishing_selection(
    book_path: Path,
    *,
    also_pdf: bool,
    also_epub: bool,
) -> PublishingOutputSelection:
    suffix = book_path.suffix.lower()
    if suffix == ".pdf":
        if also_pdf:
            raise GuiFormValidationError(
                [
                    GuiValidationIssue(
                        field="publishing_outputs",
                        message="invalid publishing output flags",
                    )
                ]
            )
        additional_outputs = ["epub"] if also_epub else []
        return PublishingOutputSelection(
            primary_output="pdf",
            additional_outputs=additional_outputs,
        )
    if suffix == ".epub":
        if also_epub:
            raise GuiFormValidationError(
                [
                    GuiValidationIssue(
                        field="publishing_outputs",
                        message="invalid publishing output flags",
                    )
                ]
            )
        additional_outputs = ["pdf"] if also_pdf else []
        return PublishingOutputSelection(
            primary_output="epub",
            additional_outputs=additional_outputs,
        )
    raise GuiFormValidationError(
        [
            GuiValidationIssue(
                field="input_path",
                message="input file must be a .pdf or .epub",
            )
        ]
    )


def _publishing_config_for_selection(
    *,
    also_pdf: bool,
    also_epub: bool,
) -> PublishingRunConfig:
    return PublishingRunConfig(
        provider="openai",
        model=DEFAULT_MODELS["openai"],
        also_pdf=also_pdf,
        also_epub=also_epub,
    )


def _publishing_output_path(book_root: Path, kind: str) -> str:
    if kind == "pdf":
        return str(book_root / "translated.pdf")
    if kind == "epub":
        return str(book_root / "translated.epub")
    raise ValueError(f"Unsupported publishing output kind: {kind}")


def _make_expected_output(
    *,
    kind: str,
    label: str,
    book_path: Path,
    path_hint: str,
) -> GuiExpectedOutput:
    return GuiExpectedOutput(
        label=label,
        kind=cast(OutputKind, kind),
        path_hint=path_hint,
        required=True,
        source_path=book_path,
    )


def _label_for_output_kind(kind: str) -> str:
    if kind == "txt":
        return "Translated text"
    if kind == "pdf":
        return "PDF"
    if kind == "epub":
        return "EPUB"
    raise ValueError(f"Unsupported output kind: {kind}")


def _collect_preview_issues(form: GuiFormState) -> list[GuiValidationIssue]:
    input_path = form.input_path
    if input_path is None:
        return [GuiValidationIssue(field="input_path", message="input_path is required")]
    if not input_path.exists():
        return [GuiValidationIssue(field="input_path", message="input_path does not exist")]

    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
            return [
                GuiValidationIssue(
                    field="input_path",
                    message="input file must be a .pdf or .epub",
                )
            ]
        return _publishing_output_flag_issues(form, input_path)

    discovered_books = _discover_books_for_input(input_path)
    if not discovered_books:
        return [
            GuiValidationIssue(
                field="input_path",
                message="no supported .pdf or .epub files found under the selected directory",
            )
        ]
    return []


def _validate_preview_form_state(form: GuiFormState) -> None:
    issues = _collect_preview_issues(form)
    if issues:
        raise GuiFormValidationError(issues)


def _publishing_output_flag_issues(
    form: GuiFormState,
    book: Path,
) -> list[GuiValidationIssue]:
    if form.mode != "publishing":
        return []
    suffix = book.suffix.lower()
    if suffix == ".pdf" and form.also_pdf:
        return [
            GuiValidationIssue(
                field="publishing_outputs",
                message="invalid publishing output flags",
            )
        ]
    if suffix == ".epub" and form.also_epub:
        return [
            GuiValidationIssue(
                field="publishing_outputs",
                message="invalid publishing output flags",
            )
        ]
    return []


def _build_publishing_config(form: GuiFormState) -> PublishingRunConfig:
    try:
        return PublishingRunConfig(
            provider=form.provider.strip(),
            model=form.model.strip(),
            api_key=form.api_key.strip() or None,
            resume=form.resume,
            force=form.force,
            glossary_path=form.glossary_path,
            name_map_path=form.name_map_path,
            chapter_strategy=form.chapter_strategy,
            manual_toc_path=form.manual_toc_path,
            chunk_size=form.chunk_size,
            render_pdf=form.render_pdf,
            request_timeout_seconds=form.request_timeout_seconds,
            max_attempts=form.max_attempts,
            style=form.style,
            from_stage=form.from_stage,
            to_stage=form.to_stage,
            max_concurrency=form.max_concurrency,
            also_pdf=form.also_pdf,
            also_epub=form.also_epub,
            audit_depth=form.audit_depth,
            enable_cross_review=form.enable_cross_review,
            image_policy=form.image_policy,
        )
    except ValidationError as exc:
        raise GuiFormValidationError(_issues_from_validation_error(exc)) from exc


def _issues_from_validation_error(exc: ValidationError) -> list[GuiValidationIssue]:
    issues: list[GuiValidationIssue] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        if isinstance(loc, tuple) and loc:
            field = ".".join(str(part) for part in loc)
        else:
            field = "publishing_config"
        issues.append(
            GuiValidationIssue(
                field=field,
                message=str(error.get("msg", "invalid value")),
            )
        )
    return issues
