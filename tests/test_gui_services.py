from __future__ import annotations

from pathlib import Path

import pytest

from book_translator.config import PublishingRunConfig, RunConfig
from book_translator.gui.services import (
    GuiFormState,
    GuiFormValidationError,
    build_runtime_request,
    expected_outputs_for_form,
    validate_form_state,
)


def test_build_runtime_request_builds_engineering_request_with_expected_outputs(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "book.pdf"
    input_path.write_text("placeholder", encoding="utf-8")
    output_path = tmp_path / "out"
    form = GuiFormState(
        mode="engineering",
        input_path=input_path,
        output_path=output_path,
        provider="openai",
        model="gpt-4o-mini",
        render_pdf=True,
    )

    request = build_runtime_request(form)

    assert request.mode == "engineering"
    assert isinstance(request.config, RunConfig)
    assert request.primary_output == "pdf"
    assert request.additional_outputs == ("txt",)
    assert request.discovered_books == (input_path,)
    assert [(item.kind, Path(item.path_hint)) for item in request.expected_outputs] == [
        ("pdf", output_path / "book" / "translated.pdf"),
        ("txt", output_path / "book" / "translated.txt"),
    ]
    assert all(item.required for item in request.expected_outputs)
    assert [item.source_path for item in request.expected_outputs] == [input_path, input_path]


def test_expected_outputs_for_form_works_before_provider_and_model_are_ready(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "book.pdf"
    input_path.write_text("placeholder", encoding="utf-8")
    output_path = tmp_path / "out"
    form = GuiFormState(
        mode="engineering",
        input_path=input_path,
        output_path=output_path,
        provider="",
        model="",
        render_pdf=True,
    )

    outputs = expected_outputs_for_form(form)

    assert [(item.kind, Path(item.path_hint)) for item in outputs] == [
        ("pdf", output_path / "book" / "translated.pdf"),
        ("txt", output_path / "book" / "translated.txt"),
    ]


def test_build_runtime_request_builds_engineering_request_for_epub_sources_with_pdf_rendering(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "book.epub"
    input_path.write_text("placeholder", encoding="utf-8")
    output_path = tmp_path / "out"
    form = GuiFormState(
        mode="engineering",
        input_path=input_path,
        output_path=output_path,
        provider="openai",
        model="gpt-4o-mini",
        render_pdf=True,
    )

    request = build_runtime_request(form)

    assert request.primary_output == "txt"
    assert request.additional_outputs == ("pdf",)
    assert [(item.kind, Path(item.path_hint)) for item in request.expected_outputs] == [
        ("txt", output_path / "book" / "translated.txt"),
        ("pdf", output_path / "book" / "translated.pdf"),
    ]


@pytest.mark.parametrize(
    (
        "filenames",
        "mode",
        "form_kwargs",
        "expected_items",
    ),
    [
        (
            ["a.pdf", "b.pdf"],
            "engineering",
            {"render_pdf": True},
            [
                ("pdf", "a.pdf", "translated.pdf"),
                ("txt", "a.pdf", "translated.txt"),
                ("pdf", "b.pdf", "translated.pdf"),
                ("txt", "b.pdf", "translated.txt"),
            ],
        ),
        (
            ["a.epub", "b.epub"],
            "publishing",
            {"also_pdf": True},
            [
                ("epub", "a.epub", "translated.epub"),
                ("pdf", "a.epub", "translated.pdf"),
                ("epub", "b.epub", "translated.epub"),
                ("pdf", "b.epub", "translated.pdf"),
            ],
        ),
        (
            ["a.pdf", "b.epub"],
            "publishing",
            {"also_pdf": True, "also_epub": True},
            [
                ("pdf", "a.pdf", "translated.pdf"),
                ("epub", "a.pdf", "translated.epub"),
                ("epub", "b.epub", "translated.epub"),
                ("pdf", "b.epub", "translated.pdf"),
            ],
        ),
    ],
)
def test_expected_outputs_for_form_uses_discovered_books_for_directory_inputs(
    tmp_path: Path,
    filenames: list[str],
    mode: str,
    form_kwargs: dict[str, object],
    expected_items: list[tuple[str, str, str]],
) -> None:
    input_path = tmp_path / "books"
    input_path.mkdir()
    for filename in filenames:
        (input_path / filename).write_text("placeholder", encoding="utf-8")
    output_path = tmp_path / "out"
    form = GuiFormState(
        mode=mode,
        input_path=input_path,
        output_path=output_path,
        provider="",
        model="",
        **form_kwargs,
    )

    outputs = expected_outputs_for_form(form)

    actual_items = [
        (item.kind, item.source_path.name, Path(item.path_hint).name)
        for item in outputs
    ]
    assert actual_items == [
        (kind, source_name, target_name) for kind, source_name, target_name in expected_items
    ]
    assert all(item.required for item in outputs)


def test_expected_outputs_for_form_rejects_empty_directory(tmp_path: Path) -> None:
    input_path = tmp_path / "empty"
    input_path.mkdir()
    form = GuiFormState(
        mode="publishing",
        input_path=input_path,
        output_path=tmp_path / "out",
        provider="",
        model="",
    )

    with pytest.raises(GuiFormValidationError, match="no supported \\.pdf or \\.epub files"):
        expected_outputs_for_form(form)


def test_build_runtime_request_builds_directory_publishing_request_shape(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "books"
    input_path.mkdir()
    pdf_book = input_path / "a.pdf"
    epub_book = input_path / "b.epub"
    pdf_book.write_text("placeholder", encoding="utf-8")
    epub_book.write_text("placeholder", encoding="utf-8")
    output_path = tmp_path / "out"
    form = GuiFormState(
        mode="publishing",
        input_path=input_path,
        output_path=output_path,
        provider="gemini",
        model="gemini-3.1-flash-lite-preview",
        also_pdf=True,
        also_epub=True,
    )

    request = build_runtime_request(form)

    assert isinstance(request.config, PublishingRunConfig)
    assert request.primary_output is None
    assert request.additional_outputs == ()
    assert request.discovered_books == (pdf_book, epub_book)
    actual_items = [
        (item.kind, item.source_path.name, Path(item.path_hint))
        for item in request.expected_outputs
    ]
    assert actual_items == [
        ("pdf", "a.pdf", output_path / "a" / "publishing" / "final" / "translated.pdf"),
        ("epub", "a.pdf", output_path / "a" / "publishing" / "final" / "translated.epub"),
        ("epub", "b.epub", output_path / "b" / "publishing" / "final" / "translated.epub"),
        ("pdf", "b.epub", output_path / "b" / "publishing" / "final" / "translated.pdf"),
    ]


@pytest.mark.parametrize(
    ("overrides", "message_fragment"),
    [
        (
            {"from_stage": "deep-review", "to_stage": "draft"},
            "from_stage must not come after to_stage",
        ),
        ({"style": "bad-style"}, "style"),
        ({"audit_depth": "wide"}, "audit_depth"),
        ({"image_policy": "ignore-everything"}, "image_policy"),
    ],
)
def test_build_runtime_request_wraps_publishing_config_validation_errors(
    tmp_path: Path,
    overrides: dict[str, object],
    message_fragment: str,
) -> None:
    input_path = tmp_path / "book.pdf"
    input_path.write_text("placeholder", encoding="utf-8")
    form_kwargs = {
        "mode": "publishing",
        "input_path": input_path,
        "output_path": tmp_path / "out",
        "provider": "gemini",
        "model": "gemini-3.1-flash-lite-preview",
    }
    form_kwargs.update(overrides)
    form = GuiFormState(**form_kwargs)

    with pytest.raises(GuiFormValidationError) as excinfo:
        build_runtime_request(form)

    assert any(
        message_fragment in issue.message or message_fragment in issue.field
        for issue in excinfo.value.issues
    )


@pytest.mark.parametrize(
    ("field", "kwargs", "message"),
    [
        ("input_path", {"input_path": None}, "input_path is required"),
        ("output_path", {"output_path": None}, "output_path is required"),
        ("provider", {"provider": ""}, "provider is required"),
        ("model", {"model": ""}, "model is required"),
    ],
)
def test_validate_form_state_rejects_missing_required_fields(
    tmp_path: Path,
    field: str,
    kwargs: dict[str, object],
    message: str,
) -> None:
    input_path = tmp_path / "book.pdf"
    input_path.write_text("placeholder", encoding="utf-8")
    form_kwargs = {
        "mode": "engineering",
        "input_path": input_path,
        "output_path": tmp_path / "out",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    form_kwargs.update(kwargs)
    form = GuiFormState(**form_kwargs)

    with pytest.raises(GuiFormValidationError, match=message):
        validate_form_state(form)


def test_validate_form_state_rejects_missing_source_file(tmp_path: Path) -> None:
    form = GuiFormState(
        mode="engineering",
        input_path=tmp_path / "missing.pdf",
        output_path=tmp_path / "out",
        provider="openai",
        model="gpt-4o-mini",
    )

    with pytest.raises(GuiFormValidationError, match="input_path does not exist"):
        validate_form_state(form)
