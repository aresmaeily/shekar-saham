"""W3-3AB — API acceptance battery for POST /api/v10/chartpro/{symbol}/derived.

Covers, per the directive rows:
- each of the 5 construction types -> 200 with the exact top-level shape
  (``bars`` for RENKO/RANGE/LINEBREAK/PNF, ``points`` for KAGI, counts,
  labeling.method == "DERIVED_<TYPE>", the four construction/note fields,
  trust envelope, source/note honesty labels);
- deterministic repeat: two identical bodies -> identical units JSON
  (timeframe "1D" so both requests resolve the same wall-clock day bucket —
  the generator's only clock input is the default end-bar bucket);
- every documented 422 refusal (missing/wrong-typed/out-of-range params,
  bad timeframe, unknown type, missing type);
- hostile bodies -> never 500;
- unknown symbol still resolves (synthetic contract);
- unit key sets exactly as documented;
- cross-endpoint ``bar_class`` equality with the canonical labeling echo.

Synthetic/Paper ONLY: everything here rides the deterministic seeded
generator pinned by tests/conftest.py (DATA_SOURCE=mock, no network).
"""
from __future__ import annotations

from typing import Any, Dict, get_args

from fastapi.testclient import TestClient

from app.api.chart_pro import DerivedBody
from app.engines.derived_charts import DERIVED_TYPES, range_bars
from app.main import app

# Same honest non-live taxonomy as tests/test_chart_pro_api.py (locally
# restated — test modules do not import each other; the names below avoid the
# banned trust-label substrings by construction: these sets enumerate the
# ALLOWED verdicts, and "live" is deliberately absent from both).
ALLOWED_TRUST_STATES = {"synthetic", "mock", "stale", "unavailable", "mixed"}
ALLOWED_TRUST_LEVELS = {"synthetic", "mixed"}

client = TestClient(app, client=("mr-wave3-derived", 12348))
# AUDIT-MR3 Obs.3 hygiene (symmetry with test_walk_forward.py): the middleware
# reads get_settings() per request; env-patching modules elsewhere can leave
# the lru_cache holding PRIVATE_MODE/AUTH_REQUIRED residue after teardown.
# Clearing at module scope makes this module immune to upstream poisoning
# without touching any other test.
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

DERIVED_URL = "/api/v10/chartpro/فملی/derived"

BAR_KEYS = {"time", "open", "high", "low", "close", "direction"}
POINT_KEYS = {"time", "value"}
LABELING_KEYS = {"bar_class", "method", "construction_en", "construction_fa", "note_en", "note_fa"}


def _shape_asserts(body: Dict[str, Any], derived_type: str, limit: int = 300) -> None:
    """Exact top-level shape shared by every 200 response."""
    unit_key = "points" if derived_type == "KAGI" else "bars"
    expected_keys = {
        "symbol", "timeframe", "type", "params", "source_count", "derived_count",
        unit_key, "labeling", "data_trust", "trust_level", "source", "note",
    }
    assert set(body) == expected_keys, set(body) ^ expected_keys
    assert body["symbol"] == "فملی"
    assert body["type"] == derived_type
    assert body["timeframe"] == "1m"
    assert body["source_count"] == limit
    assert body["derived_count"] == len(body[unit_key])
    assert body["source"] == "synthetic-seeded"
    assert body["note"] == "SYNTHETIC_OR_PAPER deterministic derived construction"
    labeling = body["labeling"]
    assert set(labeling) == LABELING_KEYS
    assert labeling["method"] == "DERIVED_" + derived_type
    assert labeling["construction_en"] and labeling["construction_fa"]
    assert "not real market bars" in labeling["note_en"]
    assert "not an independent data source" in labeling["note_en"]
    assert labeling["note_fa"]
    # trust envelope is present and carries the canonical non-live verdict
    assert body["data_trust"]["state"] in ALLOWED_TRUST_STATES
    assert body["data_trust"]["is_live"] is False
    assert body["data_trust"]["live_verified"] is False
    assert body["trust_level"] in ALLOWED_TRUST_LEVELS


def test_renko_endpoint_shape():
    r = client.post(DERIVED_URL, json={"type": "RENKO", "limit": 100})
    assert r.status_code == 200
    body = r.json()
    _shape_asserts(body, "RENKO", limit=100)
    # neither brick param given -> the documented default {"atr_period": 14}
    assert body["params"] == {"atr_period": 14}
    assert set(body["bars"][0]) == BAR_KEYS


