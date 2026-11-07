"""Opportunity clustering runtime producer (WP-A, purely additive).

WAVE-AB5 scope: 06 §6 — "Opportunity output should be organized into
explainable clusters, not only a top-N list", each class with a formal
definition, and each cluster answering the FIVE corpus questions (why-now /
what could invalidate / what evidence disagrees / risk-adjusted
interpretation / what information is missing). The AI-1 contracts
(``app.domain.opportunity``) existed with strict tests but had NO runtime
producer; this module is that producer, deterministically, over
market-intelligence ``OpportunityRank`` rows.

Governance binding:
- ``run_id`` is REQUIRED (non-empty) — every produced object/cluster binds
  to the governing run (mirrors the strict contract tests);
- ``created_at_utc`` is a REQUIRED caller-supplied instant — this module
  never reads a wall clock;
- ``declared_context`` is the caller-DECLARED map (watchlist membership,
  dedicated M&A signal evidence ids, rotation industries). M&A signals are
  NEVER inferred from a score (06 §4): they exist only when the caller
  declares dedicated evidence ids.

Classification (explicit declared rules, first match wins, module
constants — no discretion, no data-inferred classes):
- KIND (one of the 4 corpus opportunity kinds) and CLASS (one of the 7
  formal candidate-class labels) are decided by the ordered rule tables
  below; a rank matching NO kind rule or NO class rule causes a typed
  refusal (``OpportunityClusteringRefusal``) — unclassified objects are
  never silently clustered or dropped (mirrors
  ``cluster_requires_concrete_class``).
- missing data is surfaced, never invented: cluster ``missing_information``
  always carries explicit not-available notes; evidence ids are
  deterministic REFERENCES to items of the rank payload (the payload itself
  is never fabricated).

No network, no I/O, no clock reads, no LLM, no RNG; identical inputs yield
identical clusters. Nothing here registers, promotes or applies anything.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from app.domain.market_intelligence import OpportunityRank
from app.domain.opportunity import (
    ClassDefinition,
    OpportunityCluster,
    OpportunityObject,
)

__all__ = [
    "OPPORTUNITY_CLUSTERING_VERSION",
    "DECLARED_CLASS_DEFINITIONS",
    "OpportunityClusteringRefusal",
    "OpportunityClusteringResult",
    "build_opportunity_clusters",
]

OPPORTUNITY_CLUSTERING_VERSION = "OPPORTUNITY-CLUSTERING-V1"

# ---------------------------------------------------------------------------
# Declared thresholds / vocabularies (module constants — the ONLY thresholds)
# ---------------------------------------------------------------------------

STOCK_CANDIDATE_MIN_OVERALL = 60.0
STOCK_CANDIDATE_MIN_MONEY_FLOW = 55.0

VOLUME_EXPANSION_MIN_MONEY_FLOW = 70.0
BREAKOUT_MIN_TECHNICAL = 70.0
BREAKOUT_MIN_OVERALL = 65.0
EARLY_ACCUMULATION_MIN_MONEY_FLOW = 55.0
EARLY_ACCUMULATION_MAX_RISK = 60.0
EARLY_ACCUMULATION_MIN_OVERALL = 50.0
OVERSOLD_RECOVERY_MIN_FUNDAMENTAL = 60.0
OVERSOLD_RECOVERY_MAX_TECHNICAL = 40.0
OVERSOLD_RECOVERY_MIN_OVERALL = 45.0
RELATIVE_STRENGTH_MIN_OVERALL = 55.0

#: Evidence categories that count as event/news evidence (declared).
EVENT_NEWS_CATEGORIES: frozenset[str] = frozenset({"event", "news"})

#: Declared context keys the builder reads (everything else is ignored).
CONTEXT_WATCHLIST_KEY = "watchlist_symbols"
CONTEXT_MA_KEY = "ma_signal_evidence"
CONTEXT_ROTATION_KEY = "rotation_industries"

# ---------------------------------------------------------------------------
# Formal class definitions (06 §6 — declared; historical evaluation is NEVER
# fabricated: historical_evaluation_ref stays None)
# ---------------------------------------------------------------------------

DECLARED_CLASS_DEFINITIONS: Dict[str, ClassDefinition] = {
    label: ClassDefinition(
        label=label,  # type: ignore[arg-type]
        formal_definition=formal,
        data_prerequisites=prereqs,
        time_horizon=horizon,
    )
    for label, formal, prereqs, horizon in (
        (
            "EARLY_ACCUMULATION",
            "Sustained quiet buying with rising money flow and flat price over the declared window.",
            ("money_flow", "volume", "close_series"),
            "swing",
        ),
        (
            "BREAKOUT_CANDIDATE",
            "Technical strength above the declared breakout thresholds while the composite confirms.",
            ("technical_indicators", "close_series"),
            "swing",
        ),
        (
            "RELATIVE_STRENGTH",
            "Composite score above the declared relative-strength threshold versus the peer set.",
            ("composite_scores", "peer_scores"),
            "swing",
        ),
        (
            "VOLUME_EXPANSION",
            "Money-flow evidence above the declared volume-expansion threshold.",
            ("money_flow", "volume"),
            "short",
        ),
        (
            "INDUSTRY_ROTATION",
            "Caller-DECLARED rotation industry membership (industry-level, not stock-specific).",
            ("declared_rotation_context",),
            "swing",
        ),
        (
            "OVERSOLD_RECOVERY",
            "Fundamental value above the declared threshold while technical evidence is still weak.",
            ("fundamental_scores", "technical_indicators"),
            "swing",
        ),
        (
            "MATERIAL_FUNDAMENTAL_EVENT_CHANGE",
            "Material event/news/MA evidence present, or a declared material fundamental change.",
            ("event_evidence", "news_evidence", "ma_evidence"),
            "event",
        ),
    )
}

# Declared invalidation conditions per class (guarantees non-empty honesty).
_DECLARED_CLASS_INVALIDATIONS: Dict[str, Tuple[str, ...]] = {
    "EARLY_ACCUMULATION": (
        f"money_flow_score falls below {EARLY_ACCUMULATION_MIN_MONEY_FLOW}",
        "buying turns price-impulsive instead of quiet accumulation",
    ),
    "BREAKOUT_CANDIDATE": (
        f"technical_score falls below {BREAKOUT_MIN_TECHNICAL}",
        "composite fails to confirm the breakout",
    ),
    "RELATIVE_STRENGTH": (
        f"overall_score falls below {RELATIVE_STRENGTH_MIN_OVERALL}",
        "peer set overtakes the member",
    ),
    "VOLUME_EXPANSION": (
        f"money_flow_score falls below {VOLUME_EXPANSION_MIN_MONEY_FLOW}",
        "volume expansion reverses without price follow-through",
    ),
    "INDUSTRY_ROTATION": (
        "declared rotation context is withdrawn by the caller",
        "industry breadth collapses",
    ),
    "OVERSOLD_RECOVERY": (
        f"fundamental_score falls below {OVERSOLD_RECOVERY_MIN_FUNDAMENTAL}",
        "technical weakness deepens instead of recovering",
    ),
    "MATERIAL_FUNDAMENTAL_EVENT_CHANGE": (
        "the underlying event/news evidence is retracted or superseded",
        "the declared MA evidence is withdrawn",
    ),
}

# Risk semantics per class (declared band, honest wording).
_DECLARED_CLASS_RISK: Dict[str, str] = {
    "EARLY_ACCUMULATION": "medium; liquidity contraction invalidates the accumulation reading",
    "BREAKOUT_CANDIDATE": "medium-high; failed breakouts carry fast downside",
    "RELATIVE_STRENGTH": "medium; relative strength decays with the peer cycle",
    "VOLUME_EXPANSION": "high; one-sided flow can reverse violently",
    "INDUSTRY_ROTATION": "medium; rotation call is industry-level, not stock-specific",
    "OVERSOLD_RECOVERY": "medium; value trap risk while technicals stay weak",
    "MATERIAL_FUNDAMENTAL_EVENT_CHANGE": "high; event outcomes are binary and timing-uncertain",
}

# Constant honest missing-information notes (data NOT in the rank payload).
_MISSING_IN_RANK_PAYLOAD: Tuple[str, ...] = (
    "per-symbol volume_ratio is not available in the rank payload",
    "per-symbol order-book / institutional queue depth is not available in the rank payload",
    "per-symbol close-series history is not available in the rank payload",
)

# ---------------------------------------------------------------------------
# Typed refusal (mirrors RegimeSliceViolation discipline)
# ---------------------------------------------------------------------------


class OpportunityClusteringRefusal(ValueError):
    """Deterministic clustering refusal carrying a machine-readable reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}:{detail}" if detail else reason
        super().__init__(message)


