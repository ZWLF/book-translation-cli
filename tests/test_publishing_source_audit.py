from __future__ import annotations

from book_translator.models import PublishingAuditFinding
from book_translator.publishing.source_audit import audit_source_against_target


def _finding_types(findings: list[PublishingAuditFinding]) -> list[str]:
    return [item.finding_type for item in findings]


def test_audit_detects_collapsed_numbered_list() -> None:
    findings = audit_source_against_target(
        chapter_id="c1",
        source_text="1. First idea.\n2. Second idea.\n3. Third idea.",
        target_text="1. First idea. 2. Second idea. 3. Third idea.",
    )

    assert _finding_types(findings) == [
        "collapsed_numbered_list",
        "list_structure_loss",
    ]
    collapsed = findings[0]
    assert collapsed.block_id is None
    assert collapsed.severity == "high"
    assert collapsed.confidence == 0.95
    assert collapsed.agent_role == "audit"
    assert collapsed.auto_fixable is True
    assert collapsed.source_signature == "collapsed_numbered_list:1-2-3"
    structure_loss = findings[1]
    assert structure_loss.finding_type == "list_structure_loss"
    assert structure_loss.severity == "high"
    assert structure_loss.auto_fixable is True
    assert structure_loss.source_signature == "list_structure_loss:1-2-3"


def test_audit_detects_possible_omission_candidates() -> None:
    findings = audit_source_against_target(
        chapter_id="c2",
        source_text="Alpha.\nBeta.\nGamma.",
        target_text="Alpha.\nBeta.",
    )

    assert _finding_types(findings) == ["possible_omission"]
    assert findings[0].source_signature == "possible_omission:2:beta-gamma"


def test_audit_detects_callout_candidates() -> None:
    findings = audit_source_against_target(
        chapter_id="c3",
        source_text='Remember this:\n"Focus compounds over decades."',
        target_text="Remember this point because focus compounds over decades.",
    )

    assert _finding_types(findings) == ["callout_candidate"]
    assert findings[0].source_signature == "callout_candidate:focus-compounds-over-decades"


def test_audit_detects_question_answer_structure_issues() -> None:
    findings = audit_source_against_target(
        chapter_id="c4",
        source_text="Q: What matters most?\nA: Build useful things.",
        target_text="What matters most?\nBuild useful things.",
    )

    assert _finding_types(findings) == ["question_answer_structure"]
    assert findings[0].source_signature == "question_answer_structure:q1:a1"


def test_audit_keeps_heuristics_conservative_for_plain_paragraphs() -> None:
    findings = audit_source_against_target(
        chapter_id="c5",
        source_text="This is a plain narrative paragraph with no strong structural cues.",
        target_text="This is a plain narrative paragraph with no strong structural cues.",
    )

    assert _finding_types(findings) == []


def test_audit_does_not_flag_short_cjk_sentence_chain_as_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c6",
        source_text="\u7532\u3002\u4e59\u3002\u4e19\u3002",
        target_text="\u7532\u3002\u4e59\u3002",
    )

    assert _finding_types(findings) == []


def test_audit_does_not_flag_english_source_to_compact_cjk_target_as_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c6b",
        source_text="Alpha. Beta. Gamma.",
        target_text="\u7532\u3002\u4e59\u3002\u4e19\u3002",
    )

    assert _finding_types(findings) == []


def test_audit_does_not_flag_hard_wrapped_paragraph_as_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c7",
        source_text=(
            "This paragraph is intentionally wrapped across lines\n"
            "to mimic source extraction wrapping while keeping\n"
            "the same semantic sentence and meaning."
        ),
        target_text=(
            "This paragraph is intentionally wrapped across lines to mimic source extraction "
            "wrapping while keeping the same semantic sentence and meaning."
        ),
    )

    assert _finding_types(findings) == []


def test_audit_ignores_leading_source_title_when_it_is_modeled_separately() -> None:
    findings = audit_source_against_target(
        chapter_id="c7b",
        source_title="Create more than you consume.",
        source_text=(
            "Create more than you consume.\n\n"
            "Build things.\n"
            "Serve people."
        ),
        target_text=(
            "创造的多于消费。\n\n"
            "打造产品。\n"
            "服务他人。"
        ),
    )

    assert _finding_types(findings) == []