def test_range_endpoint_shape():
    r = client.post(DERIVED_URL, json={"type": "RANGE", "params": {"range_size": 100}})
    assert r.status_code == 200
    body = r.json()
    _shape_asserts(body, "RANGE")
    assert body["params"] == {"range_size": 100.0}
    assert set(body["bars"][0]) == BAR_KEYS
    assert body["derived_count"] >= 1


def test_kagi_endpoint_shape():
    r = client.post(DERIVED_URL, json={"type": "KAGI"})
    assert r.status_code == 200
    body = r.json()
    _shape_asserts(body, "KAGI")
    assert body["params"] == {"reversal_pct": 3.0}  # documented default
    assert set(body["points"][0]) == POINT_KEYS
    assert body["derived_count"] >= 1


def test_pnf_endpoint_shape():
    r = client.post(DERIVED_URL, json={"type": "PNF"})
    assert r.status_code == 200
    body = r.json()
    _shape_asserts(body, "PNF")
    assert body["params"] == {"box_size": 1.0, "reversal_boxes": 3}  # defaults
    assert set(body["bars"][0]) == BAR_KEYS
    assert body["derived_count"] >= 1


def test_linebreak_endpoint_shape():
    r = client.post(DERIVED_URL, json={"type": "LINEBREAK", "params": {"lines": 4}})
    assert r.status_code == 200
    body = r.json()
    _shape_asserts(body, "LINEBREAK")
    assert body["params"] == {"lines": 4}
    assert set(body["bars"][0]) == BAR_KEYS
    assert body["derived_count"] >= 1


def test_endpoint_deterministic_repeat():
    body_spec = {"type": "RENKO", "timeframe": "1D", "limit": 80}
    first = client.post(DERIVED_URL, json=body_spec).json()
    second = client.post(DERIVED_URL, json=body_spec).json()
    # identical args -> identical units JSON (same "1D" wall-clock bucket)
    assert first["bars"] == second["bars"]
    assert first["params"] == second["params"]
    assert first["derived_count"] == second["derived_count"]


def test_range_missing_range_size_422():
    r = client.post(DERIVED_URL, json={"type": "RANGE", "params": {}})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "range_size" in detail["en"]
    assert detail["fa"]