def _refuse(reason: str, detail: str) -> None:
    raise OpportunityClusteringRefusal(reason, detail)


# ---------------------------------------------------------------------------
# Deterministic evidence references (ids point INTO the rank payload)
# ---------------------------------------------------------------------------


def _rank_row_ref(symbol: str) -> str:
    return f"RANK-ROW:{symbol}"


def _evidence_item_ref(symbol: str, index: int, item: Mapping[str, Any]) -> str:
    category = str(item.get("category") or "unknown")
    name = str(item.get("name") or "unnamed")
    return f"RANK-EVIDENCE:{symbol}:{index}:{category}:{name}"


def _negative_evidence_refs(symbol: str, evidence: Sequence[Mapping[str, Any]]) -> Tuple[str, ...]:
    refs = [
        _evidence_item_ref(symbol, i, item)
        for i, item in enumerate(evidence)
        if str(item.get("direction") or "neutral") == "negative"
    ]
    return tuple(sorted(set(refs)))


# ---------------------------------------------------------------------------
# Declared rule tables (first match wins; order is part of the contract)
# ---------------------------------------------------------------------------


def _classify_kind(
    rank: OpportunityRank, declared_context: Mapping[str, Any]
) -> Tuple[str, str, str]:
    """Returns (kind, basis, rule_id); refuses when nothing matches."""
    symbol = rank.symbol
    ma_map = declared_context.get(CONTEXT_MA_KEY) or {}
    if isinstance(ma_map, Mapping) and tuple(ma_map.get(symbol) or ()):
        # 06 §4: an MA signal requires ITS OWN evidence — declared ids only,
        # never inferred from the opportunity score.
        return "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL", "EVIDENCE_BASED", "MA-DECLARED-EVIDENCE"
    if any(str(item.get("category") or "") in EVENT_NEWS_CATEGORIES for item in rank.evidence):
        return "EVENT_NEWS_DRIVEN_CANDIDATE", "EVIDENCE_BASED", "EVENT-NEWS-EVIDENCE"
    watchlist = declared_context.get(CONTEXT_WATCHLIST_KEY) or ()
    if symbol in watchlist:
        return "USER_WATCHLIST_COMPANY_INTELLIGENCE", "EVIDENCE_BASED", "DECLARED-WATCHLIST"
    if (
        rank.overall_score >= STOCK_CANDIDATE_MIN_OVERALL
        and rank.money_flow_score >= STOCK_CANDIDATE_MIN_MONEY_FLOW
    ):
        return "MARKET_STOCK_INVESTMENT_CANDIDATE", "OPPORTUNITY_SCORE_ONLY", "SCORE-THRESHOLD"
    _refuse(
        "rank_unclassified_kind",
        f"symbol={symbol!r} matched no declared kind rule "
        f"(overall={rank.overall_score}, money_flow={rank.money_flow_score}, "
        f"recommendation={rank.recommendation!r})",
    )
    raise AssertionError("unreachable")  # pragma: no cover


