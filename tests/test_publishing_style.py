from __future__ import annotations

from book_translator.publishing import (
    DraftRequest,
    StyleProfile,
    build_draft_request,
    get_style_profile,
)


def test_get_style_profile_returns_formal_non_fiction_profile() -> None:
    profile = get_style_profile("non-fiction-publishing")

    assert profile == StyleProfile(
        name="non-fiction-publishing",
        voice="正式、克制的非虚构出版中文文风",
        sentence_rules=[
            "优先使用完整、清晰、书面化的句子。",
            "保持段落之间的逻辑推进，不加戏剧化渲染。",
            "让术语、专名和论述保持一致、准确、可追踪。",
        ],
        prohibited_patterns=[
            "口语化缩略表达",
            "夸张修辞",
            "随意插入解释性旁白",
        ],
    )


def test_build_draft_request_packages_style_and_chapter_context() -> None:
    profile = get_style_profile("non-fiction-publishing")

    request = build_draft_request(
        style=profile,
        book_title="科学史的逻辑",
        chapter_title="第一章",
        chapter_index=1,
        chunk_index=2,
        chunk_text="Chunk text",
        source_text="Source text",
    )

    assert request == DraftRequest(
        style_name="non-fiction-publishing",
        style=profile,
        book_title="科学史的逻辑",
        chapter_title="第一章",
        chapter_index=1,
        chunk_index=2,
        chunk_text="Chunk text",
        source_text="Source text",
    )
    assert request.model_dump() == {
        "style_name": "non-fiction-publishing",
        "style": {
            "name": "non-fiction-publishing",
            "voice": "正式、克制的非虚构出版中文文风",
            "sentence_rules": [
                "优先使用完整、清晰、书面化的句子。",
                "保持段落之间的逻辑推进，不加戏剧化渲染。",
                "让术语、专名和论述保持一致、准确、可追踪。",
            ],
            "prohibited_patterns": [
                "口语化缩略表达",
                "夸张修辞",
                "随意插入解释性旁白",
            ],
        },
        "book_title": "科学史的逻辑",
        "chapter_title": "第一章",
        "chapter_index": 1,
        "chunk_index": 2,
        "chunk_text": "Chunk text",
        "source_text": "Source text",
    }
