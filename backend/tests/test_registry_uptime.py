"""Paper tests for the SourceRegistry ↔ uptime folding adapter (Agent E, module 4).

Composes source_registry.SourceDescriptor / CoverageReport verbatim and the
exact get_uptime_metrics() shape (providers.py:312-321). Injected timestamps
only; input immutability asserted; no network, no provider fetch calls, and
no 'live'/verified concept is ever introduced (source_registry's closed
status vocabulary is honored exactly).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.data.registry_uptime import coverage_report_from, fold_uptime_into_descriptors
from app.domain.source_registry import SourceDescriptor, default_precedence_for_tier

T_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
T_SUCCESS = T_NOW - timedelta(hours=1)
T_OLD = T_NOW - timedelta(days=30)


def _desc(source_id, **over) -> SourceDescriptor:
    tier = over.pop("tier", "PRIMARY_REGULATOR")
    base = dict(
        source_id=source_id,
        name=f"source {source_id}",
        tier=tier,
        precedence_class=default_precedence_for_tier(tier),
        ownership="exchange",
        permitted_access="public API within published rate limits",
        access_terms_version="terms-2026-01",
        refresh_policy="SCHEDULED",
    )
    base.update(over)
    return SourceDescriptor(**base)


def _metrics(**over) -> dict[str, object]:
    base = {
        "tsetmc_success": 5,
        "tsetmc_fail": 0,
        "tsetmc_cb_open": False,
        "brsapi_success": 0,
        "brsapi_fail": 0,
        "brsapi_cb_open": False,
        "total_fetches": 5,
        "failed_fetches": 0,
        "success_rate": 100.0,
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# Healthy / degraded / recovered / untouched paths
# ---------------------------------------------------------------------------


def test_healthy_success_marks_active_without_inventing_timestamp() -> None:
    descriptor = _desc("tsetmc")
    folded = fold_uptime_into_descriptors([descriptor], _metrics(), now_utc=T_NOW)
    assert folded[0].status == "ACTIVE"
    # get_uptime_metrics() carries no timestamps: none is fabricated.
    assert folded[0].last_success_utc is None
    assert descriptor.status == "CONFIGURED"  # input untouched


def test_explicit_last_success_instant_is_honored() -> None:
    descriptor = _desc("tsetmc")
    metrics = _metrics(tsetmc_last_success_utc=T_SUCCESS)
    folded = fold_uptime_into_descriptors([descriptor], metrics, now_utc=T_NOW)
    assert folded[0].status == "ACTIVE"
    assert folded[0].last_success_utc == T_SUCCESS
    # ISO-8601 string form of the same instant is accepted too.
    folded_str = fold_uptime_into_descriptors(
        [descriptor], _metrics(tsetmc_last_success_utc="2026-06-01T11:00:00+00:00"), now_utc=T_NOW
    )
    assert folded_str[0].last_success_utc == T_SUCCESS


def test_circuit_breaker_open_degrades_to_inaccessible() -> None:
    descriptor = _desc("tsetmc", status="ACTIVE", last_success_utc=T_OLD)
    metrics = _metrics(tsetmc_success=2, tsetmc_fail=3, tsetmc_cb_open=True)
    folded = fold_uptime_into_descriptors([descriptor], metrics, now_utc=T_NOW)
    assert folded[0].status == "INACCESSIBLE"  # closed vocabulary: the degraded state
    assert folded[0].last_success_utc == T_OLD  # carried, never edited
    assert folded[0].last_failure_utc is None  # no failure instants exist: none invented


def test_no_metrics_for_source_leaves_it_untouched() -> None:
    descriptor = _desc("codal")
    folded = fold_uptime_into_descriptors([descriptor], _metrics(), now_utc=T_NOW)
    assert folded[0] is descriptor  # success never invented from absence of evidence
    assert folded[0].status == "CONFIGURED"
    assert folded[0].last_success_utc is None


def test_failures_without_open_breaker_do_not_degrade() -> None:
    descriptor = _desc("tsetmc")
    metrics = _metrics(tsetmc_success=0, tsetmc_fail=2, tsetmc_cb_open=False)
    folded = fold_uptime_into_descriptors([descriptor], metrics, now_utc=T_NOW)
    assert folded[0].status == "CONFIGURED"  # only consecutive failures (open CB) degrade
    assert folded[0].last_success_utc is None


def test_recovered_path_back_to_active() -> None:
    descriptor = _desc("tsetmc", status="INACCESSIBLE", last_failure_utc=T_OLD)
    folded = fold_uptime_into_descriptors([descriptor], _metrics(), now_utc=T_NOW)
    assert folded[0].status == "ACTIVE"
    assert folded[0].last_failure_utc == T_OLD  # untouched history


def test_recovery_requires_an_observed_success() -> None:
    descriptor = _desc("tsetmc", status="INACCESSIBLE")
    metrics = _metrics(tsetmc_success=0, tsetmc_fail=3, tsetmc_cb_open=False)
    folded = fold_uptime_into_descriptors([descriptor], metrics, now_utc=T_NOW)
    assert folded[0].status == "INACCESSIBLE"  # breaker shut but no success yet


def test_retired_source_is_terminal_and_never_resurrected() -> None:
    descriptor = _desc("tsetmc", status="RETIRED")
    folded = fold_uptime_into_descriptors(
        [descriptor], _metrics(tsetmc_last_success_utc=T_SUCCESS), now_utc=T_NOW
    )
    assert folded[0] is descriptor
    assert folded[0].status == "RETIRED"
    assert folded[0].last_success_utc is None


# ---------------------------------------------------------------------------
# Input immutability and honest refusals
# ---------------------------------------------------------------------------


def test_fold_never_mutates_inputs_and_returns_new_records() -> None:
    descriptors = (
        _desc("tsetmc"),
        _desc("brsapi", tier="REPUTABLE_FINANCIAL_NEWS", status="INACCESSIBLE"),
    )
    metrics = _metrics(
        brsapi_success=1,
        brsapi_fail=0,
        brsapi_cb_open=False,
        tsetmc_last_success_utc=T_SUCCESS,
    )
    snapshot = [(d.status, d.last_success_utc, d.last_failure_utc) for d in descriptors]
    folded = fold_uptime_into_descriptors(descriptors, metrics, now_utc=T_NOW)
    assert folded is not descriptors and folded[0] is not descriptors[0]
    assert [d.status for d in folded] == ["ACTIVE", "ACTIVE"]
    assert folded[0].last_success_utc == T_SUCCESS
    assert [(d.status, d.last_success_utc, d.last_failure_utc) for d in descriptors] == snapshot
    # Original frozen records keep their pre-fold identity fields.
    assert descriptors[0].source_id == "tsetmc" and descriptors[1].status == "INACCESSIBLE"


@pytest.mark.parametrize(
    ("bad_value", "reason"),
    [
        ("5", "uptime_counter_must_be_int"),
        (5.0, "uptime_counter_must_be_int"),
        (True, "uptime_counter_must_be_int"),
        (-1, "uptime_counter_must_not_be_negative"),
    ],
)
def test_refusal_bad_success_counter(bad_value, reason) -> None:
    with pytest.raises(ValueError, match=reason):
        fold_uptime_into_descriptors(
            [_desc("tsetmc")], _metrics(tsetmc_success=bad_value), now_utc=T_NOW
        )


def test_refusal_bad_cb_flag_and_bad_timestamp_extension() -> None:
    with pytest.raises(ValueError, match="uptime_cb_flag_must_be_bool"):
        fold_uptime_into_descriptors(
            [_desc("tsetmc")], _metrics(tsetmc_cb_open=1), now_utc=T_NOW
        )
    with pytest.raises(ValueError, match="uptime_last_success_must_be_timestamp"):
        fold_uptime_into_descriptors(
            [_desc("tsetmc")], _metrics(tsetmc_last_success_utc="yesterday"), now_utc=T_NOW
        )
    with pytest.raises(ValueError, match="uptime_last_success_must_not_be_in_future"):
        fold_uptime_into_descriptors(
            [_desc("tsetmc")],
            _metrics(tsetmc_last_success_utc=T_NOW + timedelta(hours=1)),
            now_utc=T_NOW,
        )


def test_refusal_non_mapping_metrics_naive_now_duplicates_and_non_descriptors() -> None:
    with pytest.raises(ValueError, match="uptime_metrics_must_be_mapping"):
        fold_uptime_into_descriptors([_desc("tsetmc")], ["tsetmc_success"], now_utc=T_NOW)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timestamp_must_be_timezone_aware"):
        fold_uptime_into_descriptors([_desc("tsetmc")], _metrics(), now_utc=datetime(2026, 6, 1))
    with pytest.raises(ValueError, match="duplicate_descriptor_source_id: tsetmc"):
        fold_uptime_into_descriptors(
            [_desc("tsetmc"), _desc("tsetmc")], _metrics(), now_utc=T_NOW
        )
    with pytest.raises(ValueError, match="descriptor_must_be_source_descriptor"):
        fold_uptime_into_descriptors(
            [{"source_id": "tsetmc"}], _metrics(), now_utc=T_NOW  # type: ignore[list-item]
        )


# ---------------------------------------------------------------------------
# Honest coverage report
# ---------------------------------------------------------------------------


def test_coverage_report_from_reports_honest_lists() -> None:
    descriptors = [
        _desc("tsetmc", freshness_target=timedelta(hours=24)),
        _desc("brsapi", tier="REPUTABLE_FINANCIAL_NEWS", status="INACCESSIBLE"),
        _desc("codal", tier="AUDITED_FINANCIAL_STATEMENTS", freshness_target=timedelta(hours=24),
              last_success_utc=T_OLD),
        _desc("wiki", tier="REPUTABLE_FINANCIAL_NEWS"),
    ]
    metrics = _metrics(
        tsetmc_last_success_utc=T_SUCCESS,
        brsapi_success=1,
        brsapi_fail=2,
        brsapi_cb_open=True,
    )
    report = coverage_report_from(descriptors, metrics, now_utc=T_NOW, registry_version=7)
    assert report.as_of_utc == T_NOW
    assert report.registry_version == 7
    assert report.total_configured == 4
    assert report.active == 1  # only tsetmc (folded healthy)
    assert report.inaccessible == ("brsapi",)  # open breaker, folded
    assert report.never_retrieved == ("wiki",)  # no metrics, no success — reported honestly
    # Hand-computed staleness: codal last success 30d ago vs 24h freshness target.
    assert report.stale_sources == ("codal",)
    assert report.universal_coverage_claimed is False  # structurally locked


def test_coverage_report_never_marks_anything_live() -> None:
    descriptors = [_desc("tsetmc")]
    report = coverage_report_from(descriptors, _metrics(), now_utc=T_NOW)
    statuses = {d.status for d in fold_uptime_into_descriptors(descriptors, _metrics(), now_utc=T_NOW)}
    assert statuses <= {"CONFIGURED", "ACTIVE", "INACCESSIBLE", "RETIRED"}  # closed vocabulary
    assert all(not hasattr(d, "is_live") and not hasattr(d, "live_verified") for d in descriptors)
    assert report.universal_coverage_claimed is False
