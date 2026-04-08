from __future__ import annotations

from booksmith.models import PublishingAuditFinding
from booksmith.publishing.source_audit import audit_source_against_target


def _finding_types(findings: list[PublishingAuditFinding]) -> list[str]:
    return [item.finding_type for item in findings]


def test_audit_ignores_translation_wrapper_lines_in_target() -> None:
    findings = audit_source_against_target(
        chapter_id="c-wrapper",
        source_text="Meaning of life. Expand consciousness. Find the answer.",
        target_text=(
            "本书：《示例图书》\n"
            "章节：探寻宇宙本质\n"
            "原文片段索引：0\n"
            "翻译如下：\n"
            "生命的意义。扩展意识。寻找答案。"
        ),
        source_title="Seek the Nature of the Universe",
    )

    assert _finding_types(findings) == []