def _classify_class(
    rank: OpportunityRank, kind: str, declared_context: Mapping[str, Any]
) -> Tuple[str, str]:
    """Returns (class_label, rule_id); refuses when nothing matches."""
    rotation = declared_context.get(CONTEXT_ROTATION_KEY) or ()
    if kind in ("CORPORATE_MA_ACQUISITION_TARGET_SIGNAL", "EVENT_NEWS_DRIVEN_CANDIDATE"):
        return "MATERIAL_FUNDAMENTAL_EVENT_CHANGE", "MATERIAL-EVENT-KIND"
    if rank.money_flow_score >= VOLUME_EXPANSION_MIN_MONEY_FLOW:
        return "VOLUME_EXPANSION", "MONEY-FLOW-THRESHOLD"
    if rank.technical_score >= BREAKOUT_MIN_TECHNICAL and rank.overall_score >= BREAKOUT_MIN_OVERALL:
        return "BREAKOUT_CANDIDATE", "TECHNICAL-BREAKOUT-THRESHOLD"
    if (
        rank.money_flow_score >= EARLY_ACCUMULATION_MIN_MONEY_FLOW
        and rank.risk_score <= EARLY_ACCUMULATION_MAX_RISK
        and rank.overall_score >= EARLY_ACCUMULATION_MIN_OVERALL
    ):
        return "EARLY_ACCUMULATION", "QUIET-ACCUMULATION-THRESHOLD"
    if (
        rank.fundamental_score >= OVERSOLD_RECOVERY_MIN_FUNDAMENTAL
        and rank.technical_score < OVERSOLD_RECOVERY_MAX_TECHNICAL
        and rank.overall_score >= OVERSOLD_RECOVERY_MIN_OVERALL
    ):
        return "OVERSOLD_RECOVERY", "OVERSOLD-VALUE-THRESHOLD"
    if rank.overall_score >= RELATIVE_STRENGTH_MIN_OVERALL:
        return "RELATIVE_STRENGTH", "COMPOSITE-RELATIVE-STRENGTH"
    if rank.industry and rank.industry in rotation:
        return "INDUSTRY_ROTATION", "DECLARED-ROTATION-CONTEXT"
    _refuse(
        "rank_unclassified_class",
        f"symbol={rank.symbol!r} matched no declared class rule "
        f"(overall={rank.overall_score}, technical={rank.technical_score}, "
        f"money_flow={rank.money_flow_score}, fundamental={rank.fundamental_score}, "
        f"risk={rank.risk_score})",
    )
    raise AssertionError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class OpportunityClusteringResult:
    """Lightweight deterministic result envelope (clusters + objects)."""

    def __init__(
        self,
        *,
        run_id: str,
        created_at_utc: datetime,
        objects: Tuple[OpportunityObject, ...],
        clusters: Tuple[OpportunityCluster, ...],
    ) -> None:
        self.run_id = run_id
        self.created_at_utc = created_at_utc
        self.objects = objects
        self.clusters = clusters

    def model_dump(self, mode: str = "python") -> Dict[str, Any]:
        return {
            "clustering_version": OPPORTUNITY_CLUSTERING_VERSION,
            "run_id": self.run_id,
            "created_at_utc": self.created_at_utc.isoformat(),
            "objects": [o.model_dump(mode=mode) for o in self.objects],
            "clusters": [c.model_dump(mode=mode) for c in self.clusters],
            "object_count": len(self.objects),
            "cluster_count": len(self.clusters),
        }


