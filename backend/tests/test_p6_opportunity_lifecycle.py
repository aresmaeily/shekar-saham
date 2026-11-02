"""P6 opportunity internal-lifecycle tests (additive; repo-side contracts).

Scope: the INTERNAL lifecycle contracts of ``app/domain/opportunity.py`` —
the corpus-mandated four-way opportunity-kind distinction (02 lines 148–153),
the UNCLASSIFIED honesty state (06 §6: a class label may only exist together
with its formal definition, never fabricated), the mandatory why-now /
invalidation discipline (on objects AND clusters, independently), the
expiry/terminal semantics, cluster-membership discipline, and the 06 §4
acquisition-target rule (an M&A signal requires its OWN dedicated evidence
and is never inferred from a stock opportunity score).

The external feed legs that produce opportunities are owner-gated and are
NOT exercised here; everything below is deterministic, clock-free contract
behavior over synthetic records. Nothing is wired, executed, or fetched.

Additive to ``test_ai1_opportunity_monitoring.py``: that file pins the
field-level contract surface; this file pins the lifecycle semantics those
fields compose into (closed kind/transition vocabularies, honest
non-classification, cross-level mandatory-field independence, terminal-state
persistence, membership discipline).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import get_args

import pytest
from pydantic import ValidationError

from app.domain.governed_alerts import OpportunityLifecycleTransition
from app.domain.opportunity import (
    ClassDefinition,
    OpportunityClassLabel,
    OpportunityCluster,
    OpportunityKind,
    OpportunityObject,
    active_at,
    is_expired,
)

UTC = timezone.utc
T0 = datetime(2026, 10, 18, 9, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 18, 9, 30, 0, tzinfo=UTC)

CLASS_DEF = ClassDefinition(
    label="EARLY_ACCUMULATION",
    formal_definition="Sustained quiet buying with rising value and flat price over N sessions.",
    data_prerequisites=("money_flow", "volume", "close_series"),
    time_horizon="swing",
)


def obj(**over: object) -> OpportunityObject:
    base: dict[str, object] = {
        "object_id": "opp-1",
        "opportunity_kind": "MARKET_STOCK_INVESTMENT_CANDIDATE",
        "company_role": "INVESTMENT_CANDIDATE",
        "subject": "فملی",
        "created_at_utc": T0,
        "reason_for_now": "Money-flow turned positive while price stayed flat for four sessions.",
        "confidence": Decimal("0.62"),
        "confidence_basis": "deterministic composite score with trust cap",
        "data_trust_state": "synthetic",
        "risk_semantics": "medium; liquidity contraction invalidates",
        "evidence_ids": ("ev-1", "ev-2"),
        "invalidation_conditions": ("money_flow negative for two sessions",),
        "expiry_utc": T0 + timedelta(days=5),
        "basis": "EVIDENCE_BASED",
        "run_id": "run-1",
    }
    base.update(over)
    return OpportunityObject(**base)  # type: ignore[arg-type]


def cluster(**over: object) -> OpportunityCluster:
    base: dict[str, object] = {
        "cluster_id": "cl-1",
        "class_label": "EARLY_ACCUMULATION",
        "class_definition": CLASS_DEF,
        "member_object_ids": ("opp-1", "opp-2"),
        "created_at_utc": T0,
        "run_id": "run-1",
        "why_now": "Sector-wide value expansion started this session.",
        "invalidation_conditions": ("breadth collapse",),
        "risk_adjusted_interpretation": "Favorable asymmetry only while liquidity holds.",
        "missing_information": ("institutional queue depth",),
        "confidence": Decimal("0.55"),
        "confidence_basis": "cluster-level deterministic aggregate",
    }
    base.update(over)
    return OpportunityCluster(**base)  # type: ignore[arg-type]


# --- 4-class distinction (02 lines 148–153; 06 §4) ---------------------------


def test_opportunity_kind_literal_is_closed_four_element_set() -> None:
    """The distinction is a closed four-element vocabulary: market/stock
    investment candidate, user-watchlist company intelligence, event/news
    driven candidate, and M&A acquisition-target signal — nothing else can be
    expressed, and the honest UNCLASSIFIED state is part of the class-label
    vocabulary."""
    kinds = get_args(OpportunityKind)
    assert len(kinds) == 4 and len(set(kinds)) == 4
    assert "UNCLASSIFIED" in get_args(OpportunityClassLabel)


@pytest.mark.parametrize(
    ("kind", "role"),
    [
        ("MARKET_STOCK_INVESTMENT_CANDIDATE", "INVESTMENT_CANDIDATE"),
        ("USER_WATCHLIST_COMPANY_INTELLIGENCE", "WATCHLIST_COMPANY"),
        ("CORPORATE_MA_ACQUISITION_TARGET_SIGNAL", "MA_TARGET_SIGNAL"),
        ("EVENT_NEWS_DRIVEN_CANDIDATE", "INVESTMENT_CANDIDATE"),
        ("EVENT_NEWS_DRIVEN_CANDIDATE", "WATCHLIST_COMPANY"),
    ],
)
def test_four_way_kind_distinction_representable_with_pinned_roles(kind: OpportunityKind, role: str) -> None:
    """Each of the four kinds is representable exactly through its pinned
    company role (three kinds are hard-bound; the event-driven kind is
    role-free), and a newly created object stays honestly UNCLASSIFIED."""
    over: dict[str, object] = {}
    if kind == "CORPORATE_MA_ACQUISITION_TARGET_SIGNAL":
        over = {
            "basis": "EVIDENCE_BASED",
            "ma_signal_evidence_ids": ("ma-ev-1",),
            "reason_for_now": "Two independent regulatory filings reference a stake change.",
        }
    o = obj(opportunity_kind=kind, company_role=role, **over)  # type: ignore[arg-type]
    assert o.opportunity_kind == kind
    assert o.company_role == role
    assert o.class_label == "UNCLASSIFIED" and o.class_definition is None


def test_event_driven_kind_still_requires_full_honesty_fields() -> None:
    """Being role-free does not exempt the event-driven kind from the corpus
    honesty fields: evidence, why-now, invalidation, risk and confidence
    semantics remain mandatory."""
    o = obj(opportunity_kind="EVENT_NEWS_DRIVEN_CANDIDATE", company_role="INVESTMENT_CANDIDATE")
    assert o.evidence_ids and o.reason_for_now and o.invalidation_conditions
    with pytest.raises(ValidationError):
        obj(
            opportunity_kind="EVENT_NEWS_DRIVEN_CANDIDATE",
            company_role="INVESTMENT_CANDIDATE",
            reason_for_now="",
        )
    with pytest.raises(ValidationError):
        obj(
            opportunity_kind="EVENT_NEWS_DRIVEN_CANDIDATE",
            company_role="INVESTMENT_CANDIDATE",
            invalidation_conditions=(),
        )


# --- acquisition-target class requires its OWN evidence (06 §4) ---------------


def test_acquisition_target_requires_its_own_evidence() -> None:
    """An M&A acquisition-target signal is never laundered from a stock
    opportunity score: score-only basis is refused even when dedicated
    evidence ids are present (the basis is the discriminator); evidence-based
    basis without dedicated M&A evidence is refused; dedicated evidence must
    be distinct; and a properly evidenced signal is accepted."""
    with pytest.raises(ValidationError, match="ma_signal_requires_evidence_basis"):
        obj(
            opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
            company_role="MA_TARGET_SIGNAL",
            basis="OPPORTUNITY_SCORE_ONLY",
            ma_signal_evidence_ids=("ma-ev-1",),
        )
    with pytest.raises(ValidationError, match="ma_signal_requires_dedicated_evidence"):
        obj(
            opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
            company_role="MA_TARGET_SIGNAL",
            basis="EVIDENCE_BASED",
            ma_signal_evidence_ids=(),
        )
    with pytest.raises(ValidationError, match="duplicate_items"):
        obj(
            opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
            company_role="MA_TARGET_SIGNAL",
            basis="EVIDENCE_BASED",
            ma_signal_evidence_ids=("ma-ev-1", "ma-ev-1"),
        )
    ok = obj(
        opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
        company_role="MA_TARGET_SIGNAL",
        basis="EVIDENCE_BASED",
        evidence_ids=("ev-1",),
        ma_signal_evidence_ids=("ma-ev-1", "ma-ev-2"),
        reason_for_now="Two independent regulatory filings reference a stake change.",
    )
    assert ok.basis == "EVIDENCE_BASED"
    assert ok.ma_signal_evidence_ids == ("ma-ev-1", "ma-ev-2")


# --- UNCLASSIFIED honesty (06 §6; D-AI-33) ------------------------------------


def test_unclassified_is_honest_default_and_never_force_classified() -> None:
    """A candidate whose evidence does not satisfy any published class
    definition stays UNCLASSIFIED: the honest default survives serialization,
    a concrete label can never be carried without its formal definition (no
    silent force-classification), and an UNCLASSIFIED object can never
    pretend to carry one."""
    o = obj()
    assert o.class_label == "UNCLASSIFIED" and o.class_definition is None
    round_tripped = OpportunityObject.model_validate(o.model_dump())
    assert round_tripped.class_label == "UNCLASSIFIED" and round_tripped.class_definition is None

    with pytest.raises(ValidationError, match="labelled_class_requires_class_definition"):
        obj(class_label="BREAKOUT_CANDIDATE")
    with pytest.raises(ValidationError, match="unclassified_object_cannot_carry_class_definition"):
        obj(class_definition=CLASS_DEF)


def test_unclassified_object_cannot_be_clustered() -> None:
    """Clusters organize objects BY a concrete class (06 §6): an UNCLASSIFIED
    cluster is refused even when a real class definition object is supplied —
    a definition cannot legitimize an UNCLASSIFIED grouping, and the
    insufficiently-evidenced object simply stays outside cluster output."""
    member = obj()  # honest UNCLASSIFIED member
    assert member.class_label == "UNCLASSIFIED"
    with pytest.raises(ValidationError, match="cluster_requires_concrete_class"):
        cluster(class_label="UNCLASSIFIED")


# --- why-now / invalidation mandatory at BOTH levels --------------------------


def test_why_now_and_invalidation_mandatory_at_both_object_and_cluster_level() -> None:
    """The why-now and invalidation disciplines are required independently at
    each level: members carry their own fields, and a cluster cannot borrow
    them — it must declare its own why-now, invalidation conditions,
    risk-adjusted interpretation and (always honest) missing-information
    list. Members are referenced by id only; no member content is embedded."""
    m1 = obj(object_id="opp-1")
    m2 = obj(object_id="opp-2")
    assert m1.reason_for_now and m2.invalidation_conditions  # members are honest on their own

    c = cluster()
    assert c.member_object_ids == ("opp-1", "opp-2")
    assert "member_objects" not in c.model_dump()  # ids only, never embedded objects

    with pytest.raises(ValidationError):
        cluster(why_now="")
    with pytest.raises(ValidationError):
        cluster(invalidation_conditions=())
    with pytest.raises(ValidationError):
        cluster(missing_information=())
    with pytest.raises(ValidationError):
        cluster(risk_adjusted_interpretation="")

    with pytest.raises(ValidationError):
        obj(reason_for_now="")
    with pytest.raises(ValidationError):
        obj(invalidation_conditions=())


# --- expiry / terminal semantics ----------------------------------------------


def test_expiry_and_terminal_semantics_explicit_deterministic_and_persistent() -> None:
    """Terminal semantics: expiry is an explicit owner decision (dated XOR
    explicitly open-ended, never a forgotten default), the expiry check is
    inclusive and deterministic, open-ended objects never expire, objects
    created after the cutoff are not yet active, expired records stay frozen
    (history is preserved, never deleted), naive timestamps are refused, and
    the only lifecycle transitions the alert layer can express for an
    opportunity object are CREATED and EXPIRED."""
    expiry = T0 + timedelta(days=5)
    o = obj()

    assert is_expired(o, expiry - timedelta(seconds=1)) is False
    assert is_expired(o, expiry) is True  # inclusive boundary
    assert is_expired(o, expiry + timedelta(seconds=1)) is True
    assert active_at(o, T0) is True
    assert active_at(o, expiry) is False

    open_ended = obj(expiry_utc=None, expiry_open_ended=True)
    assert is_expired(open_ended, expiry + timedelta(days=3650)) is False

    future = obj(created_at_utc=T1)
    assert active_at(future, T0) is False

    with pytest.raises(ValidationError, match="expiry_must_be_dated_or_explicitly_open_ended"):
        obj(expiry_utc=None)
    with pytest.raises(ValidationError, match="open_ended_expiry_forbids_date"):
        obj(expiry_open_ended=True)
    with pytest.raises(ValidationError):
        obj(expiry_utc=datetime(2026, 10, 23, 9, 0, 0))  # naive timestamp refused

    with pytest.raises(ValidationError):
        o.reason_for_now = "mutated"  # type: ignore[misc]  # terminal state is immutable history

    assert get_args(OpportunityLifecycleTransition) == ("CREATED", "EXPIRED")


# --- cluster membership discipline ---------------------------------------------


def test_cluster_membership_discipline() -> None:
    """Membership is a distinct, non-empty set of plain object ids, and the
    cluster's class definition must label exactly the class it claims to
    organize; the governing run identity is mandatory."""
    with pytest.raises(ValidationError):
        cluster(member_object_ids=())
    with pytest.raises(ValidationError, match="duplicate_items"):
        cluster(member_object_ids=("opp-1", "opp-1"))
    with pytest.raises(ValidationError, match="class_definition_label_mismatch"):
        cluster(class_label="BREAKOUT_CANDIDATE")
    with pytest.raises(ValidationError):
        cluster(run_id="")

    c = cluster(member_object_ids=("opp-9",))
    assert c.member_object_ids == ("opp-9",)
    assert all(isinstance(mid, str) for mid in c.member_object_ids)


# --- class-definition integrity / historical-evaluation honesty (06 §6) -------


def test_class_definition_integrity_and_historical_evaluation_never_fabricated() -> None:
    """A formal class definition carries a non-empty definition, distinct
    non-empty data prerequisites and a time horizon; the historical-evaluation
    reference defaults to None and is never fabricated to make a class look
    validated (D-AI-41) — it round-trips only when explicitly supplied."""
    d = ClassDefinition(
        label="EARLY_ACCUMULATION",
        formal_definition="Sustained quiet buying with rising value and flat price over N sessions.",
        data_prerequisites=("money_flow", "volume", "close_series"),
        time_horizon="swing",
    )
    assert d.historical_evaluation_ref is None
    d2 = ClassDefinition(
        label="EARLY_ACCUMULATION",
        formal_definition="Sustained quiet buying with rising value and flat price over N sessions.",
        data_prerequisites=("money_flow", "volume", "close_series"),
        time_horizon="swing",
        historical_evaluation_ref="eval:early_accumulation:v3",
    )
    assert d2.historical_evaluation_ref == "eval:early_accumulation:v3"

    with pytest.raises(ValidationError):
        ClassDefinition(
            label="EARLY_ACCUMULATION",
            formal_definition="",
            data_prerequisites=("money_flow",),
            time_horizon="swing",
        )
    with pytest.raises(ValidationError):
        ClassDefinition(
            label="EARLY_ACCUMULATION",
            formal_definition="Sustained quiet buying with rising value and flat price over N sessions.",
            data_prerequisites=(),
            time_horizon="swing",
        )
    with pytest.raises(ValidationError, match="data_prerequisites_duplicates"):
        ClassDefinition(
            label="EARLY_ACCUMULATION",
            formal_definition="Sustained quiet buying with rising value and flat price over N sessions.",
            data_prerequisites=("money_flow", "money_flow"),
            time_horizon="swing",
        )
    with pytest.raises(ValidationError):
        ClassDefinition(
            label="EARLY_ACCUMULATION",
            formal_definition="Sustained quiet buying with rising value and flat price over N sessions.",
            data_prerequisites=("money_flow",),
            time_horizon="",
        )
