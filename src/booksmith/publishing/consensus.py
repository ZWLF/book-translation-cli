from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, Field

from booksmith.models import PublishingAuditFinding

LOW_CONFIDENCE_THRESHOLD = 0.6


class PublishingFindingConsensusItem(BaseModel):
    finding_key: str
    chapter_id: str
    block_id: str | None = None
    finding_type: str
    audit_finding: PublishingAuditFinding | None = None
    review_finding: PublishingAuditFinding | None = None
    arbiter_finding: PublishingAuditFinding | None = None


class PublishingFindingConsensusResult(BaseModel):
    agreed: list[PublishingFindingConsensusItem] = Field(default_factory=list)
    disputed: list[PublishingFindingConsensusItem] = Field(default_factory=list)
    low_confidence: list[PublishingFindingConsensusItem] = Field(default_factory=list)


def merge_consensus_findings(
    *,
    audit_findings: Sequence[PublishingAuditFinding],
    review_findings: Sequence[PublishingAuditFinding],
    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> PublishingFindingConsensusResult:
    grouped: dict[str, PublishingFindingConsensusItem] = {}

    for finding in _sorted_findings(audit_findings):
        _assign_consensus_finding(
            grouped=grouped,
            finding=finding,
            role="audit",
        )

    for finding in _sorted_findings(review_findings):
        _assign_consensus_finding(
            grouped=grouped,
            finding=finding,
            role="review",
        )

    result = PublishingFindingConsensusResult()
    for key in sorted(grouped):
        item = grouped[key]
        if _is_low_confidence(
            item.audit_finding,
            threshold=low_confidence_threshold,
        ) or _is_low_confidence(
            item.review_finding,
            threshold=low_confidence_threshold,
        ):
            result.low_confidence.append(item)
            continue

        if item.audit_finding is not None and item.review_finding is not None:
            if _findings_equivalent(item.audit_finding, item.review_finding):
                result.agreed.append(item)
            else:
                result.disputed.append(item)
            continue

        result.low_confidence.append(item)

    return result


def build_arbitration_queue(
    disputed_findings: Sequence[PublishingFindingConsensusItem],
) -> list[PublishingFindingConsensusItem]:
    return sorted(disputed_findings, key=lambda item: item.finding_key)


def arbiter_fix_candidates(
    *,
    consensus: PublishingFindingConsensusResult,
    arbiter_findings: Sequence[PublishingAuditFinding],
) -> list[PublishingAuditFinding]:
    candidates: dict[str, PublishingAuditFinding] = {}

    for item in consensus.agreed:
        finding = _preferred_consensus_finding(item)
        if finding is not None and finding.auto_fixable:
            candidates[finding_consensus_key(finding)] = finding

    for finding in _sorted_findings(arbiter_findings):
        if finding.auto_fixable:
            candidates[finding_consensus_key(finding)] = finding

    return [candidates[key] for key in sorted(candidates)]


def finding_consensus_key(finding: PublishingAuditFinding) -> str:
    block_id = finding.block_id or "-"
    identity = finding.source_signature or _source_excerpt_fingerprint(
        source_excerpt=finding.source_excerpt
    )
    return f"{finding.chapter_id}|{block_id}|{finding.finding_type}|{identity}"


def _sorted_findings(findings: Iterable[PublishingAuditFinding]) -> list[PublishingAuditFinding]:
    return sorted(findings, key=finding_consensus_key)


def _is_low_confidence(
    finding: PublishingAuditFinding | None,
    *,
    threshold: float,
) -> bool:
    return finding is not None and finding.confidence < threshold


def _findings_equivalent(
    left: PublishingAuditFinding,
    right: PublishingAuditFinding,
) -> bool:
    return (
        left.chapter_id == right.chapter_id
        and left.block_id == right.block_id
        and left.finding_type == right.finding_type
        and left.severity == right.severity
        and _source_identity(left) == _source_identity(right)
        and left.auto_fixable is right.auto_fixable
    )


def _preferred_consensus_finding(
    item: PublishingFindingConsensusItem,
) -> PublishingAuditFinding | None:
    findings = [
        finding
        for finding in (item.review_finding, item.audit_finding)
        if finding is not None
    ]
    if not findings:
        return None
    return max(findings, key=lambda finding: finding.confidence)


def _assign_consensus_finding(
    *,
    grouped: dict[str, PublishingFindingConsensusItem],
    finding: PublishingAuditFinding,
    role: str,
) -> None:
    key = finding_consensus_key(finding)
    item = grouped.setdefault(
        key,
        PublishingFindingConsensusItem(
            finding_key=key,
            chapter_id=finding.chapter_id,
            block_id=finding.block_id,
            finding_type=finding.finding_type,
        ),
    )

    if role == "audit":
        if item.audit_finding is not None:
            raise ValueError(f"Duplicate audit finding for consensus key: {key}")
        item.audit_finding = finding
        return

    if role == "review":
        if item.review_finding is not None:
            raise ValueError(f"Duplicate review finding for consensus key: {key}")
        item.review_finding = finding
        return

    raise ValueError(f"Unsupported consensus role: {role}")


def _source_excerpt_fingerprint(*, source_excerpt: str) -> str:
    normalized = _normalize_excerpt(source_excerpt)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _normalize_excerpt(text: str) -> str:
    return " ".join(text.split())


def _source_identity(finding: PublishingAuditFinding) -> str:
    return finding.source_signature or _source_excerpt_fingerprint(
        source_excerpt=finding.source_excerpt
    )
