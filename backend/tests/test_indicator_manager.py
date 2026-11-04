"""PKG-F tests — indicator installation & lifecycle manager (§B4).

Offline, in-memory only.  Covers: initial built-in state, deep package
validation (reserved ids, namespaces, whitelists, checksums, forbidden code-
carrying fields at any depth, size budgets), the enable/disable/remove state
machine, version policy, template composition, and manifest/package export /
import round-trips with digest determinism.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

from app.engines.indicator_catalog import BUILT_IN_CATALOG
from app.engines.indicator_manager import (
    BUDGET_ENTRIES,
    BUDGET_PACKAGE_SIZE,
    DEFAULT_ENABLED_BUILT_INS,
    IndicatorManager,
    entry_checksum,
)


# ---------------------------------------------------------------------------
# Package builders
# ---------------------------------------------------------------------------
def make_entry(idx: str = "1", **overrides: Any) -> Dict[str, Any]:
    """A valid, checksummed ``user.*`` package entry (data-only metadata)."""
    entry: Dict[str, Any] = {
        "id": f"user.alpha{idx}",
        "name_en": f"Alpha {idx}",
        "name_fa": "نوسان‌نمای آلفا",
        "category": "momentum",
        "version": "1.0.0",
        "author": "pkg-f tester",
        "math_definition": "Alpha[i] = (close[i] - close[i-1]) / close[i-1]; warm-up: 1 bar.",
        "inputs": [
            {"name": "scale", "type": "float", "default": 1.0, "minimum": 0.0, "maximum": 10.0}
        ],
        "warmup_bars": 1,
        "series_inputs": ["close"],
        "permissions": ["series:read"],
    }
    entry.update(overrides)
    entry["checksum"] = entry_checksum(entry)
    return entry


def make_package(*entries: Dict[str, Any]) -> Dict[str, Any]:
    return {"package_version": "IP-1", "indicators": list(entries)}


ALL_SERIES = frozenset({"open", "high", "low", "close", "volume"})


def rejected_codes(report) -> Dict[str, str]:
    return {r.id: r.code for r in report.rejected}


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------
def test_initial_state_all_builtins_installed():
    m = IndicatorManager()
    assert m.installed_ids() == sorted(s.id for s in BUILT_IN_CATALOG)
    assert len(m.installed_ids()) >= 14
    for eid in m.installed_ids():
        e = m.get_entry(eid)
        assert e is not None and e.source == "BUILTIN"
        assert e.checksum  # manager computed a checksum for every entry
        payload = e.model_dump(mode="json")
        payload.pop("checksum")
        assert entry_checksum(payload) == e.checksum  # self-consistent


def test_default_enable_set_exact():
    m = IndicatorManager()
    enabled = {eid for eid in m.installed_ids() if m.is_enabled(eid)}
    assert enabled == set(DEFAULT_ENABLED_BUILT_INS)
    assert enabled == {
        "builtin.sma",
        "builtin.ema",
        "builtin.rsi",
        "builtin.macd",
        "builtin.bollinger",
        "builtin.atr",
    }
    assert m.is_enabled("builtin.stochastic") is False
    assert m.is_enabled("builtin.obv") is False


def test_digest_determinism_fresh_managers():
    assert IndicatorManager().manifest_digest() == IndicatorManager().manifest_digest()


# ---------------------------------------------------------------------------
# Install / enable lifecycle
# ---------------------------------------------------------------------------
def test_install_valid_package_ok_and_disabled():
    m = IndicatorManager()
    report = m.install_package(make_package(make_entry("1")))
    assert report.ok is True
    assert report.installed == 1 and report.rejected == []
    assert m.is_installed("user.alpha1")
    assert m.is_enabled("user.alpha1") is False  # user must enable explicitly
    e = m.get_entry("user.alpha1")
    assert e is not None and e.source == "IMPORTED_SAFE_JSON"


def test_enable_then_disable_user_entry():
    m = IndicatorManager()
    m.install_package(make_package(make_entry("1")))
    op = m.enable("user.alpha1", frozenset({"close"}))
    assert op.ok is True and op.code == "OK"
    assert m.is_enabled("user.alpha1") is True
    op = m.disable("user.alpha1")
    assert op.ok is True and m.is_enabled("user.alpha1") is False


def test_enable_fail_closed_missing_series():
    m = IndicatorManager()
    m.install_package(make_package(make_entry("1", series_inputs=["close", "volume"])))
    op = m.enable("user.alpha1")  # default available_series = {} → fail closed
    assert op.ok is False and op.code == "MISSING_SERIES_INPUT"
    assert m.is_enabled("user.alpha1") is False
    op = m.enable("user.alpha1", frozenset({"open"}))  # still missing close+volume
    assert op.ok is False and op.code == "MISSING_SERIES_INPUT"
    op = m.enable("user.alpha1", ALL_SERIES)
    assert op.ok is True


def test_enable_unknown_id():
    m = IndicatorManager()
    op = m.enable("user.ghost", ALL_SERIES)
    assert op.ok is False and op.code == "UNKNOWN_ID"


def test_enable_builtin_requires_series():
    m = IndicatorManager()
    op = m.enable("builtin.obv", frozenset({"close"}))  # obv needs volume too
    assert op.ok is False and op.code == "MISSING_SERIES_INPUT"
    op = m.enable("builtin.obv", ALL_SERIES)
    assert op.ok is True and m.is_enabled("builtin.obv") is True
    op = m.enable("builtin.stochastic", frozenset({"high", "low", "close"}))
    assert op.ok is True


# ---------------------------------------------------------------------------
# Duplicate / version policy
# ---------------------------------------------------------------------------
def test_duplicate_same_version_rejected():
    m = IndicatorManager()
    assert m.install_package(make_package(make_entry("1"))).ok
    report = m.install_package(make_package(make_entry("1")))
    assert report.ok is False and report.installed == 0
    assert rejected_codes(report) == {"user.alpha1": "DUPLICATE_ID"}
    assert "allow_upgrade" in report.rejected[0].detail  # policy note


def test_greater_version_rejected_without_allow_upgrade():
    m = IndicatorManager()
    assert m.install_package(make_package(make_entry("1"))).ok
    report = m.install_package(make_package(make_entry("1", version="1.1.0")))
    assert report.ok is False
    assert rejected_codes(report) == {"user.alpha1": "DUPLICATE_ID"}


def test_greater_version_installed_with_allow_upgrade():
    m = IndicatorManager()
    assert m.install_package(make_package(make_entry("1"))).ok
    report = m.install_package(
        make_package(make_entry("1", version="1.1.0")), allow_upgrade=True
    )
    assert report.ok is True and report.installed == 1
    e = m.get_entry("user.alpha1")
    assert e is not None and e.version == "1.1.0"
    assert m.is_enabled("user.alpha1") is False  # upgraded entry stays disabled


def test_lower_version_rejected_even_with_allow_upgrade():
    m = IndicatorManager()
    assert m.install_package(make_package(make_entry("1", version="1.1.0"))).ok
    report = m.install_package(
        make_package(make_entry("1", version="1.0.0")), allow_upgrade=True
    )
    assert report.ok is False
    assert rejected_codes(report) == {"user.alpha1": "DUPLICATE_ID"}


# ---------------------------------------------------------------------------
# Remove semantics
# ---------------------------------------------------------------------------
def test_remove_builtin_forbidden():
    m = IndicatorManager()
    op = m.remove("builtin.sma")
    assert op.ok is False and op.code == "REMOVE_BUILTIN_FORBIDDEN"
    assert m.is_installed("builtin.sma")


def test_remove_user_entry_ok():
    m = IndicatorManager()
    assert m.install_package(make_package(make_entry("1"))).ok
    op = m.remove("user.alpha1")
    assert op.ok is True
    assert not m.is_installed("user.alpha1")


def test_remove_unknown_id():
    m = IndicatorManager()
    op = m.remove("user.ghost")
    assert op.ok is False and op.code == "UNKNOWN_ID"


# ---------------------------------------------------------------------------
# Deep validation / rejections
# ---------------------------------------------------------------------------
def test_checksum_tamper_rejected():
    m = IndicatorManager()
    entry = make_entry("1")
    entry["math_definition"] = "tampered after checksum"  # invalidate integrity
    report = m.install_package(make_package(entry))
    assert report.ok is False
    assert rejected_codes(report) == {"user.alpha1": "CHECKSUM_MISMATCH"}


def test_forbidden_field_nested_deep():
    m = IndicatorManager()
    doc = {
        "package_version": "IP-1",
        "indicators": [{"id": "user.x", "meta": {"sub": {"code": "evil"}}}],
    }
    report = m.install_package(doc)
    assert report.ok is False and report.installed == 0
    assert report.rejected[0].code == "FORBIDDEN_FIELD"
    assert "code" in report.rejected[0].detail


def test_forbidden_field_dunder_key():
    m = IndicatorManager()
    doc = {"package_version": "IP-1", "__proto__": {"x": 1}, "indicators": []}
    report = m.install_package(doc)
    assert report.ok is False
    assert report.rejected[0].code == "FORBIDDEN_FIELD"


def test_permission_not_whitelisted():
    m = IndicatorManager()
    entry = make_entry("1", permissions=["series:read", "shell:exec"])
    report = m.install_package(make_package(entry))
    assert report.ok is False
    assert rejected_codes(report) == {"user.alpha1": "PERMISSION_NOT_WHITELISTED"}


def test_reserved_builtin_id_rejected():
    m = IndicatorManager()
    entry = make_entry("1", id="builtin.sma")
    report = m.install_package(make_package(entry))
    assert report.ok is False
    assert rejected_codes(report) == {"builtin.sma": "RESERVED_ID"}
    # the shipped builtin.sma is untouched
    assert m.get_entry("builtin.sma") is not None


def test_id_namespace_requires_user_prefix():
    m = IndicatorManager()
    report = m.install_package(make_package(make_entry("1", id="sma")))
    assert report.ok is False
    assert rejected_codes(report) == {"sma": "ID_NAMESPACE"}


def test_budget_entries_65():
    m = IndicatorManager()
    entries = [make_entry(str(i), version="1.0.0") for i in range(BUDGET_ENTRIES + 1)]
    assert len(entries) == 65
    report = m.install_package(make_package(*entries))
    assert report.ok is False and report.installed == 0
    assert report.rejected[0].code == "BUDGET_ENTRIES"


def test_budget_package_size_oversized():
    m = IndicatorManager()
    assert BUDGET_PACKAGE_SIZE == 256 * 1024
    entry = make_entry("1", math_definition="A" * 300_000)
    report = m.install_package(make_package(entry))
    assert report.ok is False and report.installed == 0
    assert report.rejected[0].code == "BUDGET_PACKAGE_SIZE"


def test_schema_invalid_entry_and_package_version():
    m = IndicatorManager()
    bad_version = {"package_version": "IP-2", "indicators": []}
    report = m.install_package(bad_version)
    assert report.ok is False and report.rejected[0].code == "SCHEMA_INVALID"
    entry = make_entry("1")
    entry["warmup_bars"] = -1  # violates ge=0 (checksum stays valid over the value set)
    entry["checksum"] = entry_checksum(entry)
    report = m.install_package(make_package(entry))
    assert report.ok is False
    assert rejected_codes(report) == {"user.alpha1": "SCHEMA_INVALID"}
    report = m.install_package({"package_version": "IP-1", "indicators": "nope"})
    assert report.rejected[0].code == "SCHEMA_INVALID"


def test_install_empty_package_ok():
    m = IndicatorManager()
    report = m.install_package({"package_version": "IP-1", "indicators": []})
    assert report.ok is True and report.installed == 0 and report.rejected == []


# ---------------------------------------------------------------------------
# Version policy / templates
# ---------------------------------------------------------------------------
def test_version_check_semantics():
    m = IndicatorManager()
    # builtin.macd ships at 1.2.0: major equal + installed minor >= needed
    assert m.version_check("builtin.macd", "1.2.9") is True  # patch ignored
    assert m.version_check("builtin.macd", "1.2.0") is True
    assert m.version_check("builtin.macd", "1.1.0") is True  # older minor ok
    assert m.version_check("builtin.macd", "1.3.0") is False  # newer minor needed
    assert m.version_check("builtin.macd", "2.0.0") is False  # major mismatch
    assert m.version_check("user.ghost", "1.0.0") is False  # unknown id
    assert m.version_check("builtin.macd", "not-semver") is False


def test_template_compose_ok():
    m = IndicatorManager()
    tv = m.template_compose(["builtin.sma", "builtin.rsi"])
    assert tv.ok is True and tv.code == "OK"
    assert tv.ids == ["builtin.sma", "builtin.rsi"]
    assert tv.total_warmup == 19  # max(19, 14)
    assert tv.permissions == ["series:read"]
    assert [t.id for t in tv.indicators] == tv.ids
    tv = m.template_compose(["builtin.sma", "builtin.vwap"])
    assert tv.permissions == ["chart:overlay", "series:read"]  # sorted union
    assert tv.total_warmup == 19


def test_template_compose_unknown_and_duplicate():
    m = IndicatorManager()
    tv = m.template_compose(["builtin.sma", "user.ghost"])
    assert tv.ok is False and tv.code == "UNKNOWN_ID"
    tv = m.template_compose(["builtin.sma", "builtin.sma"])
    assert tv.ok is False and tv.code == "DUPLICATE_ID"


# ---------------------------------------------------------------------------
# Manifest / package export-import round-trips
# ---------------------------------------------------------------------------
def test_manifest_round_trip_digest_equal():
    m1 = IndicatorManager()
    assert m1.install_package(make_package(make_entry("1"))).ok
    assert m1.enable("user.alpha1", frozenset({"close"})).ok
    digest = m1.manifest_digest()
    doc = m1.export_manifest()
    m2 = IndicatorManager()
    op = m2.import_manifest(doc)
    assert op.ok is True and op.code == "OK"
    assert m2.manifest_digest() == digest
    assert m2.is_enabled("user.alpha1") is True
    assert m2.is_enabled("builtin.stochastic") is False


def test_digest_changes_with_state_and_restores_after_remove():
    m = IndicatorManager()
    digest_fresh = m.manifest_digest()
    assert m.install_package(make_package(make_entry("1"))).ok
    assert m.manifest_digest() != digest_fresh
    assert m.remove("user.alpha1").ok
    assert m.manifest_digest() == digest_fresh


def test_export_import_package_round_trip():
    m1 = IndicatorManager()
    assert m1.install_package(make_package(make_entry("9", version="2.3.4"))).ok
    pkg = m1.export_package(["user.alpha9"])
    assert pkg["package_version"] == "IP-1"
    m2 = IndicatorManager()
    report = m2.install_package(pkg)
    assert report.ok is True and report.installed == 1
    e = m2.get_entry("user.alpha9")
    assert e is not None
    assert e.version == "2.3.4" and e.enabled is False
    # exported package survives a second manager hop unchanged
    pkg2 = m2.export_package(["user.alpha9"])
    assert pkg2 == pkg


def test_export_package_unknown_id_raises():
    m = IndicatorManager()
    with pytest.raises(ValueError):
        m.export_package(["user.ghost"])


def test_import_manifest_bad_version_rejected():
    m = IndicatorManager()
    op = m.import_manifest({"manifest_version": "IM-0", "entries": []})
    assert op.ok is False and op.code == "MANIFEST_VERSION"
    op = m.import_manifest("not-a-dict")
    assert op.ok is False and op.code == "MANIFEST_VERSION"


def test_import_manifest_checksum_tamper_rejected():
    m1 = IndicatorManager()
    doc = m1.export_manifest()
    tampered = copy.deepcopy(doc)
    tampered["entries"][0]["math_definition"] = "tampered"
    m2 = IndicatorManager()
    op = m2.import_manifest(tampered)
    assert op.ok is False and op.code == "CHECKSUM_MISMATCH"
    # failed import leaves current state intact
    assert m2.installed_ids() == sorted(s.id for s in BUILT_IN_CATALOG)


def test_import_manifest_forbidden_field_rejected():
    m1 = IndicatorManager()
    doc = m1.export_manifest()
    tampered = copy.deepcopy(doc)
    tampered["entries"][0]["meta"] = {"script": "x"}
    m2 = IndicatorManager()
    op = m2.import_manifest(tampered)
    assert op.ok is False and op.code == "FORBIDDEN_FIELD"
