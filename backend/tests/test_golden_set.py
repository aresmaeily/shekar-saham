"""Tests for the versioned Golden Set (app.domain.golden_set + fixture).

Tamper evidence mirrors the scripts/g2_acceptance_battery.py
CORPUS_REFERENCE_DIGESTS precedent: the fixture file digest and the
version cases digest are PINNED HERE and re-verified on every run.

Float policy: expected metrics are the exact IEEE-754 doubles produced by
the deterministic engine; comparison is EXACT ``==`` (never approximate).
The engine's determinism is re-verified by a double-run in this suite —
if any nondeterminism ever appears, the suite fails loudly here instead
of silently loosening the policy.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import build_data_trust_context
from app.engines.backtest import (
    ExecutionConfig,
    WalkForwardConfig,
    run_filter_strategy_backtest,
    run_forward_test,
    run_walk_forward,
)
from app.domain.golden_set import (
    GoldenSetCase,
    GoldenSetIntegrityError,
    GoldenSetVersion,
    GoldenWindowExpectation,
    canonical_json,
    digest_of,
    parse_golden_set_version,
    verify_case,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_set" / "golden_set_v1.json"

#: Pinned reference digests (tamper evidence; CORPUS_REFERENCE_DIGESTS
#: precedent). file = raw fixture bytes; cases = canonical case records.
GOLDEN_SET_REFERENCE_DIGESTS = {
    "golden_set_v1.json.file": "d1560dfadc1f8136ca805501dc68a5c00d86bcbd668aa9854414b31902bdc214",
    "GS-2026-11-02.cases": "acefd2e7baf47d55050cb1c7f8496745847fcb10a91d71b0f4d38d14231d7850",
}


def _load_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _engine(payload: dict):
    engine = payload["engine"]
    execution = ExecutionConfig(**engine["execution"])
    wfo_config = WalkForwardConfig(**engine["walk_forward_config"])
    data_trust = build_data_trust_context(engine["data_trust_state"])
    return engine, execution, wfo_config, data_trust


# ---------------------------------------------------------------------------
# Tamper evidence (digests)
# ---------------------------------------------------------------------------


def test_fixture_file_digest_matches_pinned_reference():
    raw = FIXTURE_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == GOLDEN_SET_REFERENCE_DIGESTS["golden_set_v1.json.file"]


def test_version_cases_digest_matches_pinned_and_embedded():
    payload = _load_payload()
    version = parse_golden_set_version(payload)
    assert version.cases_digest == payload["version_sha256"]
    assert version.cases_digest == GOLDEN_SET_REFERENCE_DIGESTS["GS-2026-11-02.cases"]


def test_bars_digest_binds_exact_input_bars():
    payload = _load_payload()
    version = parse_golden_set_version(payload)
    for case_payload, case in zip(payload["cases"], version.cases):
        assert digest_of(case_payload["bars"]) == case_payload["bars_sha256"]
        assert case.bars_digest == case_payload["bars_sha256"]


def test_parse_builds_version_with_three_cases_and_explicit_timestamp():
    payload = _load_payload()
    version = parse_golden_set_version(payload)
    assert version.version_id == "GS-2026-11-02"
    assert [c.kind for c in version.cases] == ["BACKTEST", "WALK_FORWARD", "FORWARD_TEST"]
    # created_at_utc is an EXPLICIT fixture field (no wall-clock anywhere).
    assert version.created_at_utc.isoformat() == "2026-11-02T00:00:00+00:00"


# ---------------------------------------------------------------------------
# canonical_json determinism
# ---------------------------------------------------------------------------


def test_canonical_json_is_sorted_compact_and_key_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert (
        digest_of({"a": 1, "b": [2, 3]})
        == digest_of({"b": [2, 3], "a": 1})
    )


def test_canonical_json_float_roundtrip_is_exact():
    value = 0.1 + 0.2  # 0.30000000000000004 — repr round-trips exactly
    assert json.loads(canonical_json({"x": value}))["x"] == value
    assert canonical_json({"x": value}) == '{"x":0.30000000000000004}'


# ---------------------------------------------------------------------------
# Golden recomputation (exact equality, double-run determinism)
# ---------------------------------------------------------------------------


def _subset(metrics: dict, keys: dict) -> dict:
    return {k: metrics[k] for k in keys}


def test_backtest_golden_case_exact_recompute_and_double_run_determinism():
    payload = _load_payload()
    engine, execution, _, data_trust = _engine(payload)
    case_payload = next(c for c in payload["cases"] if c["kind"] == "BACKTEST")
    version = parse_golden_set_version(payload)
    case = next(c for c in version.cases if c.case_id == case_payload["case_id"])

    bars = case_payload["bars"]
    first = run_filter_strategy_backtest(
        bars, engine["entry_filter"], execution=execution, data_trust=data_trust, mode="strategy"
    )
    second = run_filter_strategy_backtest(
        bars, engine["entry_filter"], execution=execution, data_trust=data_trust, mode="strategy"
    )
    assert first == second  # determinism guard for the exact-equality policy

    result = verify_case(
        case,
        actual_metrics=_subset(first["metrics"], case.expected_metrics),
        actual_counts={"trades": first["trades"]},
        actual_flags={"mode": first["mode"]},
    )
    assert result.passed, result.failure_reasons
    assert case.expected_counts["trades"] > 0  # a golden case with no trade would be vacuous


def test_walk_forward_golden_case_exact_recompute_per_window():
    payload = _load_payload()
    engine, execution, wfo_config, data_trust = _engine(payload)
    case_payload = next(c for c in payload["cases"] if c["kind"] == "WALK_FORWARD")
    version = parse_golden_set_version(payload)
    case = next(c for c in version.cases if c.case_id == case_payload["case_id"])

    result = run_walk_forward(
        case_payload["bars"],
        engine["entry_filter"],
        config=wfo_config,
        execution=execution,
        data_trust=data_trust,
    )
    assert result == run_walk_forward(  # determinism guard
        case_payload["bars"],
        engine["entry_filter"],
        config=wfo_config,
        execution=execution,
        data_trust=data_trust,
    )

    summary = verify_case(
        case,
        actual_metrics=_subset(
            {"avg_window_total_return": result["summary"]["avg_window_total_return"]},
            case.expected_metrics,
        ),
        actual_counts={
            "windows": result["summary"]["windows"],
            "total_oos_trades": result["summary"]["total_oos_trades"],
        },
        actual_flags={"mode": result["mode"]},
    )
    assert summary.passed, summary.failure_reasons

    # Per-window expectations: exact equality, window by window, in order.
    assert len(case.expected_windows) == len(result["windows"])
    for window_expectation, actual_window in zip(case.expected_windows, result["windows"]):
        assert _subset(actual_window["result"]["metrics"], window_expectation.metrics) == dict(
            window_expectation.metrics
        )
        assert actual_window["result"]["trades"] == window_expectation.counts["trades"]
        assert actual_window["train"]["end_index"] < actual_window["test"]["start_index"]


def test_forward_test_golden_case_exact_recompute():
    payload = _load_payload()
    engine, execution, _, data_trust = _engine(payload)
    case_payload = next(c for c in payload["cases"] if c["kind"] == "FORWARD_TEST")
    version = parse_golden_set_version(payload)
    case = next(c for c in version.cases if c.case_id == case_payload["case_id"])

    result = run_forward_test(
        case_payload["bars"],
        engine["entry_filter"],
        start_ts=engine["forward_start_ts"],
        execution=execution,
        data_trust=data_trust,
    )
    assert result == run_forward_test(  # determinism guard
        case_payload["bars"],
        engine["entry_filter"],
        start_ts=engine["forward_start_ts"],
        execution=execution,
        data_trust=data_trust,
    )
    out = verify_case(
        case,
        actual_metrics=_subset(result["metrics"], case.expected_metrics),
        actual_counts={"trades": result["trades"]},
        actual_flags={
            "mode": result["mode"],
            "forward_boundary_type": result["forward_boundary"]["type"],
        },
    )
    assert out.passed, out.failure_reasons
    assert result["forward_boundary"]["start_ts"] == 28.0
    assert result["mode"] == "forward_test"


# ---------------------------------------------------------------------------
# verify_case refusal detection (exact, no tolerance)
# ---------------------------------------------------------------------------


def _mini_case(expected_metrics: dict) -> GoldenSetCase:
    return GoldenSetCase(
        case_id="GS-TEST-CASE",
        kind="BACKTEST",
        bars_digest="a" * 64,
        expected_metrics=expected_metrics,
    )


def test_verify_case_detects_mismatch_missing_and_extra():
    case = _mini_case({"a": 1.0, "b": 2.0})
    result = verify_case(case, actual_metrics={"a": 1.0, "c": 3.0})
    assert result.passed is False
    assert set(result.failure_reasons) == {"MISSING_METRIC:b", "EXTRA_METRIC:c"}

    drifted = verify_case(case, actual_metrics={"a": 1.0, "b": 2.0000001})
    assert "METRIC_MISMATCH:b" in drifted.failure_reasons  # exact ==, no tolerance

    ok = verify_case(case, actual_metrics={"a": 1.0, "b": 2.0, "extra_unpinned": 9.0})
    assert ok.passed is False  # extra unpinned keys are reported, not ignored
    assert "EXTRA_METRIC:extra_unpinned" in ok.failure_reasons


def test_verify_case_counts_and_flags_are_enforced():
    case = GoldenSetCase(
        case_id="GS-TEST-CASE",
        kind="BACKTEST",
        bars_digest="b" * 64,
        expected_metrics={},
        expected_counts={"trades": 5},
        expected_flags={"mode": "strategy"},
    )
    assert verify_case(case, actual_counts={"trades": 5}, actual_flags={"mode": "strategy"}).passed
    wrong_count = verify_case(case, actual_counts={"trades": 4}, actual_flags={"mode": "strategy"})
    assert wrong_count.failure_reasons == ("COUNT_MISMATCH:trades",)
    wrong_flag = verify_case(case, actual_counts={"trades": 5}, actual_flags={"mode": "forward_test"})
    assert wrong_flag.failure_reasons == ("FLAG_MISMATCH:mode",)


# ---------------------------------------------------------------------------
# Parse-time integrity refusals (fail-closed)
# ---------------------------------------------------------------------------


def test_parse_refuses_tampered_bars():
    payload = copy.deepcopy(_load_payload())
    payload["cases"][0]["bars"]["GSAAA"][0]["pl"] = 999  # flip one price
    with pytest.raises(GoldenSetIntegrityError, match="CASE_BARS_DIGEST_MISMATCH"):
        parse_golden_set_version(payload)


def test_parse_refuses_tampered_expected_metrics():
    payload = copy.deepcopy(_load_payload())
    # Tampering with pinned content changes the cases digest; the embedded
    # version digest no longer matches -> refused (content cannot be
    # silently rewritten even with bars untouched).
    payload["cases"][0]["expected"]["metrics"]["total_return"] = 99.0
    with pytest.raises(GoldenSetIntegrityError, match="VERSION_DIGEST_MISMATCH"):
        parse_golden_set_version(payload)


def test_parse_refuses_missing_payload_keys_and_non_mapping():
    payload = _load_payload()
    broken = {k: v for k, v in payload.items() if k != "version_sha256"}
    with pytest.raises(GoldenSetIntegrityError, match="PAYLOAD_KEY_MISSING"):
        parse_golden_set_version(broken)
    with pytest.raises(GoldenSetIntegrityError, match="PAYLOAD_NOT_MAPPING"):
        parse_golden_set_version(["not", "a", "mapping"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Model-level vocabulary refusals
# ---------------------------------------------------------------------------


def _case(case_id: str) -> GoldenSetCase:
    return GoldenSetCase(case_id=case_id, kind="BACKTEST", bars_digest="c" * 64)


def test_version_refuses_duplicate_case_ids_and_bad_version_id():
    with pytest.raises(ValidationError, match="duplicate_case_ids"):
        GoldenSetVersion(
            version_id="GS-2026-11-02",
            created_at_utc="2026-11-02T00:00:00+00:00",
            cases=(_case("SAME"), _case("SAME")),
        )
    with pytest.raises(ValidationError):
        GoldenSetVersion(
            version_id="GS-2026-1-2",  # violates GS-YYYY-MM-DD
            created_at_utc="2026-11-02T00:00:00+00:00",
            cases=(_case("ONLY"),),
        )


def test_cases_digest_excludes_created_at_utc():
    cases = (_case("ONLY"),)
    early = GoldenSetVersion(
        version_id="GS-2026-01-01",
        created_at_utc="2026-01-01T00:00:00+00:00",
        cases=cases,
    )
    late = GoldenSetVersion(
        version_id="GS-2026-12-31",
        created_at_utc="2026-12-31T23:59:59+00:00",
        cases=cases,
    )
    # The same case content yields the same digest regardless of when the
    # version record was minted (timestamps are excluded by policy).
    assert early.cases_digest == late.cases_digest
    assert early.cases_digest != GOLDEN_SET_REFERENCE_DIGESTS["GS-2026-11-02.cases"]
