"""MASTER-WAVE-2 — regression tests for the Wave-2 audit-authorized hardening.

Covers the authorized repo-side findings fixed in this wave (each traceable to
its audit record):
- W2-DATA F-3: non-finite refusal in the provider scalar helpers + the tsetmc
  JSON-path ``pl <= 0`` row gate (parity with the legacy CSV path).
- W2-DATA F-2: per-cycle source-label capture in ``MarketService.refresh`` —
  a concurrent cycle's ``last_source`` overwrite during a lock suspension can
  no longer leak into this cycle's commit.
- W2-SEC C-6: the rate limiter's attacker-keyed stores are hard-bounded.
- W2-SEC C-1/C-3/C-4/C-5 + C-12: workflow least-privilege + SHA/digest pins +
  .gitignore secret patterns + runner Python alignment (config-contract pins).
- W2-DATA F-4: the test-suite isolation guard is FAIL-CLOSED (subprocess
  proof: a host-exported live DATA_SOURCE aborts the session).
- P3 F1 (W2-QUANT): HoldoutAttestation cross-field type-level validator —
  forged direct constructions are refused; the legitimate path is unchanged.

Discipline: offline (DATA_SOURCE=mock pinned), no network, subprocess probes
inherit a scrubbed environment explicitly constructed per case.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.rate_limiter import InMemoryRateLimiter
from app.data.providers import _safe_float, _safe_int, tsetmc_mw_to_snapshot
from app.engines.holdout import HoldoutAttestation
from app.models.schemas import SymbolSnapshot
from app.services.market_service import MarketService

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# W2-DATA F-3 — provider scalar hardening
# ---------------------------------------------------------------------------


def test_safe_float_refuses_non_finite_to_default() -> None:
    nan = float("nan")
    inf = float("inf")
    assert _safe_float(nan) == 0.0
    assert _safe_float(-inf) == 0.0
    assert _safe_float(inf, default=5.0) == 5.0
    assert _safe_float("nan") == 0.0  # string form parses to nan → refused
    assert _safe_float(3.5) == 3.5
    assert _safe_float(None) == 0.0
    assert _safe_float("") == 0.0
    assert _safe_float("abc") == 0.0


def test_safe_int_refuses_non_finite_and_overflow() -> None:
    nan = float("nan")
    inf = float("inf")
    assert _safe_int(nan) == 0
    assert _safe_int(inf) == 0  # int(inf) raises OverflowError pre-fix
    assert _safe_int(-inf, default=7) == 7
    assert _safe_int("inf") == 0
    assert _safe_int(3.9) == 3
    assert _safe_int("12") == 12


def test_tsetmc_json_path_drops_non_positive_last_price() -> None:
    live_row = {
        "lva": "فولاد",
        "pl": 1000.0,
        "pc": 1050.0,
        "py": 1000.0,
        "plp": 0.0,
        "tvol": 1000.0,
    }
    snap = tsetmc_mw_to_snapshot(live_row)
    assert snap is not None and snap.l18 == "فولاد"
    # Halted / absent quote: last price zero → row dropped (legacy parity).
    zero_row = dict(live_row, pl=0)
    assert tsetmc_mw_to_snapshot(zero_row) is None
    negative_row = dict(live_row, pl=-5)
    assert tsetmc_mw_to_snapshot(negative_row) is None
    # NaN last price: _safe_float refuses to 0.0 → the pl<=0 gate drops it.
    nan_row = dict(live_row, pl=float("nan"))
    assert tsetmc_mw_to_snapshot(nan_row) is None


# ---------------------------------------------------------------------------
# W2-DATA F-2 — per-cycle source-label capture
# ---------------------------------------------------------------------------


class _SourceOverwritingProvider:
    """Two-fetch provider whose shared ``last_source`` is overwritten by the
    second fetch — modeling a concurrent cycle completing during cycle A's
    lock suspension."""

    def __init__(self) -> None:
        self.settings = None
        self.last_source = "src_initial"
        self.last_error = ""
        self.calls = 0

    async def fetch(self):  # noqa: ANN201
        self.calls += 1
        if self.calls == 1:
            self.last_source = "src_a"
            return [SymbolSnapshot(l18="فولاد", l30="ف", pl=1.0, py=1.0)]
        self.last_source = "src_b"  # concurrent cycle's overwrite
        return [SymbolSnapshot(l18="فولاد", l30="ف", pl=2.0, py=1.0)]


class _SuspendingLock:
    """asyncio.Lock that runs a one-shot hook just before the N-th acquisition
    (the Q-1 lock-seam pattern). refresh() acquires the lock in Phase 0 (fast
    check), Phase 1 (mirror flag) and Phase 3 (commit) — target_n selects
    which acquisition carries the injected suspension."""

    def __init__(self, target_n: int = 2) -> None:
        self._inner = asyncio.Lock()
        self._hook: Any = None
        self._target_n = target_n
        self._acquisitions = 0

    def arm(self, hook: Any) -> None:
        self._hook = hook

    async def __aenter__(self) -> None:
        self._acquisitions += 1
        if self._hook is not None and self._acquisitions == self._target_n:
            hook, self._hook = self._hook, None
            await hook()
        await self._inner.acquire()

    async def __aexit__(self, *exc: Any) -> None:
        self._inner.release()


def _fresh_service(provider: Any, lock: Any) -> MarketService:
    service = MarketService.__new__(MarketService)
    service.provider = provider
    service.settings = None
    service._lock = lock
    service._last_analysis = None
    service._last_symbols = [SymbolSnapshot(l18="فولاد", l30="ف", pl=1.0, py=1.0)]
    service._last_fetch_ts = 0.0
    service._last_big_moves = []
    service._last_tablocastic = []
    service._last_confluence = {}
    service._row_cache = []
    service._seen_alert_keys = set()
    service._trust_level = "mixed"
    service._source = "none"
    service._flow_meta = {}
    service._fetch_degraded = False
    service._fund_cache = {}
    service._fund_cache_max = 200
    service._last_prune_ts = 0.0
    service._prune_interval = 3600
    return service


def test_refresh_commits_per_cycle_source_not_shared_overwrite() -> None:
    provider = _SourceOverwritingProvider()
    lock = _SuspendingLock(target_n=2)
    service = _fresh_service(provider, lock)

    async def scenario() -> None:
        async def run_b_during_a_lock() -> None:
            # Cycle B's fetch: overwrites the SHARED last_source label.
            await provider.fetch()

        lock.arm(run_b_during_a_lock)
        await service.refresh(force=True)

    asyncio.run(scenario())
    # Pre-fix shape: Phase 3 read the SHARED attribute after the suspending
    # lock → committed "src_b" (cycle B's label). The per-cycle capture
    # commits cycle A's own label.
    assert service._source == "src_a"
    assert provider.calls == 2


def test_refresh_degraded_cycle_keeps_provider_label_without_crash() -> None:
    """Degraded path: capture happens at the top of the except body (before
    the suspending lock) — the recycled board keeps the provider's best-known
    label and the false-fresh guard (Q-1) still preserves the old stamp."""

    class _FailingProvider(_SourceOverwritingProvider):
        async def fetch(self):  # noqa: ANN201
            self.calls += 1
            self.last_source = "src_outage"
            raise RuntimeError("synthetic outage")

    provider = _FailingProvider()
    lock = _SuspendingLock(target_n=2)  # armed hook never fires (fetch fails)
    old_ts = 1_700_000_000.0
    service = _fresh_service(provider, lock)
    service._last_fetch_ts = old_ts

    async def scenario() -> None:
        await service.refresh(force=True)

    asyncio.run(scenario())
    assert service._source == "src_outage"
    assert service._last_fetch_ts == old_ts  # Q-1 guard unchanged
    assert service._fetch_degraded is False  # one-cycle mirror consumed


# ---------------------------------------------------------------------------
# W2-SEC C-6 — rate limiter distinct-key bound
# ---------------------------------------------------------------------------


def test_rate_limiter_store_keys_hard_bounded() -> None:
    limiter = InMemoryRateLimiter()
    limiter._MAX_DISTINCT_KEYS = 8  # shrink for the probe (same code path)
    for i in range(50):
        ip = f"10.0.{i // 256}.{i % 256}"
        limiter.check_limit(ip, "/api/health")
        limiter.record(ip, "/api/health")
    assert len(limiter.general) <= 8
    assert len(limiter.path_specific) <= 8
    # The bound never breaks the normal single-client limit contract: the
    # refusal fires on the check AFTER 150 recorded requests.
    fresh = InMemoryRateLimiter()
    for _ in range(150):
        limited, _, _ = fresh.check_limit("1.2.3.4", "/api/health")
        assert not limited
        fresh.record("1.2.3.4", "/api/health")
    limited, _, _ = fresh.check_limit("1.2.3.4", "/api/health")
    assert limited  # 151st check within the window is refused as before


# ---------------------------------------------------------------------------
# P3 F1 — HoldoutAttestation type-level forgery refusals
# ---------------------------------------------------------------------------


def _legit_attestation_kwargs() -> dict[str, Any]:
    return dict(
        strategy_id="s1",
        holdout_boundary_ts=100.0,
        insample_first_ts=0.0,
        insample_last_ts=99.0,
        holdout_first_ts=100.0,
        holdout_last_ts=150.0,
        insample_bar_count=10,
        holdout_bar_count=5,
    )


def test_attestation_legitimate_shape_validates() -> None:
    att = HoldoutAttestation(**_legit_attestation_kwargs())
    assert att.isolated is True


@pytest.mark.parametrize(
    "mutation, reason",
    [
        (dict(insample_bar_count=0), "attestation_insample_bar_count_below_one"),
        (dict(holdout_bar_count=0), "attestation_holdout_bar_count_below_one"),
        (
            dict(insample_first_ts=99.0, insample_last_ts=1.0),
            "attestation_insample_window_inverted",
        ),
        (
            dict(holdout_first_ts=160.0, holdout_last_ts=150.0),
            "attestation_holdout_window_inverted",
        ),
        (
            dict(insample_last_ts=100.0),
            "attestation_insample_crosses_holdout_boundary",
        ),
        (dict(holdout_first_ts=99.0), "attestation_holdout_before_boundary"),
    ],
)
def test_attestation_forged_direct_constructions_refused(
    mutation: dict[str, Any], reason: str
) -> None:
    kwargs = _legit_attestation_kwargs()
    kwargs.update(mutation)
    with pytest.raises(ValidationError, match=reason):
        HoldoutAttestation(**kwargs)


def test_attestation_non_finite_fields_refused_by_model_config() -> None:
    kwargs = _legit_attestation_kwargs()
    kwargs["insample_last_ts"] = float("nan")
    with pytest.raises(ValidationError):
        HoldoutAttestation(**kwargs)


# ---------------------------------------------------------------------------
# W2-DATA F-4 — test-suite isolation guard is FAIL-CLOSED (subprocess proof)
# ---------------------------------------------------------------------------


def _run_conftest_import(env_overrides: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"DATA_SOURCE", "RADAR_ALLOW_LIVE_TESTS", "BRSAPI_KEY"}
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(env_overrides)
    code = "import sys; sys.path.insert(0, 'tests'); import conftest"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT / "backend"),
        env=env,
        capture_output=True,
        timeout=60,
    )


def test_conftest_guard_aborts_host_exported_live_source() -> None:
    proc = _run_conftest_import({"DATA_SOURCE": "auto"})
    assert proc.returncode != 0, "fail-closed guard must abort the session"
    assert b"TEST-ISOLATION GUARD" in proc.stderr


def test_conftest_guard_allows_mock_and_explicit_opt_in() -> None:
    ok_default = _run_conftest_import({})
    assert ok_default.returncode == 0, ok_default.stderr
    assert ok_default.stdout == b"" or b"mock" not in ok_default.stdout
    ok_mock = _run_conftest_import({"DATA_SOURCE": "mock"})
    assert ok_mock.returncode == 0, ok_mock.stderr
    ok_opt_in = _run_conftest_import(
        {"DATA_SOURCE": "auto", "RADAR_ALLOW_LIVE_TESTS": "1"}
    )
    assert ok_opt_in.returncode == 0, ok_opt_in.stderr


# ---------------------------------------------------------------------------
# W2-SEC C-1/C-3/C-4/C-5/C-12 — CI/CD config-contract pins
# ---------------------------------------------------------------------------


def test_workflows_least_privilege_and_sha_pinned() -> None:
    for name in ("ci.yml", "windows.yml"):
        text = (REPO_ROOT / ".github" / "workflows" / name).read_text("utf-8")
        assert "permissions:" in text and "contents: read" in text, name
        for action in ("actions/checkout@", "actions/setup-python@"):
            idx = text.index(action) + len(action)
            ref = text[idx : idx + 40]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), (
                f"{name}: {action} must be pinned by a 40-hex commit SHA"
            )


def test_workflows_python_version_alignment() -> None:
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    win = (REPO_ROOT / ".github" / "workflows" / "windows.yml").read_text("utf-8")
    assert 'python-version: "3.13"' in ci
    assert 'python-version: "3.13"' in win
    assert 'python-version: "3.12"' not in win


def test_dockerfile_base_pinned_by_manifest_digest() -> None:
    text = (REPO_ROOT / "Dockerfile").read_text("utf-8")
    line = next(l for l in text.splitlines() if l.startswith("FROM "))
    assert "@sha256:" in line, line
    digest = line.split("@sha256:", 1)[1].split()[0]
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)


def test_gitignore_covers_secret_material_patterns() -> None:
    text = (REPO_ROOT / ".gitignore").read_text("utf-8")
    for pattern in (".env.*", "*.key", "*.pem"):
        assert pattern in text, pattern
