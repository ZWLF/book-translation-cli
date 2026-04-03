from __future__ import annotations

import re

from book_translator.models import PublishingAuditFinding, PublishingLayoutAnnotation

_QUOTE_SPAN_RE = re.compile(r'["“”「」『』](.{8,220}?)["“”「」『』]')


def generate_layout_annotations(
    *,
    source_text: str,
    chapter_text: str,
    findings: list[PublishingAuditFinding],
) -> list[PublishingLayoutAnnotation]:
    _ = source_text
    annotations: list[PublishingLayoutAnnotation] = []
    seen_keys: set[tuple[str, str]] = set()

    for finding in findings:
        if finding.finding_type == "callout_candidate":
            callout_text = _choose_callout_text(chapter_text=chapter_text, finding=finding)
            if not callout_text:
                continue
            _append_unique(
                annotations=annotations,
                seen_keys=seen_keys,
                annotation=PublishingLayoutAnnotation(
                    kind="callout",
                    payload={
                        "text": callout_text,
                        "chapter_id": finding.chapter_id,
                    },
                ),
                key_value=callout_text,
            )
            continue

        if finding.finding_type == "question_answer_structure":
            anchor = _choose_qa_anchor(chapter_text=chapter_text, finding=finding)
            _append_unique(
                annotations=annotations,
                seen_keys=seen_keys,
                annotation=PublishingLayoutAnnotation(
                    kind="qa_block",
                    payload={
                        "anchor": anchor,
                        "chapter_id": finding.chapter_id,
                        "has_question_marker": _has_question_marker(chapter_text),
                        "has_answer_marker": _has_answer_marker(chapter_text),
                    },
                ),
                key_value=anchor,
            )

    return annotations


def _append_unique(
    *,
    annotations: list[PublishingLayoutAnnotation],
    seen_keys: set[tuple[str, str]],
    annotation: PublishingLayoutAnnotation,
    key_value: str,
) -> None:
    key = (annotation.kind, key_value)
    if key in seen_keys:
        return
    seen_keys.add(key)
    annotations.append(annotation)


def _choose_callout_text(*, chapter_text: str, finding: PublishingAuditFinding) -> str:
    quoted_spans = [match.group(1).strip() for match in _QUOTE_SPAN_RE.finditer(chapter_text)]
    if quoted_spans:
        matched_quote = _select_quote_for_finding(quoted_spans=quoted_spans, finding=finding)
        if matched_quote:
            return matched_quote

    emphasized = _stable_emphasized_line(chapter_text)
    if emphasized:
        return emphasized

    target_excerpt = finding.target_excerpt.strip()
    if target_excerpt:
        return target_excerpt
    return _excerpt(chapter_text)


def _select_quote_for_finding(
    *,
    quoted_spans: list[str],
    finding: PublishingAuditFinding,
) -> str:
    target_excerpt = finding.target_excerpt.strip()
    context = " ".join(
        [
            target_excerpt,
            finding.source_excerpt.strip(),
            finding.reason.strip(),
        ]
    ).strip()
    context_tokens = _tokenize_for_match(context)

    scored: list[tuple[int, str]] = []
    for quote in quoted_spans:
        score = _quote_score(
            quote=quote,
            target_excerpt=target_excerpt,
            context_tokens=context_tokens,
        )
        scored.append((score, quote))

    if not scored:
        return ""

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_quote = scored[0]
    if best_score > 0:
        return best_quote
    if len(quoted_spans) == 1:
        return quoted_spans[0]
    return ""


def _quote_score(*, quote: str, target_excerpt: str, context_tokens: set[str]) -> int:
    score = 0
    quote_l = quote.lower()
    target_l = target_excerpt.lower()

    if target_l:
        if quote_l in target_l:
            score += 8
        if target_l in quote_l:
            score += 4

    quote_tokens = _tokenize_for_match(quote)
    if quote_tokens and context_tokens:
        score += len(quote_tokens & context_tokens) * 3

    return score


def _tokenize_for_match(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9]{3,}|[\u4e00-\u9fff]{2,}", text.lower())
    return set(tokens)


def _choose_qa_anchor(*, chapter_text: str, finding: PublishingAuditFinding) -> str:
    target_excerpt = finding.target_excerpt.strip()
    if target_excerpt:
        return target_excerpt
    return _excerpt(chapter_text)


def _stable_emphasized_line(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _looks_like_emphasized_line(line):
            return line
    return ""


def _looks_like_emphasized_line(line: str) -> bool:
    compact = re.sub(r"\s+", " ", line).strip()
    if not compact or len(compact) > 120:
        return False
    if re.search(r"[.!?。！？]$", compact) is None:
        return False
    return bool(
        re.search(
            r"\b(remember|note|important|key point|takeaway)\b|记住|注意|重点|要点",
            compact,
            re.IGNORECASE,
        )
    )


def _has_question_marker(text: str) -> bool:
    return bool(re.search(r"(?mi)^\s*(?:q|question|问)\s*[:：]", text))


def _has_answer_marker(text: str) -> bool:
    return bool(re.search(r"(?mi)^\s*(?:a|answer|答)\s*[:：]", text))


def _excerpt(text: str, *, max_len: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_len:
        return compact
    return f"{compact[: max_len - 1]}..."