def test_audit_does_not_misclassify_partially_preserved_block_list_as_collapsed() -> None:
    findings = audit_source_against_target(
        chapter_id="c8",
        source_text="1. One.\n2. Two.\n3. Three.\n4. Four.\n5. Five.",
        target_text="1. One.\n2. Two.\n3. Three.",
    )

    assert _finding_types(findings) == ["list_structure_loss", "possible_omission"]
    assert findings[0].source_signature == "list_structure_loss:1-2-3-4-5"
    assert findings[1].source_signature == "possible_omission:2:4-four-5-five"


def test_audit_detects_non_one_based_numbered_runs_as_list_structure() -> None:
    findings = audit_source_against_target(
        chapter_id="c8b",
        source_text="4. One.\n5. Two.\n6. Three.",
        target_text="4. One 5. Two 6. Three",
    )

    assert _finding_types(findings) == [
        "collapsed_numbered_list",
        "list_structure_loss",
    ]
    assert findings[0].source_signature == "collapsed_numbered_list:4-5-6"
    assert findings[1].source_signature == "list_structure_loss:4-5-6"


def test_audit_keeps_cross_language_prose_conservative_when_coverage_is_substantial() -> None:
    findings = audit_source_against_target(
        chapter_id="c8c",
        source_text=(
            "Elon built companies by taking risks. "
            "He read widely and thought from first principles. "
            "He learned from physics. "
            "He acted quickly when the evidence was clear."
        ),
        target_text=(
            "埃隆通过承担风险来建立公司，并以第一性原理思考。\n\n"
            "他广泛阅读，学习物理学，并在证据清晰时迅速行动。"
        ),
    )

    assert _finding_types(findings) == []


def test_audit_populates_richer_finding_shape_for_non_autofixable_results() -> None:
    findings = audit_source_against_target(
        chapter_id="c9",
        source_text="Q: What matters most?\nA: Build useful things.",
        target_text="Only the answer remains.",
    )

    assert _finding_types(findings) == ["question_answer_structure"]
    finding = findings[0]
    assert finding.block_id is None
    assert finding.confidence == 0.7
    assert finding.agent_role == "audit"
    assert finding.auto_fixable is False
    assert finding.source_signature == "question_answer_structure:q1:a1"


def test_audit_ignores_trailing_reference_tail_as_chapter_local_omission() -> None:
    findings = audit_source_against_target(
        chapter_id="c10",
        source_text=(
            "Build useful things.\n"
            "Move fast.\n"
            "Learn constantly.\n\n"
            "76 Musk, \"Full Send Podcast.\"\n"
            "77 Fridman and Musk, \"Lex Fridman Podcast #252.\"\n"
            "78 Musk, \"Web 2.0 Summit 08.\""
        ),
        target_text="Build useful things.\nMove fast.\nLearn constantly.",
    )

    assert _finding_types(findings) == []


def test_audit_still_flags_missing_tail_when_it_is_real_prose_not_references() -> None:
    findings = audit_source_against_target(
        chapter_id="c11",
        source_text=(
            "Build useful things.\n"
            "Move fast.\n"
            "Learn constantly.\n"
            "Then share the lessons with the team."
        ),
        target_text="Build useful things.\nMove fast.\nLearn constantly.",
    )

    assert _finding_types(findings) == ["possible_omission"]


def test_audit_relaxes_cross_language_possible_omission_with_shared_numeric_anchors() -> None:
    findings = audit_source_against_target(
        chapter_id="c12",
        source_text=(
            "A big rock will hit Earth eventually. We currently have no defense.\n"
            "894\n"
            "If you think long term, you realize some natural disaster could end life on Earth.\n"
            "895\n"
            "Large asteroids and comets remain a danger.\n"
            "896\n"
            "A multiplanet civilization increases the lifespan of life.\n"
            "897\n"
            "791 Anderson and Musk, \"A Future Worth Getting Excited About.\""
        ),
        target_text=(
            "最终，一颗巨大的陨石终将撞击地球，我们目前没有任何防御手段。\n"
            "894\n"
            "如果你从长远的角度看，就会意识到某种自然灾害终会毁灭地球上的生命。\n"
            "895\n"
            "大型小行星和彗星仍然构成威胁。\n"
            "896\n"
            "如果我们成为多行星文明，生命的寿命将大大延长。\n"
            "897"
        ),
    )

    assert _finding_types(findings) == []


