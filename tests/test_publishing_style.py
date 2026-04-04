from __future__ import annotations

import pytest
from pydantic import ValidationError

from booksmith.publishing import (
    DraftRequest,
    StyleProfile,
    build_draft_request,
    get_style_profile,
)


def test_get_style_profile_returns_unknown_style_error() -> None:
    with pytest.raises(KeyError, match="Unknown publishing style: missing-style"):
        get_style_profile("missing-style")


def test_get_style_profile_returns_independent_copies() -> None:
    profile = get_style_profile("non-fiction-publishing")
    profile.sentence_rules.append("added rule")

    refreshed = get_style_profile("non-fiction-publishing")

    assert refreshed is not profile
    assert "added rule" not in refreshed.sentence_rules


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        (
            {
                "name": "",
                "voice": "voice",
                "sentence_rules": ["rule"],
                "prohibited_patterns": ["pattern"],
            },
            "name",
        ),
        (
            {
                "name": "style",
                "voice": "",
                "sentence_rules": ["rule"],
                "prohibited_patterns": ["pattern"],
            },
            "voice",
        ),
        (
            {
                "name": "style",
                "voice": "voice",
                "sentence_rules": [],
                "prohibited_patterns": ["pattern"],
            },
            "sentence_rules",
        ),
        (
            {
                "name": "style",
                "voice": "voice",
                "sentence_rules": ["rule"],
                "prohibited_patterns": [],
            },
            "prohibited_patterns",
        ),
    ],
)
def test_style_profile_rejects_empty_fields(payload: dict[str, object], field_name: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        StyleProfile.model_validate(payload)

    assert field_name in str(exc_info.value)


def test_style_profile_requires_rule_lists_when_omitted() -> None:
    with pytest.raises(ValidationError) as exc_info:
        StyleProfile(name="style", voice="voice")

    message = str(exc_info.value)
    assert "sentence_rules" in message
    assert "prohibited_patterns" in message


def test_build_draft_request_keeps_style_context_consistent() -> None:
    profile = get_style_profile("non-fiction-publishing")

    request = build_draft_request(
        style=profile,
        book_title="Book",
        chapter_title="Chapter",
        chapter_index=1,
        chunk_index=2,
        chunk_text="Chunk text",
        source_text="Source text",
    )

    assert request.style_name == profile.name
    assert request.style == profile
    assert request.book_title == "Book"
    assert request.chapter_title == "Chapter"
    assert request.chunk_text == "Chunk text"
    assert request.source_text == "Source text"


def test_draft_request_rejects_style_name_mismatch() -> None:
    profile = get_style_profile("non-fiction-publishing")

    with pytest.raises(ValidationError, match="style_name"):
        DraftRequest(
            style_name="different-style",
            style=profile,
            book_title="Book",
            chapter_title="Chapter",
            chapter_index=1,
            chunk_index=2,
            chunk_text="Chunk text",
            source_text="Source text",
        )
