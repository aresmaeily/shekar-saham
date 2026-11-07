"""Deterministic primary-precedence conflict resolution (WP-G / G3).

WAVE-AB4 (2026-11-08, MASTER-CONTINUOUS-EXECUTION directive §10 G3): the
evidence audit recorded a HIGH gap — precedence tier→class mapping existed
and was validator-enforced, but NO resolver actually applied
primary-over-secondary to close a conflict: every conflict stayed OPEN until
a caller hand-wrote a rule string. This module implements the explicit
deterministic rule:

    PRIMARY sources take precedence over SECONDARY sources; within the same
    precedence class the rule is NOT APPLICABLE (the conflict stays OPEN —
    nothing is resolved by an arbitrary tie-break).

Honesty invariants (never violated):

- A resolution names the rule (``PRIMARY_OVER_SECONDARY_V1``), the acting
  reviewer id (the caller-supplied accountable name), and the resolution
  time (caller-supplied; this module reads NO clock).
- The loser values are NEVER deleted: the resolution record names winner
  and losers explicitly, and the original EvidenceItems are untouched
  (immutability is structural — frozen models).
- Deterministic total order for winner selection: precedence class
  (PRIMARY first) → publication KNOWN before UNAVAILABLE → earlier
  publication_time_utc first → source_id lexicographic (final, explicit).
- No corroboration inflation: winning does not make the winner CORROBORATED.
- Cross-tier same-class conflicts stay OPEN (rule not applicable).
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.domain.evidence import EvidenceConflict, EvidenceItem

#: The ONLY deterministic resolution rule this module implements. Closed on
#: purpose: a resolution that cannot name its rule is a silent reconciliation.
PRIMARY_OVER_SECONDARY_V1 = "PRIMARY_OVER_SECONDARY_V1"

_RULES: tuple[str, ...] = (PRIMARY_OVER_SECONDARY_V1,)

_RESOLUTION_NOTE_PREFIX = "deterministic-resolution:"


class ResolutionRefusal(ValueError):
    """Raised when the rule cannot resolve a conflict honestly.

    Subclasses ValueError so callers' fail-closed except ValueError
    handlers (the repo's deterministic-refusal convention) catch it."""

    def __init__(self, reason: str, conflict_id: str) -> None:
        super().__init__(f"{reason}:{conflict_id}")
        self.reason = reason
        self.conflict_id = conflict_id


class ConflictResolutionRecord(BaseModel):
    """One resolved conflict's auditable resolution row (append-only)."""

    model_config = ConfigDict(frozen=True)

    conflict_id: str = Field(min_length=1)
    rule_id: str
    winner_evidence_id: str = Field(min_length=1)
    loser_evidence_ids: tuple[str, ...] = Field(min_length=1)
    winner_source_id: str = Field(min_length=1)
    loser_source_ids: tuple[str, ...] = Field(min_length=1)
    winner_precedence: str
    loser_precedences: tuple[str, ...]
    resolved_by: str = Field(min_length=1)
    resolved_at_utc: datetime
    rationale: str = Field(min_length=1)


def _precedence_of(item: EvidenceItem, tier_precedence: Mapping[str, str]) -> str:
    tier = str(item.source_tier)
    if tier not in tier_precedence:
        raise ResolutionRefusal("tier_not_in_precedence_map", item.evidence_id)
    return tier_precedence[tier]


def _selection_key(item: EvidenceItem, precedence: str) -> tuple:
    """Deterministic, documented total order (stable, no clock)."""
    pub_known = 0 if item.publication_status == "KNOWN" else 1
    pub_time = item.publication_time_utc.timestamp() if item.publication_time_utc is not None else 0.0
    return (0 if precedence == "PRIMARY" else 1, pub_known, pub_time, item.source_id, item.evidence_id)


def resolve_conflict_by_precedence(
    conflict: EvidenceConflict,
    evidence_items: Iterable[EvidenceItem],
    *,
    tier_precedence: Mapping[str, str],
    resolved_by: str,
    resolved_at_utc: datetime,
    rule_id: str = PRIMARY_OVER_SECONDARY_V1,
) -> tuple[EvidenceConflict, ConflictResolutionRecord]:
    """Resolve ONE conflict under ``PRIMARY_OVER_SECONDARY_V1``.

    Returns the RESOLVED_DETERMINISTIC conflict (a NEW frozen record — the
    input conflict is never mutated) plus the audit row. Deterministic
    refusals (ValueError subclass) — the conflict stays OPEN under any of
    them and NOTHING is resolved:

    - ``rule_unknown`` — rule_id not in the closed rule vocabulary;
    - ``conflict_already_resolved`` — only OPEN conflicts are eligible;
    - ``evidence_missing`` — a conflict party has no EvidenceItem;
    - ``rule_not_applicable_same_precedence`` — every party shares one
      precedence class (the rule is primary-over-secondary ONLY).
    """
    if rule_id not in _RULES:
        raise ResolutionRefusal("rule_unknown", conflict.conflict_id)
    if conflict.status != "OPEN":
        raise ResolutionRefusal("conflict_already_resolved", conflict.conflict_id)
    by_id = {i.evidence_id: i for i in evidence_items}
    parties: list[EvidenceItem] = []
    for evidence_id in conflict.evidence_ids:
        item = by_id.get(evidence_id)
        if item is None:
            raise ResolutionRefusal("evidence_missing", conflict.conflict_id)
        parties.append(item)
    precedences = {p.evidence_id: _precedence_of(p, tier_precedence) for p in parties}
    classes = set(precedences.values())
    if len(classes) == 1:
        raise ResolutionRefusal("rule_not_applicable_same_precedence", conflict.conflict_id)

    ranked = sorted(parties, key=lambda p: _selection_key(p, precedences[p.evidence_id]))
    winner = ranked[0]
    losers = [p for p in ranked[1:]]
    winner_class = precedences[winner.evidence_id]
    if any(precedences[l.evidence_id] == winner_class for l in losers):
        # a same-class loser under the winner: still deterministic (the total
        # order decides), but the rule name would lie — refuse honestly.
        raise ResolutionRefusal("rule_not_applicable_same_precedence", conflict.conflict_id)

    note = (
        f"{_RESOLUTION_NOTE_PREFIX} rule={rule_id}; "
        f"winner={winner.evidence_id} ({winner_class}); "
        f"losers={[l.evidence_id for l in losers]} "
        f"({[precedences[l.evidence_id] for l in losers]}); "
        f"loser values preserved on record; nothing deleted"
    )
    resolved = EvidenceConflict(
        conflict_id=conflict.conflict_id,
        evidence_ids=conflict.evidence_ids,
        description=conflict.description,
        status="RESOLVED_DETERMINISTIC",
        resolution_rule=rule_id,
        resolved_by=resolved_by,
        resolved_at_utc=resolved_at_utc,
        notes=(conflict.notes + " | " + note).strip(" |"),
    )
    record = ConflictResolutionRecord(
        conflict_id=conflict.conflict_id,
        rule_id=rule_id,
        winner_evidence_id=winner.evidence_id,
        loser_evidence_ids=tuple(l.evidence_id for l in losers),
        winner_source_id=winner.source_id,
        loser_source_ids=tuple(l.source_id for l in losers),
        winner_precedence=winner_class,
        loser_precedences=tuple(precedences[l.evidence_id] for l in losers),
        resolved_by=resolved_by,
        resolved_at_utc=resolved_at_utc,
        rationale=(
            "PRIMARY evidence outranks SECONDARY under the closed rule "
            f"{rule_id}; ties would be refused, not broken silently"
        ),
    )
    return resolved, record


def resolve_conflicts_by_precedence(
    conflicts: Iterable[EvidenceConflict],
    evidence_items: Iterable[EvidenceItem],
    *,
    tier_precedence: Mapping[str, str],
    resolved_by: str,
    resolved_at_utc: datetime,
    rule_id: str = PRIMARY_OVER_SECONDARY_V1,
) -> tuple[tuple[EvidenceConflict, ...], tuple[ConflictResolutionRecord, ...], tuple[Mapping[str, str], ...]]:
    """Batch resolution in deterministic conflict_id order.

    Returns (resolved_conflicts, audit_records, refusals) where ``refusals``
    rows are ``{"conflict_id", "reason"}`` dicts for conflicts the rule
    honestly refused (they stay OPEN in the input set's vocabulary — the
    caller keeps them explicit). The original conflict objects are never
    mutated; resolved outputs are NEW records.
    """
    items = list(evidence_items)
    ordered = sorted(conflicts, key=lambda c: c.conflict_id)
    resolved: list[EvidenceConflict] = []
    records: list[ConflictResolutionRecord] = []
    refusals: list[dict[str, str]] = []
    for conflict in ordered:
        try:
            new_conflict, record = resolve_conflict_by_precedence(
                conflict,
                items,
                tier_precedence=tier_precedence,
                resolved_by=resolved_by,
                resolved_at_utc=resolved_at_utc,
                rule_id=rule_id,
            )
        except ResolutionRefusal as refusal:
            refusals.append({"conflict_id": conflict.conflict_id, "reason": refusal.reason})
            continue
        resolved.append(new_conflict)
        records.append(record)
    return tuple(resolved), tuple(records), tuple(refusals)
