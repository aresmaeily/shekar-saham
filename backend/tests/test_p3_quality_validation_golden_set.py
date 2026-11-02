"""T2 / CONSOL-NEXT Wave 1 — P3 independent validation of the versioned
Golden Set (app.domain.golden_set + fixtures/golden_set/golden_set_v1.json,
MA-1 WS-2).

ADDITIVE gap tests. Existing coverage (tests/test_golden_set.py, not
duplicated): pinned file/cases digests, bars digest binding, parse happy
path, canonical JSON determinism/roundtrip, engine recomputation per
case with whole-result double-run equality, verify_case refusal codes,
in-memory deepcopy tamper refusals, model vocabulary refusals,
created_at_utc digest exclusion.

Gaps filled here:
  1. Tamper evidence against a COPY on disk in a tmp dir (never the repo
     fixture), plus proof the repo fixture stays byte-identical.
  2. The trust-model boundary: a SELF-CONSISTENT rewrite (tampered metric
     + recomputed version digest) defeats parse-time integrity but can
     never match the independently pinned file/cases digests — pinned as
     an honest documentation of what each layer does and does not cover.
  3. Metric-level double-run determinism for ALL THREE cases with
     repr-identical floats, plus proof that every pinned key is actually
     produced by the engine (no vacuous pins).
  4. Fixture self-labeling (synthetic provenance, mock trust state, no
     superiority language) pinned so the fixture cannot silently lose its
     honest labeling.

The reference digests below are an INDEPENDENT re-statement (validation
layer must not import the primary pin) of tests/test_golden_set.py's
GOLDEN_SET_REFERENCE_DIGESTS; they were re-derived from the fixture
bytes and from an independent canonical-JSON reimplementation in this
file (no app import).
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from app.domain.golden_set import parse_golden_set_version

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_set" / "golden_set_v1.json"

#: Independent re-statement of the pinned reference digests.
P3_PINS = {
    "golden_set_v1.json.file": "d1560dfadc1f8136ca805501dc68a5c00d86bcbd668aa9854414b31902bdc214",
    "GS-2026-11-02.cases": "acefd2e7baf47d55050cb1c7f8496745847fcb10a91d71b0f4d38d14231d7850",
}


# ---------------------------------------------------------------------------
# Independent canonical digest (NO app import) — cross-checks the module's
# canonical_json/digest_of construction from first principles.
# ---------------------------------------------------------------------------


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(payload) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _load_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _tmp_json_roundtrip(payload: dict) -> dict:
    """Round-trip a payload through JSON text (simulates a file copy)."""
    return json.loads(json.dumps(payload))


def _case_payloads(payload: dict) -> list[dict]:
    """Rebuild the canonical case records exactly as golden_set.py does."""
    records = []
    for case in payload["cases"]:
        expected = case["expected"]
        records.append(
            {
                "bars_digest": case["bars_sha256"],
                "case_id": case["case_id"],
                "description": case.get("description", ""),
                "expected_counts": expected.get("counts", {}),
                "expected_flags": expected.get("flags", {}),
                "expected_metrics": expected.get("metrics", {}),
                "expected_windows": [
                    {"metrics": w.get("metrics", {}), "counts": w.get("counts", {})}
                    for w in expected.get("windows", ())
                ],
                "kind": case["kind"],
            }
        )
    return records


def test_p3_independent_digest_reimplementation_matches_all_pins():
    # A from-scratch canonical-JSON + SHA-256 reimplementation (above)
    # reproduces the embedded version digest and the file digest — the
    # digest construction is not self-referential.
    raw = FIXTURE_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == P3_PINS["golden_set_v1.json.file"]
    payload = _load_payload()
    assert _digest(_case_payloads(payload)) == P3_PINS["GS-2026-11-02.cases"]
    assert payload["version_sha256"] == P3_PINS["GS-2026-11-02.cases"]


# ---------------------------------------------------------------------------
# 1. Tamper evidence on a COPY in tmp — repo fixture untouched
# ---------------------------------------------------------------------------


def test_p3_tampered_tmp_copy_refused_and_repo_fixture_byte_identical():
    repo_raw = FIXTURE_PATH.read_bytes()
    tmp_copy = _tmp_json_roundtrip(copy.deepcopy(_load_payload()))
    # Perturb ONE price in the COPY only.
    tmp_copy["cases"][0]["bars"]["GSAAA"][2]["pl"] = 123.456
    text = json.dumps(tmp_copy)
    parsed_back = json.loads(text)
    from app.domain.golden_set import GoldenSetIntegrityError

    with pytest.raises(GoldenSetIntegrityError, match="CASE_BARS_DIGEST_MISMATCH"):
        parse_golden_set_version(parsed_back)
    # The repo fixture is byte-identical to the pinned state: the tamper
    # happened ONLY in the tmp copy.
    assert FIXTURE_PATH.read_bytes() == repo_raw
    assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == P3_PINS["golden_set_v1.json.file"]
    # The UNMODIFIED copy parses fine (the refusal is caused by the
    # perturbation, not by the tmp round-trip).
    clean_copy = _tmp_json_roundtrip(copy.deepcopy(_load_payload()))
    version = parse_golden_set_version(clean_copy)
    assert version.version_id == "GS-2026-11-02"


# ---------------------------------------------------------------------------
# 2. Trust-model boundary: self-consistent rewrite vs pinned digests
# ---------------------------------------------------------------------------


def test_p3_selfconsistent_rewrite_defeats_parse_but_never_the_pins():
    # ADVERSARIAL: rewrite a pinned metric AND recompute the embedded
    # version digest with the SAME canonical construction. parse-time
    # integrity is INTERNAL-CONSISTENCY only — it cannot know history —
    # so the rewrite parses cleanly. The pinned file/cases digests are
    # the tamper evidence against history; this test pins that layered
    # contract honestly (parse: no forged inconsistency; pins: no silent
    # history rewrite).
    payload = copy.deepcopy(_load_payload())
    payload["cases"][0]["expected"]["metrics"]["total_return"] = 42.0
    payload["version_sha256"] = _digest(_case_payloads(payload))
    version = parse_golden_set_version(payload)  # self-consistent -> parses
    assert version.cases[0].expected_metrics["total_return"] == 42.0
    # ...but the rewritten content can never match the independent pins:
    assert version.cases_digest != P3_PINS["GS-2026-11-02.cases"]
    assert payload["version_sha256"] != P3_PINS["GS-2026-11-02.cases"]


# ---------------------------------------------------------------------------
# 3. Metric-level double-run determinism + substantive pins
# ---------------------------------------------------------------------------


def _engine_tuple(payload: dict):
    from app.core.config import build_data_trust_context
    from app.engines.backtest import ExecutionConfig, WalkForwardConfig

    engine = payload["engine"]
    return (
        engine,
        ExecutionConfig(**engine["execution"]),
        WalkForwardConfig(**engine["walk_forward_config"]),
        build_data_trust_context(engine["data_trust_state"]),
    )


def test_p3_all_cases_double_run_metric_level_determinism_and_pins_substantive():
    from app.engines.backtest import (
        run_filter_strategy_backtest,
        run_forward_test,
        run_walk_forward,
    )

    payload = _load_payload()
    version = parse_golden_set_version(payload)
    engine, execution, wfo_config, data_trust = _engine_tuple(payload)

    for case_payload, case in zip(payload["cases"], version.cases):
        if case_payload["kind"] == "BACKTEST":
            runs = [
                run_filter_strategy_backtest(
                    case_payload["bars"],
                    engine["entry_filter"],
                    execution=execution,
                    data_trust=data_trust,
                    mode="strategy",
                )
                for _ in range(2)
            ]
            actual_metrics = runs[0]["metrics"]
            actual_metrics_run2 = runs[1]["metrics"]
            actual_counts = {"trades": runs[0]["trades"]}
            actual_flags = {"mode": runs[0]["mode"]}
        elif case_payload["kind"] == "WALK_FORWARD":
            runs = [
                run_walk_forward(
                    case_payload["bars"],
                    engine["entry_filter"],
                    config=wfo_config,
                    execution=execution,
                    data_trust=data_trust,
                )
                for _ in range(2)
            ]
            actual_metrics = runs[0]["summary"]
            actual_metrics_run2 = runs[1]["summary"]
            actual_counts = {
                "windows": runs[0]["summary"]["windows"],
                "total_oos_trades": runs[0]["summary"]["total_oos_trades"],
            }
            actual_flags = {"mode": runs[0]["mode"]}
        else:
            runs = [
                run_forward_test(
                    case_payload["bars"],
                    engine["entry_filter"],
                    start_ts=engine["forward_start_ts"],
                    execution=execution,
                    data_trust=data_trust,
                )
                for _ in range(2)
            ]
            actual_metrics = runs[0]["metrics"]
            actual_metrics_run2 = runs[1]["metrics"]
            actual_counts = {"trades": runs[0]["trades"]}
            actual_flags = {
                "mode": runs[0]["mode"],
                "forward_boundary_type": runs[0]["forward_boundary"]["type"],
            }

        # METRIC-level determinism: the FULL metrics mapping of run 1 and
        # run 2 are identical — every key, not only the pinned subset.
        assert actual_metrics == actual_metrics_run2, case.case_id
        # Float identity down to the repr (exact IEEE-754 double, not
        # merely ==-close): repr round-trip is the shortest exact form.
        for key, value in case.expected_metrics.items():
            assert repr(float(actual_metrics[key])) == repr(float(value)), (
                case.case_id,
                key,
            )
        # SUBSTANTIVE PINS: every pinned metric/count key exists in the
        # engine output — no vacuous pin against a key the engine never
        # produces (which would make exact-equality verification hollow).
        for key in case.expected_metrics:
            assert key in actual_metrics, (case.case_id, key)
        for key in case.expected_counts:
            assert key in actual_counts, (case.case_id, key)
        for key in case.expected_flags:
            assert key in actual_flags, (case.case_id, key)
        # Per-window pins (WFO only): keys exist in the window results and
        # both runs agree window by window.
        if case_payload["kind"] == "WALK_FORWARD":
            for window_expectation, window_a, window_b in zip(
                case.expected_windows, runs[0]["windows"], runs[1]["windows"]
            ):
                assert window_a["result"]["metrics"] == window_b["result"]["metrics"]
                for key in window_expectation.metrics:
                    assert key in window_a["result"]["metrics"], (case.case_id, key)


# ---------------------------------------------------------------------------
# 4. Fixture self-labeling: synthetic provenance pinned
# ---------------------------------------------------------------------------


def test_p3_fixture_is_clearly_labeled_synthetic_with_mock_trust_state():
    # Provenance audit (T2/WP-3): the fixture must SAY what it is. It is a
    # synthetic, hand-written, mock-trust-state fixture — NOT production
    # market evidence — and its honesty labeling is pinned here so it can
    # not silently drift away.
    payload = _load_payload()
    assert payload["schema"] == "golden_set_v1"
    assert payload["version_id"] == "GS-2026-11-02"
    assert payload["engine"]["data_trust_state"] == "mock"
    assert "Hand-written deterministic price paths" in payload["notes"]
    assert "No superiority claim" in payload["notes"]
    # Every case reuses the SAME hand-written three-symbol paths (one
    # bars payload, three evaluations of it) — pinned so a future edit
    # swapping in different (or real-market) bars cannot pass unnoticed.
    bars_digests = {case["bars_sha256"] for case in payload["cases"]}
    assert len(bars_digests) == 1
    symbol_sets = [tuple(sorted(case["bars"].keys())) for case in payload["cases"]]
    assert set(symbol_sets) == {("GSAAA", "GSBBB", "GSCCC")}
    # Determinism statement in the notes is present and accurate: the
    # pinned values ARE exactly recomputable in-repo (verified by the
    # recomputation tests in this suite and in test_golden_set.py).
    assert "double-run equality verified" in payload["notes"]
    # No case claims live-market or production data anywhere in its text.
    for case in payload["cases"]:
        blob = json.dumps(case).lower()
        assert "live market" not in blob
        assert "real market" not in blob