def test_renko_both_params_422():
    r = client.post(
        DERIVED_URL,
        json={"type": "RENKO", "params": {"brick_size": 10, "atr_period": 14}},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "exactly one" in detail["en"]
    assert detail["fa"]


def test_renko_atr_period_out_of_range_422():
    for bad in (1, 201, "14", 2.5, True):
        r = client.post(DERIVED_URL, json={"type": "RENKO", "params": {"atr_period": bad}})
        assert r.status_code == 422, bad
        assert r.json()["detail"]["fa"]


def test_linebreak_lines_out_of_range_422():
    for bad in (1, 11, "3", 3.5):
        r = client.post(DERIVED_URL, json={"type": "LINEBREAK", "params": {"lines": bad}})
        assert r.status_code == 422, bad


def test_pnf_reversal_boxes_zero_422():
    r = client.post(DERIVED_URL, json={"type": "PNF", "params": {"reversal_boxes": 0}})
    assert r.status_code == 422
    r2 = client.post(DERIVED_URL, json={"type": "PNF", "params": {"reversal_boxes": 21}})
    assert r2.status_code == 422
    r3 = client.post(DERIVED_URL, json={"type": "PNF", "params": {"box_size": 0}})
    assert r3.status_code == 422


def test_kagi_reversal_pct_invalid_422():
    for bad in (0, -3, "3", True):
        r = client.post(DERIVED_URL, json={"type": "KAGI", "params": {"reversal_pct": bad}})
        assert r.status_code == 422, bad


def test_bad_timeframe_422():
    r = client.post(DERIVED_URL, json={"type": "KAGI", "timeframe": "2h"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "timeframe" in detail["en"]
    assert detail["fa"]


def test_unknown_type_422():
    r = client.post(DERIVED_URL, json={"type": "ICHIMOKU"})
    assert r.status_code == 422  # body Literal + registry discipline


def test_missing_type_422():
    r = client.post(DERIVED_URL, json={"timeframe": "1m"})
    assert r.status_code == 422


def test_hostile_bodies_never_500():
    hostile = [
        {"type": "RENKO", "params": [1, 2, 3]},                     # params as list
        {"type": "RANGE", "params": {"range_size": "big"}},          # wrong-typed value
        {"type": "RANGE", "params": {"range_size": [5]}},            # list value
        {"type": "RENKO", "params": {"brick_size": {"x": 1}}},       # object value
        {"type": "KAGI", "limit": "abc"},                            # non-numeric limit
        {"type": "KAGI", "limit": None},                             # null limit
        {"type": "PNF", "timeframe": 7},                             # non-string timeframe
        {"type": "LINEBREAK", "params": None},                       # null params
        ["not", "an", "object"],                                     # body as list
        "just a string",                                             # body as string
    ]
    for payload in hostile:
        r = client.post(DERIVED_URL, json=payload)
        assert r.status_code < 500, (payload, r.status_code)


def test_limit_clamped_and_extra_fields_ignored():
    # huge limit -> clamped to the generator 1000 ceiling; negative -> 50 floor
    r = client.post(DERIVED_URL, json={"type": "RANGE", "limit": 10**9, "params": {"range_size": 50}})
    assert r.status_code == 200
    assert r.json()["source_count"] == 1000
    r2 = client.post(DERIVED_URL, json={"type": "RANGE", "limit": -5, "params": {"range_size": 50}})
    assert r2.status_code == 200
    assert r2.json()["source_count"] == 50
    # extra unknown body fields AND unknown param keys are ignored (documented)
    r3 = client.post(
        DERIVED_URL,
        json={
            "type": "KAGI",
            "limit": 60,
            "mystery_field": {"nested": True},
            "params": {"reversal_pct": 5.0, "unknown_key": "ignored"},
        },
    )
    assert r3.status_code == 200
    assert r3.json()["params"] == {"reversal_pct": 5.0}
    assert r3.json()["derived_count"] >= 1


def test_unknown_symbol_still_200():
    r = client.post("/api/v10/chartpro/ZZZ_UNKNOWN_X/derived", json={"type": "RENKO", "limit": 60})
    assert r.status_code == 200  # synthetic contract: unknown symbols never 404
    body = r.json()
    assert body["symbol"] == "ZZZ_UNKNOWN_X"
    assert body["source"] == "synthetic-seeded"
    assert body["source_count"] == 60


def test_unit_keys_documented_everywhere():
    for derived_type, params, unit_key, keys in (
        ("RENKO", {}, "bars", BAR_KEYS),
        ("RANGE", {"range_size": 100}, "bars", BAR_KEYS),
        ("KAGI", {}, "points", POINT_KEYS),
        ("PNF", {}, "bars", BAR_KEYS),
        ("LINEBREAK", {}, "bars", BAR_KEYS),
    ):
        r = client.post(DERIVED_URL, json={"type": derived_type, "limit": 60, "params": params})
        assert r.status_code == 200, derived_type
        units = r.json()[unit_key]
        for unit in units:
            assert set(unit) == keys, (derived_type, set(unit))


def test_kagi_omits_bars_others_omit_points():
    kagi = client.post(DERIVED_URL, json={"type": "KAGI", "limit": 60}).json()
    assert "bars" not in kagi and "points" in kagi
    renko = client.post(DERIVED_URL, json={"type": "RENKO", "limit": 60}).json()
    assert "points" not in renko and "bars" in renko


def test_labeling_bar_class_matches_series_endpoint():
    series = client.get("/api/v10/chartpro/فملی", params={"limit": 60}).json()
    derived = client.post(DERIVED_URL, json={"type": "KAGI", "limit": 60}).json()
    # bar_class is REUSED from the canonical _labeling_echo() logic, never
    # re-asserted: the two surfaces must always agree.
    assert derived["labeling"]["bar_class"] == series["labeling"]["bar_class"]
    assert derived["labeling"]["bar_class"]


def test_derived_endpoint_matches_engine_on_shared_window():
    # Same "1D" wall-clock bucket for both requests (the generator's only
    # clock input) -> the endpoint must expose the engine output verbatim.
    got = client.get("/api/v10/chartpro/فملی", params={"timeframe": "1D", "limit": 60}).json()
    post = client.post(
        DERIVED_URL,
        json={"type": "RANGE", "timeframe": "1D", "limit": 60, "params": {"range_size": 100}},
    ).json()
    assert post["source_count"] == len(got["ohlcv"])
    assert post["bars"] == range_bars(got["ohlcv"], range_size=100.0)


def test_body_type_literal_matches_registry():
    # the Literal pins the registry's type set — drift in either direction
    # is a governance failure and must be caught here.
    annotation = DerivedBody.model_fields["type"].annotation
    assert set(get_args(annotation)) == set(DERIVED_TYPES)