def build_opportunity_clusters(
    ranks: Sequence[OpportunityRank],
    *,
    run_id: str,
    created_at_utc: datetime,
    declared_context: Mapping[str, Any] | None = None,
    expiry_utc: datetime | None = None,
    expiry_open_ended: bool = True,
) -> OpportunityClusteringResult:
    """Deterministically cluster market-intelligence ranks (06 §6).

    Parameters
    ----------
    ranks:
        Market-intelligence ``OpportunityRank`` rows (any order; grouping is
        deterministic and duplicate symbols are refused).
    run_id:
        REQUIRED non-empty governance binding (objects + clusters carry it).
    created_at_utc:
        REQUIRED caller-supplied instant (no wall clock anywhere).
    declared_context:
        Caller-DECLARED map: ``watchlist_symbols`` (list), ``ma_signal_evidence``
        ({symbol: [dedicated evidence ids]}), ``rotation_industries`` (list).
        M&A signals exist ONLY from declared dedicated evidence — never from
        a score (06 §4).
    expiry_utc / expiry_open_ended:
        Explicit expiry decision passed through to the objects (the contract
        refuses forgotten defaults).

    Returns
    -------
    OpportunityClusteringResult
        ``objects`` (one per rank, each with exactly one declared kind+class)
        and ``clusters`` (grouped by (industry, class), each carrying the
        FIVE corpus explanations built honestly from the rank data — missing
        data becomes explicit not-available notes).

    Refusals (``OpportunityClusteringRefusal``): ``run_id_required``,
    ``duplicate_rank_symbol``, ``rank_unclassified_kind``,
    ``rank_unclassified_class``.
    """
    context = dict(declared_context or {})
    if not isinstance(run_id, str) or not run_id.strip():
        _refuse("run_id_required", "governance binding requires a non-empty run_id")
    created = created_at_utc

    objects: List[OpportunityObject] = []
    seen_symbols: set[str] = set()
    for rank in ranks:
        symbol = rank.symbol
        if symbol in seen_symbols:
            _refuse("duplicate_rank_symbol", f"symbol={symbol!r} appears twice in the rank set")
        seen_symbols.add(symbol)
        kind, basis, rule_id = _classify_kind(rank, context)
        class_label, class_rule_id = _classify_class(rank, kind, context)
        evidence_refs = [_rank_row_ref(symbol)]
        evidence_refs.extend(
            _evidence_item_ref(symbol, i, item) for i, item in enumerate(rank.evidence)
        )
        if kind == "USER_WATCHLIST_COMPANY_INTELLIGENCE":
            evidence_refs.append(f"DECLARED-WATCHLIST-MEMBERSHIP:{symbol}")
        ma_ids = tuple(context.get(CONTEXT_MA_KEY, {}).get(symbol) or ()) if isinstance(
            context.get(CONTEXT_MA_KEY), Mapping
        ) else ()
        if kind == "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL":
            evidence_refs.extend(ma_ids)
        invalidations = list(_DECLARED_CLASS_INVALIDATIONS[class_label])
        invalidations.extend(str(w) for w in rank.warnings if w)
        trust_state = str((rank.data_trust or {}).get("state") or "unknown")
        profile = (
            f"overall={rank.overall_score}, technical={rank.technical_score}, "
            f"money_flow={rank.money_flow_score}, fundamental={rank.fundamental_score}, "
            f"filter={rank.filter_score}, strategy={rank.strategy_score}, "
            f"risk={rank.risk_score}, recommendation={rank.recommendation}"
        )
        objects.append(
            OpportunityObject(
                object_id=f"OPP-{run_id}-{symbol}"[:128],
                opportunity_kind=kind,  # type: ignore[arg-type]
                company_role=(
                    "MA_TARGET_SIGNAL"
                    if kind == "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL"
                    else "WATCHLIST_COMPANY"
                    if kind == "USER_WATCHLIST_COMPANY_INTELLIGENCE"
                    else "INVESTMENT_CANDIDATE"
                ),
                subject=symbol,
                class_label=class_label,  # type: ignore[arg-type]
                class_definition=DECLARED_CLASS_DEFINITIONS[class_label],
                created_at_utc=created,
                reason_for_now=(
                    f"Declared rule {rule_id}/{class_rule_id} matched the rank profile: {profile}."
                )[:1000],
                confidence=Decimal(str(min(max(float(rank.confidence), 0.0), 1.0))),
                confidence_basis=(
                    "rank confidence from the deterministic trust-capped AI core aggregation"
                ),
                data_trust_state=trust_state,
                risk_semantics=(
                    f"rank risk_score={rank.risk_score}; declared class band: "
                    f"{_DECLARED_CLASS_RISK[class_label]}"
                )[:1000],
                evidence_ids=tuple(dict.fromkeys(evidence_refs)),
                contradicting_evidence_ids=_negative_evidence_refs(symbol, rank.evidence),
                invalidation_conditions=tuple(dict.fromkeys(invalidations)),
                expiry_utc=expiry_utc,
                expiry_open_ended=expiry_open_ended,
                basis=basis,  # type: ignore[arg-type]
                ma_signal_evidence_ids=tuple(dict.fromkeys(ma_ids))
                if kind == "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL"
                else (),
                run_id=run_id,
                notes=f"clustering_version={OPPORTUNITY_CLUSTERING_VERSION}",
            )
        )

    # ------------------------------------------------------------------ clusters
    groups: Dict[Tuple[str, str], List[OpportunityObject]] = {}
    for obj in objects:
        source_rank = next(r for r in ranks if r.symbol == obj.subject)
        industry = source_rank.industry or ""
        groups.setdefault((industry, obj.class_label), []).append(obj)

    clusters: List[OpportunityCluster] = []
    for (industry, class_label) in sorted(groups, key=lambda k: (k[0], k[1])):
        members = sorted(groups[(industry, class_label)], key=lambda o: o.subject)
        member_ids = tuple(o.object_id for o in members)
        member_symbols = tuple(o.subject for o in members)
        source_ranks = [next(r for r in ranks if r.symbol == o.subject) for o in members]
        strongest = max(source_ranks, key=lambda r: (r.overall_score, r.money_flow_score))
        mean_overall = sum(r.overall_score for r in source_ranks) / len(source_ranks)
        mean_risk = sum(r.risk_score for r in source_ranks) / len(source_ranks)
        max_risk = max(r.risk_score for r in source_ranks)
        trust_state = str((strongest.data_trust or {}).get("state") or "unknown")
        contradicting = tuple(
            sorted({ref for o in members for ref in o.contradicting_evidence_ids})
        )
        missing = list(_MISSING_IN_RANK_PAYLOAD)
        if not industry:
            missing.insert(0, "industry is not available in the rank payload")
        invalidations = list(_DECLARED_CLASS_INVALIDATIONS[class_label])
        invalidations.extend(
            str(w) for r in source_ranks for w in (r.warnings or ()) if w
        )
        clusters.append(
            OpportunityCluster(
                cluster_id=(
                    f"CLUSTER-{run_id}-{class_label}-"
                    + hashlib.sha256(industry.encode("utf-8")).hexdigest()[:8]
                )[:128],
                class_label=class_label,  # type: ignore[arg-type]
                class_definition=DECLARED_CLASS_DEFINITIONS[class_label],
                member_object_ids=member_ids,
                created_at_utc=created,
                run_id=run_id,
                why_now=(
                    f"Declared class rule matched for {list(member_symbols)} in industry "
                    f"{industry!r}: class {class_label}; strongest member "
                    f"{strongest.symbol!r} with overall={strongest.overall_score}, "
                    f"money_flow={strongest.money_flow_score}, "
                    f"recommendation={strongest.recommendation} "
                    f"(data trust state={trust_state})."
                )[:2000],
                invalidation_conditions=tuple(dict.fromkeys(invalidations)),
                disagreeing_evidence_ids=contradicting,
                risk_adjusted_interpretation=(
                    f"Mean overall={mean_overall:.1f}, mean risk={mean_risk:.1f}, max risk="
                    f"{max_risk:.1f} across {len(members)} member(s); declared risk band: "
                    f"{_DECLARED_CLASS_RISK[class_label]}; data trust state={trust_state} "
                    f"so no live-market claim is made; advisory only."
                )[:2000],
                missing_information=tuple(dict.fromkeys(missing)),
                confidence=Decimal(str(min(max(float(min(o.confidence for o in members)), 0.0), 1.0))),
                confidence_basis=(
                    "cluster-level deterministic aggregate: minimum member rank confidence"
                ),
                notes=f"clustering_version={OPPORTUNITY_CLUSTERING_VERSION}",
            )
        )
    return OpportunityClusteringResult(
        run_id=run_id,
        created_at_utc=created,
        objects=tuple(objects),
        clusters=tuple(clusters),
    )
