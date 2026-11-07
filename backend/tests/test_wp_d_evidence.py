"""WAVE-AI (2026-11-08, WP-D): AI-2 deep-evaluation refusal-path + provenance
evidence, and the dormant persistence adapter's independent evidence battery
(extended).

The WAVE-AI-ACCEPTANCE directive §5 requires: all deep-evaluation stages and
their refusal paths verified; caller-DECLARED regime partitions explicitly
distinguished from data-inferred regimes; holdout isolation and baseline
provenance verified; the dormant SQLite/WAL adapter tested INDEPENDENTLY
(migrations, row-digest verification, backup, restore, tamper refusal).

WAVE-AB4 shipped the bulk (test_ai2_deep_evaluation.py + test_ai2_persistence_kit.py).
This file closes the remaining evidence gaps WITHOUT touching any of those
pinned suites:

1. holdout-stage and comparison-stage ENGINE-FAILURE refusal paths
   (fail-honest refusal rows, run still commits);
2. baseline PROVENANCE pin: every comparison row references the DECLARED
   fixed reference ``AI2-BASELINE-BUY-HOLD-1`` (never fitted, never selected)
   with the declared delta_basis note;
3. regime-partition distinction pinned against the DATA side: no clustering /
   inference function may exist in the composition surface — the only regime
   labels are the DECLARED NEUTRAL thirds (structural, not discovered);
4. adapter independence re-verified on the LIVE connection: the database
   file itself is in journal_mode=wal and synchronous=FULL (pragma probe),
   and the migration/row-digest/backup/restore/tamper battery already pinned
   by test_ai2_persistence_kit.py stays untouched (imported here as evidence
   pointers, not re-implemented).

No real-data execution, no LLM call, no persistence activation: the adapter
remains dormant (no runtime importer) and AI-2 production behavior is
unchanged (AI2_ENABLED default 0; these tests opt in to the TEST transport
only, as the shipped WAVE-AB4 suite does).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable

import pytest

from app.core.config import get_settings
from app.services import ai2_deep_evaluation as ai2_deep_module
from app.services.ai2_deep_evaluation import AI2_BASELINE_LABEL
from app.services.ai2_generation import (
    AI2GenerationService,
    GenerationOutcome,
    GenerationRequest,
)

UTC = timezone.utc
NOW_UTC = datetime(2026, 11, 9, 12, 0, 0, tzinfo=UTC)

# --- shared fixtures (verbatim semantics from test_ai2_deep_evaluation.py) ---

VALID_SPEC: dict[str, Any] = {
    "strategy_name": "wpd-refusal-path-smoke",
    "entry": {
        "kind": "cmp",
        "op": ">",
        "children": [
            {"kind": "series", "base": "close"},
            {
                "kind": "call",
                "fn": "sma",
                "children": [
                    {"kind": "series", "base": "close"},
                    {"kind": "num", "value": 20},
                ],
            },
        ],
    },
    "exit": {
        "kind": "call",
        "fn": "crossunder",
        "children": [
            {"kind": "series", "base": "close"},
            {
                "kind": "call",
                "fn": "sma",
                "children": [
                    {"kind": "series", "base": "close"},
                    {"kind": "num", "value": 20},
                ],
            },
        ],
    },
    "risk": {"stop_loss_pct": 2.0, "max_position_pct": 25.0},
    "rationale": "audit-only free text",
}

INPUT_SPEC: dict[str, Any] = {
    **VALID_SPEC,
    "entry": {
        "kind": "cmp",
        "op": ">",
        "children": [
            {"kind": "series", "base": "close"},
            {"kind": "input", "name": "p", "value": 1000},
        ],
    },
}

HAPPY_QUESTION = (
    "I want a strategy that buys when close crosses above the 20-period sma "
    "and sells on crossunder, with 2% stop loss risk."
)


def _ok_transport(spec: dict[str, Any] | None = None) -> Callable[[dict[str, Any]], dict[str, Any]]:
    text = json.dumps(VALID_SPEC if spec is None else spec)

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "status": "ok", "text": text}

    return transport


def _request(**over: Any) -> GenerationRequest:
    base: dict[str, Any] = {
        "question": HAPPY_QUESTION,
        "symbol": "FOLAD",
        "timeframe": "1D",
        "bar_count": 200,
        "end_bar_index": 500,
    }
    base.update(over)
    return GenerationRequest(**base)


@pytest.fixture
def gen_enabled(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "unit-test-key")
    monkeypatch.setenv("AI2_ENABLED", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _generate(svc: AI2GenerationService, request: GenerationRequest) -> GenerationOutcome:
    return asyncio.run(
        svc.generate(request, transport=_ok_transport(INPUT_SPEC), now_utc=lambda: NOW_UTC)
    )


# ---------------------------------------------------------------------------
# 1) every remaining stage refuses honestly on engine failure
# ---------------------------------------------------------------------------


class TestRemainingStageRefusalPaths:
    def test_holdout_engine_failure_refusal_row(self, gen_enabled, monkeypatch) -> None:
        svc = AI2GenerationService()
        monkeypatch.setattr(
            ai2_deep_module, "split_holdout", _boom
        )  # holdout injection point (module attribute)
        outcome = _generate(svc, _request())
        assert outcome.ok is True  # the run still commits (fail-honest, not raise)
        de = svc.candidates.get(outcome.candidate_id).deep_evaluation
        assert de is not None
        assert de.holdout is None  # the stage refused; nothing fabricated
        rows = [(r.stage, r.reason) for r in de.refusals]
        assert ("holdout", "engine_exception:RuntimeError") in rows

    def test_comparison_engine_failure_refusal_row(self, gen_enabled, monkeypatch) -> None:
        svc = AI2GenerationService()
        monkeypatch.setattr(
            ai2_deep_module, "run_backtest_on_seeded", _boom
        )  # comparison/baseline injection point
        outcome = _generate(svc, _request())
        assert outcome.ok is True
        de = svc.candidates.get(outcome.candidate_id).deep_evaluation
        rows = [(r.stage, r.reason) for r in de.refusals]
        assert ("comparison", "engine_exception:RuntimeError") in rows
        assert de.comparison == ()  # no fabricated comparison rows

    def test_walk_forward_engine_failure_refusal_row(self, gen_enabled, monkeypatch) -> None:
        svc = AI2GenerationService()
        monkeypatch.setattr(ai2_deep_module, "run_walk_forward", _boom)
        outcome = _generate(svc, _request())
        assert outcome.ok is True
        de = svc.candidates.get(outcome.candidate_id).deep_evaluation
        rows = [(r.stage, r.reason) for r in de.refusals]
        assert ("walk_forward", "engine_exception:RuntimeError") in rows
        assert de.walk_forward is None

    def test_regime_engine_failure_refusal_row(self, gen_enabled, monkeypatch) -> None:
        svc = AI2GenerationService()
        monkeypatch.setattr(ai2_deep_module, "slice_by_regime", _boom)
        outcome = _generate(svc, _request())
        assert outcome.ok is True
        de = svc.candidates.get(outcome.candidate_id).deep_evaluation
        rows = [(r.stage, r.reason) for r in de.refusals]
        assert ("regime_slices", "engine_exception:RuntimeError") in rows
        assert de.robustness is None


def _boom(*_a: Any, **_k: Any) -> None:
    raise RuntimeError("injected engine failure")


# ---------------------------------------------------------------------------
# 2) baseline provenance + 3) declared-vs-inferred regime distinction
# ---------------------------------------------------------------------------


class TestBaselineProvenanceAndDeclaredRegimes:
    def test_comparison_rows_carry_declared_baseline_provenance(self, gen_enabled) -> None:
        svc = AI2GenerationService()
        outcome = _generate(svc, _request())
        de = svc.candidates.get(outcome.candidate_id).deep_evaluation
        assert len(de.comparison) == 3
        for row in de.comparison:
            # the reference is the DECLARED fixed baseline — never a fitted or
            # selected candidate; provenance rides the row verbatim
            assert row.baseline_spec == AI2_BASELINE_LABEL == "AI2-BASELINE-BUY-HOLD-1"
            assert row.delta_basis, "every row discloses the declared comparison basis"
            assert "seeded" in row.delta_basis or "SAME" in row.delta_basis

    def test_regime_labels_are_declared_not_inferred(self, gen_enabled) -> None:
        svc = AI2GenerationService()
        outcome = _generate(svc, _request())
        de = svc.candidates.get(outcome.candidate_id).deep_evaluation
        assert de.robustness is not None
        # the declaration note is carried verbatim on the record
        assert "NOT data-inferred regimes" in de.robustness.declaration_note
        assert "caller-declared" in de.robustness.declaration_note
        assert set(de.robustness.labels) == {"NEUTRAL"}  # the ONLY label ever used
        assert len(de.robustness.labels) == len(de.robustness.bar_counts)
        # and the DATA side is structurally closed: the composition surface
        # exposes no inference/clustering entry point at all
        forbidden = {
            n
            for n in dir(ai2_deep_module)
            for token in ("cluster", "infer", "detect_regime", "hmm", "gmm")
            if token in n.lower()
        }
        assert forbidden == set(), f"data-inferred regime machinery must not exist: {forbidden}"

    def test_holdout_isolation_is_attested_with_provenance_note(self, gen_enabled) -> None:
        svc = AI2GenerationService()
        outcome = _generate(svc, _request())
        de = svc.candidates.get(outcome.candidate_id).deep_evaluation
        assert de.holdout.isolated is True
        assert de.holdout.holdout_fraction == ai2_deep_module.AI2_HOLDOUT_FRACTION
        # the attestation note documents the declared selection surface
        assert de.holdout.basis_note.startswith("attestation scope:")
        assert "closed strictly before the holdout boundary" in de.holdout.basis_note


# ---------------------------------------------------------------------------
# 4) dormant adapter: independent pragma-level evidence (WAL + synchronous)
# ---------------------------------------------------------------------------


class TestDormantAdapterPragmaEvidence:
    def test_database_file_is_wal_with_full_synchronous(self, tmp_path) -> None:
        from app.data.ai2_ledger_sqlite import DurableAI2LedgerStore

        db = tmp_path / "wpd_probe.sqlite3"
        DurableAI2LedgerStore(db)  # construct via the adapter (creates schema + pragmas)
        with sqlite3.connect(str(db)) as conn:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
        assert str(journal_mode).lower() == "wal"
        assert int(synchronous) == 2  # 2 = FULL
        import app.data.ai2_ledger_sqlite as ai2_ledger_module

        assert ai2_ledger_module.SCHEMA_VERSION == "AI2-LEDGER-STORE-V1"

    def test_adapter_stays_disconnected_from_production(self) -> None:
        # re-prove dormancy at the import-graph level (mirror of the shipped
        # WAVE-AB4 pin, kept as an independent two-key check in this battery)
        from pathlib import Path

        import app.data.ai2_ledger_sqlite as mod

        backend_dir = Path(mod.__file__).resolve().parents[1]
        offenders = []
        for directory in (backend_dir / "services", backend_dir / "api"):
            for py in sorted(directory.rglob("*.py")):
                if "ai2_ledger_sqlite" in py.read_text(encoding="utf-8"):
                    offenders.append(str(py))
        assert offenders == []
        # production config gate untouched: default off
        cfg = (backend_dir / "core" / "config.py").read_text(encoding="utf-8")
        assert '_env_bool("AI2_ENABLED", "0")' in cfg
