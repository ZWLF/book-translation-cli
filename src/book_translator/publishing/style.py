from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class StyleProfile(BaseModel):
    name: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    sentence_rules: list[str] = Field(default_factory=list, min_length=1)
    prohibited_patterns: list[str] = Field(default_factory=list, min_length=1)

    @field_validator("name", "voice")
    @classmethod
    def _strip_and_reject_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


_STYLE_PROFILES: dict[str, StyleProfile] = {
    "non-fiction-publishing": StyleProfile(
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
    ),
}


def get_style_profile(style_name: str) -> StyleProfile:
    try:
        return _STYLE_PROFILES[style_name].model_copy(deep=True)
    except KeyError as error:
        raise KeyError(f"Unknown publishing style: {style_name}") from error
