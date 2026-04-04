from __future__ import annotations

import re

from book_translator.models import PublishingAuditFinding

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_NUMBERED_MARKER_RE = re.compile(r"(?<!\d)(\d{1,3})[.)]\s+\S")
_STRUCTURED_LINE_RE = re.compile(
    r"^\s*(?:\d{1,3}[.)]|[-*]|\u2022|(?:q|question|a|answer|\u95ee|\u7b54)\s*[:\uff1a])\s+\S",
    re.IGNORECASE,
)


def audit_source_against_target(
    *,
    chapter_id: str,
    source_text: str,
    target_text: str,
) -> list[PublishingAuditFinding]:
    findings: list[PublishingAuditFinding] = []

    if _looks_like_collapsed_numbered_list(source_text=source_text, target_text=target_text):
        findings.append(
            _build_audit_finding(
                chapter_id=chapter_id,
                finding_type="collapsed_numbered_list",
                severity="high",
                source_excerpt=_excerpt(source_text),
                target_excerpt=_excerpt(target_text),
                reason="Ordered list markers in source are not preserved as block items in target.",
                auto_fixable=True,
                confidence=0.95,
                source_signature=_collapsed_numbered_list_signature(source_text),
            )
        )

    findings.extend(
        _detect_list_structure_loss(
            chapter_id=chapter_id,
            source_text=source_text,
            target_text=target_text,
        )
    )
    findings.extend(
        _detect_possible_omissions(
            chapter_id=chapter_id,
            source_text=source_text,
            target_text=target_text,
        )
    )
    findings.extend(
        _detect_callout_candidates(
            chapter_id=chapter_id,
            source_text=source_text,
            target_text=target_text,
        )
    )
    findings.extend(
        _detect_question_answer_structure(
            chapter_id=chapter_id,
            source_text=source_text,
            target_text=target_text,
        )
    )
    return findings


def _looks_like_collapsed_numbered_list(*, source_text: str, target_text: str) -> bool:
    source_items = _extract_numbered_block_items(source_text)
    if not _has_sequential_run(source_items, min_run=3, require_start_at_one=True):
        return False
    if _has_numbered_block_run(target_text, min_run=3):
        return False
    return _has_inline_numbered_run(target_text, min_run=3)


def _detect_list_structure_loss(
    *,
    chapter_id: str,
    source_text: str,
    target_text: str,
) -> list[PublishingAuditFinding]:
    source_items = _extract_numbered_block_items(source_text)
    if not _has_sequential_run(source_items, min_run=3, require_start_at_one=True):
        return []

    target_items = _extract_numbered_block_items(target_text)
    if source_items == target_items:
        return []

    return [
        _build_audit_finding(
            chapter_id=chapter_id,
            finding_type="list_structure_loss",
            severity="high",
            source_excerpt=_excerpt(source_text),
            target_excerpt=_excerpt(target_text),
            reason="Ordered list cardinality or block structure drifted between source and target.",
            auto_fixable=True,
            confidence=0.9,
            source_signature=_list_structure_loss_signature(source_text),
        )
    ]


def _detect_possible_omissions(
    *,
    chapter_id: str,
    source_text: str,
    target_text: str,
) -> list[PublishingAuditFinding]:
    if _looks_like_collapsed_numbered_list(source_text=source_text, target_text=target_text):
        return []

    source_sentence_count = _sentence_count(source_text)
    target_sentence_count = _sentence_count(target_text)
    if source_sentence_count >= 3 and target_sentence_count >= source_sentence_count:
        return []

    source_units = _extract_structural_units(source_text)
    target_units = _extract_structural_units(target_text)

    if len(source_units) < 3:
        return []
    if len(target_units) >= len(source_units):
        return []

    missing_count = len(source_units) - len(target_units)
    if missing_count <= 0:
        return []

    missing_units = source_units[-missing_count:]
    return [
        _build_audit_finding(
            chapter_id=chapter_id,
            finding_type="possible_omission",
            severity="medium",
            source_excerpt=_excerpt("\n".join(missing_units)),
            target_excerpt=_excerpt(target_text),
            reason=(
                "Source contains additional structural units that are not represented in target; "
                "review for potential omissions."
            ),
            auto_fixable=False,
            confidence=0.65,
            source_signature=_possible_omission_signature(missing_units),
        )
    ]


