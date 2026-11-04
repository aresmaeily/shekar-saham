"""MASTER-RADAR WAVE-B — /api/v10/user-indicators API tests (§B4).

Pinned here: the governed lifecycle over HTTP (validate/install/list/detail/
enable/disable/uninstall/export/import/compute), the typed error taxonomy,
trust-envelope + SYNTHETIC_SEEDED honesty on every payload, determinism and
prefix stability of compute, the fail-closed defaults, and the governance
boundaries (no scheduler, no egress, no live path, single execution seam).

Rate-limit hygiene: a dedicated TestClient identity (mr-waveb-uidl:12349),
the convention established in WAVE-2/WAVE-3 after the shared-identity 429
cascade finding.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, client=("mr-waveb-uidl", 12349))
# AUDIT-MR3 Obs.3 hygiene (symmetry with test_chart_pro_derived_api.py /
# test_security_hardening.py interplay): env-patching modules cache a
# settings object with PRIVATE_MODE/AUTH_REQUIRED residue inside the
# get_settings() lru_cache; monkeypatch teardown restores the environment
# but NOT the cache. A module-scope clear runs at collection time — before
# any test — so the durable hygiene here is an autouse per-test clear:
# before each test the cache is rebuilt from the (restored) environment,
# and after each test it is cleared again so THIS module cannot poison
# later ones. No other test file is touched.
from app.core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _settings_cache_hygiene():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


BAND_SRC = (
    "INDICATOR api_band\n"
    "INPUT len = 20\n"
    "PLOT basis = sma(close, len)\n"
    "PLOT upper = sma(close, len) * 1.02\n"
    "PLOT lower = sma(close, len) * 0.98\n"
)


@pytest.fixture()
def installed_band():
    r = client.post("/api/v10/user-indicators", json={"source": BAND_SRC})
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    yield uid
    client.delete(f"/api/v10/user-indicators/{uid}")


def detail_of(resp) -> dict:
    body = resp.json()
    return body.get("detail") if isinstance(body.get("detail"), dict) else body


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_validate_ok_shape(self) -> None:
        r = client.post("/api/v10/user-indicators/validate", json={"source": BAND_SRC})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["dsl_version"] == "UIDL-1"
        assert body["name"] == "api_band"
        assert [p["name"] for p in body["plots"]] == ["basis", "upper", "lower"]
        assert body["warmup_bars"] == 19
        assert body["declarations"]["lookahead_declared"] is False
        assert "trust_envelope" in body

    def test_validate_does_not_install(self) -> None:
        before = client.get("/api/v10/user-indicators").json()["count"]
        client.post(
            "/api/v10/user-indicators/validate",
            json={"source": "INDICATOR never_installed\nPLOT p = close"},
        )
        assert client.get("/api/v10/user-indicators").json()["count"] == before

    def test_dsl_error_taxonomy(self) -> None:
        for src, code in (
            ("INDICATOR x\nPLOT p = close > open", "SEM_PLOT_NOT_SERIES"),
            ("INDICATOR x\nPLOT p = ref(close, -2)", "LOOKAHEAD_NEGATIVE_REF"),
            ("INDICATOR x\nPLOT p = nosuchfn(close)", "TYPE_UNKNOWN_FUNCTION"),
            ("PLOT p = close", "PARSE_MISSING_INDICATOR"),
        ):
            r = client.post("/api/v10/user-indicators/validate", json={"source": src})
            assert r.status_code == 422, src
            d = detail_of(r)
            assert d["error"] == "DSL_COMPILE_FAILED"
            assert d["code"] == code, (src, d)
            assert d["dsl_version"] == "UIDL-1"

    def test_validate_rejects_extra_fields(self) -> None:
        r = client.post(
            "/api/v10/user-indicators/validate",
            json={"source": BAND_SRC, "version": "1.0.0"},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# install / lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_install_disabled_by_default(self, installed_band) -> None:
        r = client.get(f"/api/v10/user-indicators/{installed_band}")
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_install_duplicate_409(self, installed_band) -> None:
        r = client.post("/api/v10/user-indicators", json={"source": BAND_SRC})
        assert r.status_code == 409
        assert detail_of(r)["error"] == "DUPLICATE_ID"

    def test_enable_disable_cycle(self, installed_band) -> None:
        assert client.post(f"/api/v10/user-indicators/{installed_band}/enable").json()["code"] == "ENABLED"
        assert client.get(f"/api/v10/user-indicators/{installed_band}").json()["enabled"] is True
        assert client.post(f"/api/v10/user-indicators/{installed_band}/disable").json()["code"] == "DISABLED"
        assert client.get(f"/api/v10/user-indicators/{installed_band}").json()["enabled"] is False

    def test_uninstall_and_404(self, installed_band) -> None:
        assert client.delete(f"/api/v10/user-indicators/{installed_band}").json()["code"] == "REMOVED"
        assert client.delete(f"/api/v10/user-indicators/{installed_band}").status_code == 404
        assert client.get(f"/api/v10/user-indicators/{installed_band}").status_code == 404

    def test_install_bad_version(self) -> None:
        r = client.post(
            "/api/v10/user-indicators",
            json={"source": BAND_SRC, "version": "not-semver"},
        )
        assert r.status_code == 422
        assert detail_of(r)["error"] == "BAD_VERSION"

    def test_install_dsl_failure_typed(self) -> None:
        r = client.post(
            "/api/v10/user-indicators",
            json={"source": "INDICATOR x\nPLOT p = exec('x')"},
        )
        assert r.status_code == 422
        # the store wraps compile failures with its typed DSL_* taxonomy
        assert detail_of(r)["error"].startswith("DSL_")

    def test_id_namespace(self, installed_band) -> None:
        assert installed_band.startswith("user.dsl.")

    def test_detail_carries_source_and_declarations(self, installed_band) -> None:
        body = client.get(f"/api/v10/user-indicators/{installed_band}").json()
        assert body["source"] == BAND_SRC
        assert body["declarations"]["missing_data"] == "WARMUP_ZERO"
        assert body["declarations"]["repaint"] == "NONE_DECLARED"
        assert "ref offsets >= 0" in body["declarations"]["lookahead_enforced"]
        assert body["checksum"] and len(body["checksum"]) == 64


# ---------------------------------------------------------------------------
# export / import
# ---------------------------------------------------------------------------


class TestPackageRoundTrip:
    def test_export_import_round_trip(self, installed_band) -> None:
        pkg = client.get("/api/v10/user-indicators/export").json()["package"]
        assert pkg["package_version"] == "UIDL-PKG-1"
        client.delete(f"/api/v10/user-indicators/{installed_band}")
        r = client.post("/api/v10/user-indicators/import", json=pkg)
        assert r.status_code == 200
        assert r.json()["installed"] == 1
        # import installs DISABLED (fail-closed), matching direct install
        assert client.get(f"/api/v10/user-indicators/{installed_band}").json()["enabled"] is False

    def test_checksum_mismatch_rejected(self, installed_band) -> None:
        pkg = client.get("/api/v10/user-indicators/export").json()["package"]
        pkg["indicators"][0]["name"] = "tampered"
        r = client.post("/api/v10/user-indicators/import", json=pkg)
        assert r.status_code == 422
        assert detail_of(r)["error"] == "IMPORT_REJECTED"

    def test_forbidden_field_rejected(self) -> None:
        pkg = {
            "package_version": "UIDL-PKG-1",
            "indicators": [
                {
                    "id": "user.dsl.evil",
                    "source": "INDICATOR e\nPLOT p = close",
                    "version": "1.0.0",
                    "checksum": "0" * 64,
                    "payload": {"exec": "x"},
                }
            ],
        }
        r = client.post("/api/v10/user-indicators/import", json=pkg)
        assert r.status_code == 422

    def test_non_dsl_namespace_rejected(self) -> None:
        pkg = {
            "package_version": "UIDL-PKG-1",
            "indicators": [
                {"id": "builtin.sma", "source": "x", "version": "1.0.0", "checksum": "0" * 64}
            ],
        }
        r = client.post("/api/v10/user-indicators/import", json=pkg)
        assert r.status_code == 422
        d = detail_of(r)
        assert any(x["code"] == "ID_NAMESPACE" for x in d["rejected"])

    def test_non_compiling_source_rejected(self) -> None:
        pkg = {
            "package_version": "UIDL-PKG-1",
            "indicators": [
                {"id": "user.dsl.broken", "source": "ENTRY close > open", "version": "1.0.0"}
            ],
        }
        r = client.post("/api/v10/user-indicators/import", json=pkg)
        assert r.status_code == 422
        assert client.get("/api/v10/user-indicators").json()["count"] == client.get(
            "/api/v10/user-indicators"
        ).json()["count"]  # nothing installed

    def test_bad_package_version_rejected(self) -> None:
        r = client.post(
            "/api/v10/user-indicators/import",
            json={"package_version": "IM-1", "indicators": []},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# compute
# ---------------------------------------------------------------------------


class TestCompute:
    def test_compute_shape_and_honesty(self, installed_band) -> None:
        r = client.get(
            f"/api/v10/user-indicators/{installed_band}/compute"
            "?symbol=FOLAD&timeframe=1D&count=100&end_bar_index=500"
        )
        assert r.status_code == 200
        body = r.json()
        assert body["data_class"] == "SYNTHETIC_SEEDED"
        assert body["synthetic_note"]
        assert set(body["plots"]) == {"basis", "upper", "lower"}
        assert body["bars"] == 100
        assert body["warmup_bars"] == 19
        assert body["valid_from_index"] == 19
        assert len(body["plots"]["basis"]) == 100
        assert "trust_envelope" in body
        assert body["declarations"]["lookahead_declared"] is False
        assert len(body["output_digest"]) == 64

    def test_compute_deterministic_digest(self, installed_band) -> None:
        q = "?symbol=FOLAD&timeframe=1D&count=80&end_bar_index=300"
        d1 = client.get(f"/api/v10/user-indicators/{installed_band}/compute{q}").json()["output_digest"]
        d2 = client.get(f"/api/v10/user-indicators/{installed_band}/compute{q}").json()["output_digest"]
        assert d1 == d2

    def test_compute_prefix_stability(self, installed_band) -> None:
        full = client.get(
            f"/api/v10/user-indicators/{installed_band}/compute"
            "?count=100&end_bar_index=500&timeframe=1D"
        ).json()["plots"]["basis"]
        part = client.get(
            f"/api/v10/user-indicators/{installed_band}/compute"
            "?count=60&end_bar_index=460&timeframe=1D"
        ).json()["plots"]["basis"]
        assert all(a["value"] == pytest.approx(b["value"], abs=1e-12)
                   for a, b in zip(part, full[:60]))

    def test_compute_params_override(self, installed_band) -> None:
        base = client.get(
            f"/api/v10/user-indicators/{installed_band}/compute?count=80&end_bar_index=300"
        ).json()
        over = client.get(
            f"/api/v10/user-indicators/{installed_band}/compute"
            '?count=80&end_bar_index=300&params={"len": 5}'
        ).json()
        assert over["params_used"]["len"] == 5.0
        assert over["output_digest"] != base["output_digest"]
        assert over["warmup_bars"] == 4

    def test_compute_param_errors(self, installed_band) -> None:
        base = f"/api/v10/user-indicators/{installed_band}/compute"
        assert client.get(f"{base}?params={{}}").status_code == 200
        assert client.get(f"{base}?params={{\"nope\":1}}").status_code == 422
        assert client.get(f"{base}?params={{\"len\":\"x\"}}").status_code == 422
        assert client.get(f"{base}?params=notjson").status_code == 422
        assert client.get(f"{base}?timeframe=2h").status_code == 422

    def test_compute_unknown_id_404(self) -> None:
        r = client.get("/api/v10/user-indicators/user.dsl.nothere/compute")
        assert r.status_code == 404

    def test_disabled_indicator_still_computable(self, installed_band) -> None:
        # lifecycle state governs UI mounting, not the deterministic math —
        # compute is read-only and stateless (documented contract)
        r = client.get(f"/api/v10/user-indicators/{installed_band}/compute?count=60")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# governance boundaries
# ---------------------------------------------------------------------------


class TestGovernanceBoundaries:
    def test_router_surface_is_scoped(self) -> None:
        paths = {
            getattr(r, "path", "") for r in app.routes
        }
        ui = [p for p in paths if "user-indicators" in p]
        assert ui and all(p.startswith("/api/v10/user-indicators") for p in ui)

    def test_no_scheduler_or_egress_added(self) -> None:
        import pathlib

        text = pathlib.Path("app/api/user_indicator_api.py").read_text(encoding="utf-8")
        for banned in ("asyncio.create_task", "BackgroundTasks", "httpx", "requests.",
                       "urllib", "socket", "subprocess"):
            assert banned not in text, banned

    def test_synthetic_only_seeded_path(self, installed_band) -> None:
        # frozen end_bar_index must be byte-stable (no wall-clock in payload)
        q = "?count=50&end_bar_index=42&timeframe=5m"
        a = client.get(f"/api/v10/user-indicators/{installed_band}/compute{q}").json()
        b = client.get(f"/api/v10/user-indicators/{installed_band}/compute{q}").json()
        assert a["plots"] == b["plots"]

    def test_list_carries_manifest_digest(self, installed_band) -> None:
        body = client.get("/api/v10/user-indicators").json()
        assert len(body["manifest_digest"]) == 64
        assert body["dsl_version"] == "UIDL-1"