def test_audit_keeps_cross_language_possible_omission_when_target_is_too_sparse() -> None:
    findings = audit_source_against_target(
        chapter_id="c13",
        source_text=(
            "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five. "
            "Sentence six. Sentence seven. Sentence eight. Sentence nine. Sentence ten."
        ),
        target_text="这是一句非常短的中文摘要。",
    )

    assert _finding_types(findings) == ["possible_omission"]


def test_audit_does_not_flag_reference_tail_when_same_content_is_reflowed_in_target() -> None:
    findings = audit_source_against_target(
        chapter_id="c14",
        source_text=(
            "788 The Tesla Team, Master Plan Part IV, https://digitalassets.\n"
            "tesla.\n"
            "com/tesla-contents/image/upload/Tesla-Master-Plan-Part-4.\n"
            "789 Farzad, https://www.\n"
            "youtube.\n"
            "com/watch?\n"
            "v=BoGNEZF2XFQ ."
        ),
        target_text=(
            "788 The Tesla Team, Master Plan Part IV, https://digitalassets.\n"
            "tesla.\n"
            "com/tesla-contents/image/upload/Tesla-Master-Plan-Part-4.\n"
            "789 Farzad, https://www.\n"
            "youtube.\n"
            "com/watch?\n"
            "v=BoGNEZF2XFQ."
        ),
    )

    assert _finding_types(findings) == []


def test_audit_relaxes_citation_heavy_timeline_with_high_anchor_coverage() -> None:
    findings = audit_source_against_target(
        chapter_id="c15",
        source_text="".join(
            [
                "1005 Cade Metz, \"Inside OpenAI\", Wired.\n",
                (
                    "1006 Sony Salzman et al., "
                    "\"Neuralink's First Brain Implant Patient\", ABC News.\n"
                ),
                "1007 Fred Lambert, \"Tesla Model 3\", Electrek.\n",
                "1008 Fridman and Musk, \"Lex Fridman Podcast #400.\"\n",
                "1009 Jackie Wattles, \"NASA, SpaceX Launch Astronauts\", CNN.\n",
                "1010 Sergei Klebnikov, "
                "\"Elon Musk Is Now the Richest Person in the World\", Forbes.\n",
                "1011 Tien Le and Vanessa Romo, \"Elon Musk Is Time's 2021 Person of the Year.\"\n",
                "1012 Elon Musk (@elonmusk), \"The first human received an implant...\", X.\n",
                "1013 Mike Wendling, "
                "\"Elon Musk's Starbase in Texas Will Officially Become a City\", BBC News.\n",
                "1014 Matt Durot, "
                "\"Elon Musk Just Became the First Person Ever Worth $500 Billion\", Forbes.",
            ]
        ),
        target_text="".join(
            [
                "1005 Cade Metz，《Inside OpenAI》，《连线》。\n",
                (
                    "1006 Sony Salzman 等，"
                    "《Neuralink's First Brain Implant Patient》，《ABC 新闻》。\n"
                ),
                "1007 Fred Lambert，《Tesla Model 3》，Electrek。\n",
                "1008 Fridman 和 Musk，《Lex Fridman Podcast #400》。\n",
                "1009 Jackie Wattles，《NASA, SpaceX Launch Astronauts》，《CNN》。\n",
                "1010 Sergei Klebnikov，"
                "《Elon Musk Is Now the Richest Person in the World》，《福布斯》。\n",
                "1011 Tien Le 和 Vanessa Romo，《Elon Musk Is Time's 2021 Person of the Year》。\n",
                "1012 Elon Musk (@elonmusk)，《The first human received an implant...》，X。\n",
                "1013 Mike Wendling，"
                "《Elon Musk's Starbase in Texas Will Officially Become a City》，《BBC 新闻》。\n",
                "1014 Matt Durot，"
                "《Elon Musk Just Became the First Person Ever Worth $500 Billion》，《福布斯》。",
            ]
        ),
    )

    assert _finding_types(findings) == []