def _detect_callout_candidates(
    *,
    chapter_id: str,
    source_text: str,
    target_text: str,
) -> list[PublishingAuditFinding]:
    quote_matches = re.findall(r'["\u201c\u201d](.{12,140}?)["\u201c\u201d]', source_text)
    if not quote_matches:
        return []

    cue_present = bool(
        re.search(
            r"\b(remember|note|important|key point|takeaway)\b",
            source_text,
            re.I,
        )
    )
    target_has_quote_marker = bool(
        re.search(r'["\u201c\u201d\u300c\u300d\u300e\u300f]', target_text)
    )
    if not cue_present or target_has_quote_marker:
        return []

    source_excerpt = quote_matches[0].strip()
    return [
        _build_audit_finding(
            chapter_id=chapter_id,
            finding_type="callout_candidate",
            severity="medium",
            source_excerpt=_excerpt(source_excerpt),
            target_excerpt=_excerpt(target_text),
            reason=(
                "Source highlights a short quoted emphasis line with cue words; target may need "
                "explicit callout treatment."
            ),
            auto_fixable=True,
            confidence=0.75,
            source_signature=f"callout_candidate:{_signature_token(source_excerpt)}",
        )
    ]


def _detect_question_answer_structure(
    *,
    chapter_id: str,
    source_text: str,
    target_text: str,
) -> list[PublishingAuditFinding]:
    source_questions = _count_qa_markers(source_text, marker_kind="question")
    source_answers = _count_qa_markers(source_text, marker_kind="answer")
    if source_questions == 0 or source_answers == 0:
        return []

    target_questions = _count_qa_markers(target_text, marker_kind="question")
    target_answers = _count_qa_markers(target_text, marker_kind="answer")
    if target_questions >= source_questions and target_answers >= source_answers:
        return []

    return [
        _build_audit_finding(
            chapter_id=chapter_id,
            finding_type="question_answer_structure",
            severity="medium",
            source_excerpt=_excerpt(source_text),
            target_excerpt=_excerpt(target_text),
            reason=(
                "Question/answer markers in source are not fully preserved in target; verify "
                "Q&A block structure."
            ),
            auto_fixable=False,
            confidence=0.7,
            source_signature=(
                f"question_answer_structure:q{source_questions}:a{source_answers}"
            ),
        )
    ]


def _build_audit_finding(
    *,
    chapter_id: str,
    finding_type: str,
    severity: str,
    source_excerpt: str,
    target_excerpt: str,
    reason: str,
    auto_fixable: bool,
    confidence: float,
    source_signature: str | None = None,
) -> PublishingAuditFinding:
    return PublishingAuditFinding(
        chapter_id=chapter_id,
        block_id=None,
        source_signature=source_signature,
        finding_type=finding_type,
        severity=severity,
        source_excerpt=source_excerpt,
        target_excerpt=target_excerpt,
        reason=reason,
        auto_fixable=auto_fixable,
        confidence=confidence,
        agent_role="audit",
    )


def _collapsed_numbered_list_signature(source_text: str) -> str:
    items = _extract_numbered_block_items(source_text)
    if not items:
        return "collapsed_numbered_list:none"
    run = "-".join(str(item) for item in items[:5])
    return f"collapsed_numbered_list:{run}"


def _list_structure_loss_signature(source_text: str) -> str:
    items = _extract_numbered_block_items(source_text)
    if not items:
        return "list_structure_loss:none"
    run = "-".join(str(item) for item in items[:5])
    return f"list_structure_loss:{run}"


