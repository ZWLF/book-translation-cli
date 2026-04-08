from __future__ import annotations

from booksmith.models import PublishingAuditFinding
from booksmith.publishing.source_audit import audit_source_against_target


def _finding_types(findings: list[PublishingAuditFinding]) -> list[str]:
    return [item.finding_type for item in findings]


def test_audit_ignores_trailing_reference_tail_without_numeric_prefix() -> None:
    findings = audit_source_against_target(
        chapter_id="c-reference-tail",
        source_text=(
            "Build useful things.\n"
            "Move fast.\n"
            "Learn constantly.\n\n"
            "“Elon Musk: Digital Superintelligence,” Y Combinator.\n"
            "Musk, “Caltech Commencement Speech.”"
        ),
        target_text="Build useful things.\nMove fast.\nLearn constantly.",
    )

    assert _finding_types(findings) == []


def test_audit_relaxes_cross_language_omission_when_tail_turns_into_references() -> None:
    findings = audit_source_against_target(
        chapter_id="c-reference-heavy-tail",
        source_text=(
            "A big rock will hit Earth eventually. We currently have no defense.\n"
            "If you think long term, you realize some natural disaster could end life on Earth.\n"
            "Large asteroids and comets remain a danger.\n"
            "There is always some risk of this occurring.\n"
            "A multiplanet civilization increases the lifespan of life.\n"
            "We should keep building defenses.\n"
            "791 Anderson and Musk, \"A Future Worth Getting Excited About.\"\n"
            "792 Peterson and Musk, \"Dr. Peterson x Elon Musk.\"\n"
            "youtube.\n"
            "com/watch?\n"
            "v=abcdef12345 .\n"
            "Musk, \"Caltech Commencement Speech.\"\n"
            "\"Elon Musk: Digital Superintelligence,\" Y Combinator.\n"
        ),
        target_text=(
            "一块巨石终将撞击地球，而我们目前没有任何防御手段。"
            "如果你从长远角度思考，就会意识到某种自然灾害终将毁灭地球上的生命。"
            "大型小行星和彗星仍然构成威胁。"
            "这种风险始终存在。"
            "如果我们成为多行星文明，生命的寿命就会更长。"
            "我们应该继续建设防御能力。"
        ),
    )

    assert _finding_types(findings) == []
