"""P5/P6 governed-alert acceptance tests.

Derived from the 2026-10-02 amendment corpus (byte-verified), NOT from the
implementation:
- 02_EXECUTION_ROADMAP lines 147–153: the nine operational alert classes;
  every alert needs evidence, timestamp, confidence semantics, data trust,
  risk, invalidation/expiry and reason-for-now.
- 06_PRODUCT_CAPABILITY_CHARTER §4: an acquisition-target signal requires its
  own evidence and must not be inferred solely from a stock opportunity score
  — carried through to the alert layer.
- 06 §9 / 02:181–186 / D-AI-30: this contract layer dispatches nothing;
  delivery/cadence remain owner-gated (asserted here as code-shape checks).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.governed_alerts import (
    AlertKind,
    GovernedAlertObject,
    active_at,
    is_expired,
)
from app.domain.opportunity import OpportunityKind

UTC = timezone.utc
NOW = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)

VALID_KINDS: tuple[AlertKind, ...] = (
    "MARKET_ANOMALY",
    "MATERIAL_COMPANY_DISCLOSURE",
    "FILING_REPORT_PUBLICATION",
    "SOURCE_CONFLICT",
    "SOURCE_STALENESS",
    "SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE",
    "WATCHLIST_CHANGE",
    "OPPORTUNITY_LIFECYCLE",
    "RESEARCH_RESULT_MATURITY",
)


def _base(**over: object) -> dict[str, object]:
    d: dict[str, object] = {
        "alert_id": "ALERT-1",
        "alert_kind": "SOURCE_CONFLICT",
        "subject": "فملی",
        "created_at_utc": NOW,
        "reason_for_now": "two primary sources disagree on the same figure",
        "confidence": Decimal("0.5"),
        "confidence_basis": "declared by the detecting governed run",
        "data_trust_state": "synthetic",
        "risk_semantics": "informational; no position implication",
        "evidence_ids": ("E1", "E2"),
        "invalidation_conditions": ("conflict resolved with reviewer + rule",),
        "expiry_utc": NOW + timedelta(days=7),
        "run_id": "RUN-1",
        "conflict_id": "CONFLICT-1",
    }
    d.update(over)
    return d


# --- corpus criterion 1: closed nine-kind set -------------------------------

def _binding_kwargs(kind: AlertKind) -> dict[str, object]:
    """The dedicated trigger binding for one kind (None-cleared elsewhere)."""
    if kind == "MARKET_ANOMALY":
        return {"conflict_id": None, "detector_ref": "DETECTOR-OBS-1"}
    if kind == "MATERIAL_COMPANY_DISCLOSURE":
        return {"conflict_id": None, "content_kind": "COMPANY_DISCLOSURE"}
    if kind == "FILING_REPORT_PUBLICATION":
        return {"conflict_id": None, "content_kind": "FILING"}
    if kind == "SOURCE_CONFLICT":
        return {"conflict_id": "CONFLICT-1"}
    if kind == "SOURCE_STALENESS":
        return {"conflict_id": None, "stale_source_ids": ("SRC-1",)}
    if kind == "SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE":
        return {"conflict_id": None, "fact_id": "F-2", "superseded_fact_id": "F-1"}
    if kind == "WATCHLIST_CHANGE":
        return {"conflict_id": None, "watchlist_ref": "WL-1", "change_kind": "ADDED"}
    if kind == "OPPORTUNITY_LIFECYCLE":
        return {"conflict_id": None, "opportunity_object_id": "OPP-1", "lifecycle_transition": "CREATED"}
    return {"conflict_id": None, "prediction_id": "P-1", "outcome_id": "O-1"}  # RESEARCH_RESULT_MATURITY


@pytest.mark.parametrize("kind", VALID_KINDS)
def test_each_of_the_nine_corpus_kinds_representable(kind: AlertKind) -> None:
    """Each of the nine corpus classes must be expressible (02:148–149)."""
    obj = GovernedAlertObject(**_base(alert_kind=kind, **_binding_kwargs(kind)))
    assert obj.alert_kind == kind
    assert obj.model_config.get("frozen") is True


def test_unknown_alert_kind_unrepresentable() -> None:
    """The set is closed: an unlisted kind cannot be expressed."""
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(alert_kind="EVERYTHING_ALARM"))  # type: ignore[arg-type]


# --- corpus criterion 2: honesty fields, freeze, UTC ------------------------

def test_minimal_valid_alert_is_frozen() -> None:
    obj = GovernedAlertObject(**_base())
    with pytest.raises(ValidationError):
        obj.subject = "other"  # type: ignore[misc]


def test_naive_created_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(created_at_utc=datetime(2026, 10, 30, 12, 0, 0)))


def test_naive_expiry_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(expiry_utc=datetime(2026, 11, 6, 12, 0, 0)))


def test_confidence_bounds_enforced() -> None:
    for bad in (Decimal("-0.01"), Decimal("1.01")):
        with pytest.raises(ValidationError):
            GovernedAlertObject(**_base(confidence=bad))


def test_evidence_required_and_never_self_referential() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(evidence_ids=()))
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(evidence_ids=("ALERT-1",)))
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(evidence_ids=("E1", "E1")))


def test_invalidation_conditions_required() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(invalidation_conditions=()))


def test_expiry_must_be_explicit_not_forgotten() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(expiry_utc=None, expiry_open_ended=False))
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(expiry_utc=NOW + timedelta(days=1), expiry_open_ended=True))
    obj = GovernedAlertObject(**_base(expiry_utc=None, expiry_open_ended=True))
    assert obj.expiry_open_ended is True


# --- corpus criterion 3: per-kind dedicated bindings -------------------------

def test_market_anomaly_requires_detector_ref() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(alert_kind="MARKET_ANOMALY", conflict_id=None))
    obj = GovernedAlertObject(**_base(alert_kind="MARKET_ANOMALY", conflict_id=None, detector_ref="DETECTOR-OBS-1"))
    assert obj.detector_ref == "DETECTOR-OBS-1"


def test_disclosure_alert_content_kind_domain() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(alert_kind="MATERIAL_COMPANY_DISCLOSURE", conflict_id=None))
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(alert_kind="MATERIAL_COMPANY_DISCLOSURE", conflict_id=None, content_kind="FILING")
        )
    obj = GovernedAlertObject(
        **_base(alert_kind="MATERIAL_COMPANY_DISCLOSURE", conflict_id=None, content_kind="MATERIAL_EVENT")
    )
    assert obj.content_kind == "MATERIAL_EVENT"


def test_filing_alert_content_kind_domain() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(alert_kind="FILING_REPORT_PUBLICATION", conflict_id=None, content_kind="COMPANY_DISCLOSURE"))
    obj = GovernedAlertObject(
        **_base(alert_kind="FILING_REPORT_PUBLICATION", conflict_id=None, content_kind="FINANCIAL_STATEMENT")
    )
    assert obj.content_kind == "FINANCIAL_STATEMENT"


def test_source_conflict_requires_conflict_id() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(alert_kind="SOURCE_CONFLICT", conflict_id=None))
    obj = GovernedAlertObject(**_base(alert_kind="SOURCE_CONFLICT", conflict_id="CONFLICT-9"))
    assert obj.conflict_id == "CONFLICT-9"


def test_staleness_requires_stale_source_ids() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(alert_kind="SOURCE_STALENESS", conflict_id=None, stale_source_ids=()))
    obj = GovernedAlertObject(
        **_base(alert_kind="SOURCE_STALENESS", conflict_id=None, stale_source_ids=("SRC-A", "SRC-B"))
    )
    assert obj.stale_source_ids == ("SRC-A", "SRC-B")
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(alert_kind="SOURCE_STALENESS", conflict_id=None, stale_source_ids=("SRC-A", "SRC-A"))
        )


def test_statement_change_requires_restatement_chain() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(alert_kind="SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE", conflict_id=None, fact_id="F-2")
        )
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(
                alert_kind="SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE",
                conflict_id=None,
                fact_id="F-2",
                superseded_fact_id="F-2",
            )
        )
    obj = GovernedAlertObject(
        **_base(
            alert_kind="SIGNIFICANT_FINANCIAL_STATEMENT_CHANGE",
            conflict_id=None,
            fact_id="F-2",
            superseded_fact_id="F-1",
        )
    )
    assert obj.superseded_fact_id == "F-1"


def test_watchlist_change_requires_ref_and_kind() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(alert_kind="WATCHLIST_CHANGE", conflict_id=None, watchlist_ref="WL-1"))
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(alert_kind="WATCHLIST_CHANGE", conflict_id=None, change_kind="REMOVED")
        )
    obj = GovernedAlertObject(
        **_base(alert_kind="WATCHLIST_CHANGE", conflict_id=None, watchlist_ref="WL-1", change_kind="REMOVED")
    )
    assert obj.change_kind == "REMOVED"


def test_opportunity_lifecycle_requires_object_and_transition() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(alert_kind="OPPORTUNITY_LIFECYCLE", conflict_id=None, lifecycle_transition="EXPIRED")
        )
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(alert_kind="OPPORTUNITY_LIFECYCLE", conflict_id=None, opportunity_object_id="OPP-1")
        )
    obj = GovernedAlertObject(
        **_base(
            alert_kind="OPPORTUNITY_LIFECYCLE",
            conflict_id=None,
            opportunity_object_id="OPP-1",
            lifecycle_transition="EXPIRED",
        )
    )
    assert obj.lifecycle_transition == "EXPIRED"


def test_research_maturity_requires_prediction_and_outcome() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(alert_kind="RESEARCH_RESULT_MATURITY", conflict_id=None, prediction_id="P-1")
        )
    obj = GovernedAlertObject(
        **_base(
            alert_kind="RESEARCH_RESULT_MATURITY",
            conflict_id=None,
            prediction_id="P-1",
            outcome_id="O-1",
        )
    )
    assert obj.outcome_id == "O-1"


# --- corpus criterion 3b: cross-kind contamination refused -------------------

@pytest.mark.parametrize(
    ("kind", "contamination"),
    [
        ("SOURCE_CONFLICT", {"detector_ref": "X"}),
        ("SOURCE_CONFLICT", {"content_kind": "FILING"}),
        ("SOURCE_CONFLICT", {"stale_source_ids": ("S",)}),
        ("SOURCE_CONFLICT", {"fact_id": "F", "superseded_fact_id": "G"}),
        ("SOURCE_CONFLICT", {"watchlist_ref": "W", "change_kind": "ADDED"}),
        ("SOURCE_CONFLICT", {"opportunity_object_id": "O", "lifecycle_transition": "CREATED"}),
        ("SOURCE_CONFLICT", {"prediction_id": "P", "outcome_id": "Q"}),
    ],
)
def test_dedicated_binding_fields_cannot_leak_across_kinds(kind: str, contamination: dict) -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(alert_kind=kind, **contamination))


def test_ma_evidence_only_valid_inside_opportunity_lifecycle_kind() -> None:
    with pytest.raises(ValidationError):
        GovernedAlertObject(**_base(ma_signal_evidence_ids=("MA-1",)))


# --- corpus criterion 4: M&A non-conflation carried through ------------------

def test_ma_lifecycle_alert_requires_dedicated_ma_evidence() -> None:
    """06 §4: M&A signal is never a stock-buy signal; dedicated evidence must
    survive into the alert layer."""
    with pytest.raises(ValidationError):
        GovernedAlertObject(
            **_base(
                alert_kind="OPPORTUNITY_LIFECYCLE",
                conflict_id=None,
                opportunity_object_id="OPP-MA-1",
                lifecycle_transition="CREATED",
                referenced_opportunity_kind="CORPORATE_MA_ACQUISITION_TARGET_SIGNAL",
            )
        )


@pytest.mark.parametrize("ma_kind", ["CORPORATE_MA_ACQUISITION_TARGET_SIGNAL", "MARKET_STOCK_INVESTMENT_CANDIDATE"])
def test_ma_lifecycle_alert_with_dedicated_evidence_accepted(ma_kind: OpportunityKind) -> None:
    obj = GovernedAlertObject(
        **_base(
            alert_kind="OPPORTUNITY_LIFECYCLE",
            conflict_id=None,
            opportunity_object_id="OPP-MA-1",
            lifecycle_transition="CREATED",
            referenced_opportunity_kind=ma_kind,
            ma_signal_evidence_ids=("MA-EV-1",),
        )
    )
    assert obj.referenced_opportunity_kind == ma_kind


def test_non_ma_opportunity_alert_needs_no_ma_evidence() -> None:
    obj = GovernedAlertObject(
        **_base(
            alert_kind="OPPORTUNITY_LIFECYCLE",
            conflict_id=None,
            opportunity_object_id="OPP-1",
            lifecycle_transition="EXPIRED",
            referenced_opportunity_kind="MARKET_STOCK_INVESTMENT_CANDIDATE",
        )
    )
    assert obj.ma_signal_evidence_ids == ()


# --- corpus criterion 5: deterministic lifecycle helpers ----------------------

def test_expiry_helpers_deterministic() -> None:
    expiring = GovernedAlertObject(**_base(expiry_utc=NOW - timedelta(minutes=1)))
    open_ended = GovernedAlertObject(**_base(expiry_utc=None, expiry_open_ended=True))
    future = GovernedAlertObject(**_base(expiry_utc=NOW + timedelta(days=1)))
    past_created = GovernedAlertObject(**_base(created_at_utc=NOW + timedelta(days=1)))

    assert is_expired(expiring, NOW) is True
    assert is_expired(open_ended, NOW) is False
    assert is_expired(future, NOW) is False
    assert active_at(future, NOW) is True
    assert active_at(future, NOW + timedelta(days=2)) is False
    assert active_at(past_created, NOW) is False
    assert active_at(expiring, NOW) is False


# --- delivery/cadence stay out of the contract layer (D-AI-30 / 06 §9) -------

def test_contract_layer_dispatches_nothing() -> None:
    """The module exposes only contracts and pure helpers — no send/publish/
    schedule surface exists at the domain layer."""
    import app.domain.governed_alerts as mod

    assert sorted(mod.__all__) == [
        "AlertKind",
        "GovernedAlertObject",
        "OpportunityLifecycleTransition",
        "WatchlistChangeKind",
        "active_at",
        "is_expired",
    ]
    for forbidden in ("send", "publish", "schedule", "deliver", "notify", "dispatch"):
        assert forbidden not in mod.__all__
