from __future__ import annotations

from booksmith.models import TranslationRequest


def build_system_prompt() -> str:
    return (
        "You are a professional book translator. "
        "Translate the provided text into Simplified Chinese. "
        "Preserve chapter headings. Do not summarize or explain. Do not omit content. "
        "Keep proper nouns and terms consistent."
    )


def build_user_prompt(request: TranslationRequest) -> str:
    extras: list[str] = []
    if request.glossary:
        extras.append(
            "Glossary:\n"
            + "\n".join(
                f"- {source}: {target}" for source, target in request.glossary.items()
            )
        )
    if request.name_map:
        extras.append(
            "Name map:\n"
            + "\n".join(
                f"- {source}: {target}" for source, target in request.name_map.items()
            )
        )
    extra_text = ""
    if extras:
        extra_text = "\n\n" + "\n\n".join(extras)
    return (
        f"Book: {request.book_title}\n"
        f"Chapter: {request.chapter_title}\n"
        f"Chunk index: {request.chunk_index}\n\n"
        "Translate the following text into Simplified Chinese only:\n\n"
        f"{request.source_text}{extra_text}"
    )
