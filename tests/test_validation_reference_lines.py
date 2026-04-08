from __future__ import annotations

from pathlib import Path

from booksmith.publishing.validation import validate_publishing_redlines


def test_validate_publishing_redlines_allows_reference_like_english_lines(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "translated.txt"
    chapters_path = tmp_path / "revised_chapters.jsonl"
    text_path.write_text(
        "\n".join(
            [
                "\u7b2c\u4e00\u7ae0\uff1a\u4e2d\u6587\u6807\u9898",
                "",
                "Tim Urban, \"SpaceX's Big F***ing Rocket.\" 971",
                "Musk (@elonmusk), X account. 944",
                "https://example.com/source",
                "\u201cElon Musk: Digital Superintelligence,\u201d Y Combinator.",
                "Musk, \u201cCaltech Commencement Speech.\u201d",
            ]
        ),
        encoding="utf-8",
    )
    chapters_path.write_text(
        (
            '{"chapter_id":"c1","chapter_index":0,'
            '"source_title":"Chapter 1",'
            '"translated_title":"\\u7b2c\\u4e00\\u7ae0\\uff1a\\u4e2d\\u6587\\u6807\\u9898",'
            '"blocks":[],"assets":[]}\n'
        ),
        encoding="utf-8",
    )

    report = validate_publishing_redlines(
        text_path=text_path,
        chapters_path=chapters_path,
    )

    assert report["passed"] is True
    assert report["markdown_artifact_count"] == 0
    assert report["english_body_line_count"] == 0
    assert report["blocker_count"] == 0