def _possible_omission_signature(missing_units: list[str]) -> str:
    normalized_units = [_signature_token(unit) for unit in missing_units if _signature_token(unit)]
    joined = "-".join(normalized_units[:3]) or "none"
    return f"possible_omission:{len(missing_units)}:{joined}"


def _extract_numbered_block_items(text: str) -> list[int]:
    items: list[int] = []
    for line in text.splitlines():
        match = re.match(r"^\s*(\d{1,3})[.)]\s+\S", line)
        if match is None:
            continue
        items.append(int(match.group(1)))
    return items


def _has_numbered_block_run(text: str, *, min_run: int) -> bool:
    return _has_sequential_run(
        _extract_numbered_block_items(text),
        min_run=min_run,
        require_start_at_one=True,
    )


def _has_inline_numbered_run(text: str, *, min_run: int) -> bool:
    for line in text.splitlines():
        markers = [int(match.group(1)) for match in _NUMBERED_MARKER_RE.finditer(line)]
        if _has_sequential_run(markers, min_run=min_run, require_start_at_one=True):
            return True
    return False


def _has_sequential_run(
    values: list[int],
    *,
    min_run: int,
    require_start_at_one: bool,
) -> bool:
    if len(values) < min_run:
        return False

    run_length = 1
    for index in range(1, len(values)):
        if values[index] == values[index - 1] + 1:
            run_length += 1
        else:
            run_length = 1
        if run_length >= min_run:
            if not require_start_at_one:
                return True
            run_start = values[index - run_length + 1]
            if run_start == 1:
                return True
    return False


def _extract_structural_units(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    units: list[str] = []
    paragraphs = [
        segment.strip()
        for segment in re.split(r"\n\s*\n+", normalized)
        if segment.strip()
    ]
    for paragraph in paragraphs:
        if _looks_like_structured_line_block(paragraph):
            for line in paragraph.splitlines():
                line_unit = line.strip()
                if line_unit and _is_meaningful_unit(line_unit):
                    units.append(line_unit)
            continue

        compact = re.sub(r"\s+", " ", paragraph).strip()
        sentence_candidates = [
            item for item in _split_sentences(compact) if _is_meaningful_unit(item)
        ]
        if len(sentence_candidates) >= 3:
            units.extend(sentence_candidates)
        else:
            units.append(compact)
    return units


def _looks_like_structured_line_block(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    return all(_STRUCTURED_LINE_RE.match(line) for line in lines)


def _split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for match in re.finditer(r"[^.!?\u3002\uff01\uff1f]+[.!?\u3002\uff01\uff1f]?", text):
        sentence = match.group(0).strip()
        if sentence:
            sentences.append(sentence)
    return sentences


def _sentence_count(text: str) -> int:
    compact = re.sub(r"\s+", " ", text.replace("\n", " ").strip())
    if not compact:
        return 0
    return len(_split_sentences(compact))


def _is_meaningful_unit(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"[.!?,;:\u3002\uff01\uff1f\uff0c\uff1b\uff1a\"'()\[\]{}]", "", compact)
    if not compact:
        return False
    if _CJK_RE.search(compact):
        return len(compact) >= 4
    return len(re.findall(r"[A-Za-z0-9]", compact)) >= 4


def _count_qa_markers(text: str, *, marker_kind: str) -> int:
    if marker_kind == "question":
        pattern = r"(?mi)^\s*(?:q|question|\u95ee)\s*[:\uff1a]"
    else:
        pattern = r"(?mi)^\s*(?:a|answer|\u7b54)\s*[:\uff1a]"
    return len(re.findall(pattern, text))


def _excerpt(text: str, *, max_len: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_len:
        return compact
    return f"{compact[: max_len - 1]}..."


def _signature_token(text: str, *, max_words: int = 6) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    if words:
        return "-".join(words[:max_words])

    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
    if cjk_chars:
        return "".join(cjk_chars[:8])

    compact = re.sub(r"\s+", "-", text.strip().lower())
    compact = re.sub(r"[^a-z0-9\-\u4e00-\u9fff]", "", compact)
    return compact[:32] or "none"
