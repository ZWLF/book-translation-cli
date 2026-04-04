from __future__ import annotations

from pydantic import BaseModel, model_validator

from booksmith.publishing.style import StyleProfile


class DraftRequest(BaseModel):
    style_name: str
    style: StyleProfile
    book_title: str
    chapter_title: str
    chapter_index: int
    chunk_index: int
    chunk_text: str
    source_text: str

    @model_validator(mode="after")
    def _ensure_style_name_matches_style(self) -> DraftRequest:
        if self.style_name != self.style.name:
            raise ValueError("style_name must match style.name")
        return self


def build_draft_request(
    *,
    style: StyleProfile,
    book_title: str,
    chapter_title: str,
    chapter_index: int,
    chunk_index: int,
    chunk_text: str,
    source_text: str,
) -> DraftRequest:
    return DraftRequest(
        style_name=style.name,
        style=style,
        book_title=book_title,
        chapter_title=chapter_title,
        chapter_index=chapter_index,
        chunk_index=chunk_index,
        chunk_text=chunk_text,
        source_text=source_text,
    )
