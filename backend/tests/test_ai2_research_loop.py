"""AI-2 synthetic/paper research-loop runner tests (mock-based, no network).

Mirrors the conventions of tests/test_ai2_service.py: in-memory
``SimpleNamespace`` settings are patched onto the service module ONLY to
exercise the synthetic-transport path (AI2_ENABLED invariant untouched —
nothing is written to the environment or to any committed file); the
synthetic transport is injected per-call; deterministic clock/now_utc
implementations are injected into the runner (never time.time).

Every refusal path has a test: duplicate-identical refusal, repeated-question
flagging, budget exhaustion (invocations AND wall seconds), run-context
mismatch, ledger record-id conflict, runner internal error containment —
plus the explicit executed_shadow → LEDGERED mapping and the
governed_acceptance refusal of the shadow record.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.domain.ai2_governance import (
    AI2BudgetSpec,
    AI2RunLedger,
    governed_acceptance,
)
from app.domain.research_memory import EpisodicRunArchive
from app.domain.run_governance import RunContext
from app.services import ai2_service as ai2_module
from app.services.ai2_research_loop import (
    AI2ResearchLoopRunner,
    AI2ResearchRunInput,
    OUTCOME_STATUS_MAP,
    append_record_idempotent,
)
from app.services.ai2_service import AI2Request, AI2Service

UTC = timezone.utc
# Far-future fixed instant: guaranteed >= the service's real provenance stamp
# (information_cutoff_utc <= recorded_at_utc must hold on archive appends).
NOW = datetime(2027, 1, 1, 12, 0, 0, tzinfo=UTC)
RUN = "run-loop-1"
SHA_A = "a" * 64
SHA_B = "b" * 64
BUDGET = AI2BudgetSpec(max_provider_invocations=3, max_iterations=8, max_wall_seconds=1800)

VALID_OUTPUT = {
    "summary": "Structured second-stage interpretation of deterministic context.",
    "observations": ["Entry score is elevated."],
    "risks": ["Data trust is not independently verified."],
    "confidence": 0.42,
}


class DummyMarketService:
    """Same convention as tests/test_ai2_service.py DummyMarketService."""

    def __init__(self, trust_state: str = "mock"):
        self._data_trust = {
            "state": trust_state,
            "trust_level": "synthetic",
            "source": "mock_fallback",
            "provider": "mock_fallback",
            "is_live": False,
            "live_verified": False,
            "is_generated": True,
            "warning": f"{trust_state.upper()} data",
        }

    async def get_analysis(self, force=False):
        return None

    def status(self):
        return {"source": "mock_fallback", "trust_level": "synthetic", "symbol_count": 1}

    def data_trust_context(self):
        return self._data_trust

    def get_symbol(self, symbol):
        return {
            "snapshot": {"l18": symbol, "pl": 1000, "plp": -1.5},
            "metrics": {"entry_score": 75},
            "data_trust": self._data_trust,
        }

    def run_user_filter(self, expr, limit=10):
        return {"ok": True, "count": 1, "rows": [], "data_trust": self._data_trust}


class FakeClock:
    """Deterministic injected clock (durations only; never time.time)."""

    def __init__(self, start: float = 1000.0, step: float = 0.0):
        self.t = start
        self.step = step
        self.calls = 0

    def __call__(self) -> float:
        t = self.t
        self.calls += 1
        self.t += self.step
        return t


def _now_utc() -> datetime:
    return NOW


def _valid_transport(payload):
    return {"text": json.dumps(VALID_OUTPUT)}


@pytest.fixture
def _shadow_env(monkeypatch):
    """Synthetic-transport path ONLY: ai2_enabled=True in-memory settings +
    external provider env so the seam reaches the injected test transport
    (no network occurs — exactly mirrors test_ai2_service.py)."""
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "unit-test-key")
    monkeypatch.setattr(ai2_module, "get_settings", lambda: SimpleNamespace(ai2_enabled=True))


@pytest.fixture
def _disabled_env(monkeypatch):
    monkeypatch.setattr(ai2_module, "get_settings", lambda: SimpleNamespace(ai2_enabled=False))


def _run_input(
    record_id: str = "rec-1",
    run_id: str = RUN,
    sha: str = SHA_A,
    task: str = "analyst",
    **over: Any,
) -> AI2ResearchRunInput:
    base = dict(
        record_id=record_id,
        run_id=run_id,
        policy_version="gov-1",
        task=task,
        request=AI2Request(task=task, symbol="فملی"),
        input_snapshot_sha256=sha,
    )
    base.update(over)
    return AI2ResearchRunInput(**base)


def _runner(
    ledger: AI2RunLedger | None = None,
    budget: AI2BudgetSpec = BUDGET,
    archive: EpisodicRunArchive | None = None,
    clock: FakeClock | None = None,
) -> AI2ResearchLoopRunner:
    return AI2ResearchLoopRunner(
        AI2Service(),
        ledger if ledger is not None else AI2RunLedger(),
        budget,
        archive,
        clock=clock if clock is not None else FakeClock(),
        now_utc=_now_utc,
    )


def _context(run_id: str = RUN) -> RunContext:
    return RunContext(
        run_id=run_id,
        run_kind="AI2_INTERPRETATION",
        policy_version="gov-1",
        created_at_utc=NOW,
    )


# ---------------------------------------------------------------------------
# Mapping table + executed_shadow invariant
# ---------------------------------------------------------------------------


def test_outcome_status_map_pins_shadow_to_non_completed() -> None:
    """The mapping table is explicit: executed_shadow is NEVER COMPLETED."""
    assert OUTCOME_STATUS_MAP["executed_shadow"] == "LEDGERED"
    assert OUTCOME_STATUS_MAP["executed"] == "COMPLETED"
    assert OUTCOME_STATUS_MAP["failed_provider"] == "FAILED"
    assert OUTCOME_STATUS_MAP["failed_schema"] == "FAILED"
    assert OUTCOME_STATUS_MAP["gated_not_executed"] == "GATED_NOT_EXECUTED"
    # governed_acceptance accepts ONLY COMPLETED — so the shadow row is
    # structurally un-acceptable.
    assert OUTCOME_STATUS_MAP["executed_shadow"] != "COMPLETED"


@pytest.mark.asyncio
async def test_shadow_run_maps_to_ledgered_never_completed(_shadow_env) -> None:
    runner = _runner()
    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport)
    assert outcome.outcome == "executed_shadow"
    assert outcome.ok is True
    assert outcome.ledger_status == "LEDGERED"
    assert outcome.record is not None
    assert outcome.record.status == "LEDGERED"
    assert outcome.record.artifact is None  # LEDGERED cannot carry an artifact
    assert outcome.execution_label == "SYNTHETIC_OR_PAPER"
    assert "synthetic_shadow_run_never_completed" in outcome.record.notes
    assert runner.loop_status().stage2_invocations_used == 1


@pytest.mark.asyncio
async def test_governed_acceptance_refuses_shadow_record(_shadow_env) -> None:
    runner = _runner()
    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport)
    assert outcome.record is not None
    blocking = governed_acceptance(_context(), outcome.record)
    assert "run_status_not_completed" in blocking


# ---------------------------------------------------------------------------
# Refusal paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_identical_refused_before_execution(_shadow_env) -> None:
    runner = _runner()
    first = await runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport)
    assert first.ok is True
    ledger_size_after_first = len(runner.ledger.records)

    calls: list[Any] = []

    def _spy_transport(payload):
        calls.append(payload)
        return {"text": json.dumps(VALID_OUTPUT)}

    second = await runner.execute_run(
        _run_input(record_id="rec-2"), DummyMarketService(), transport=_spy_transport
    )
    assert second.outcome == "duplicate_refused"
    assert second.ok is False
    assert second.record is None
    assert second.duplicate_class == "DUPLICATE_IDENTICAL"
    assert calls == []  # nothing was executed
    assert len(runner.ledger.records) == ledger_size_after_first  # ledger unchanged
    status = runner.loop_status()
    assert status.stage2_invocations_used == 1  # second attempt consumed nothing
    assert [r.reason for r in status.refusals] == ["duplicate_refused"]


@pytest.mark.asyncio
async def test_duplicate_repeated_question_runs_and_record_is_flagged(_shadow_env) -> None:
    runner = _runner()
    first = await runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport)
    assert first.duplicate_class == "NEW"
    second = await runner.execute_run(
        _run_input(record_id="rec-2", sha=SHA_B), DummyMarketService(), transport=_valid_transport
    )
    # Allowed (same question task, different input snapshot), but visible.
    assert second.duplicate_class == "DUPLICATE_REPEATED_QUESTION"
    assert second.ok is True
    assert second.outcome == "executed_shadow"
    assert second.ledger_status == "DUPLICATE_FLAGGED"
    assert second.record is not None
    assert second.record.status == "DUPLICATE_FLAGGED"
    assert second.record.artifact is None
    assert "outcome=executed_shadow" in second.record.notes  # underlying outcome visible
    # governed_acceptance refuses the flagged record even though the service ran OK.
    blocking = governed_acceptance(_context(), second.record)
    assert "run_status_not_completed" in blocking


@pytest.mark.asyncio
async def test_budget_exhaustion_after_max_invocations(_shadow_env) -> None:
    # Hand-verified budget math: max_provider_invocations=2 → runs 1 and 2
    # execute (prechecks see usage 0 and 1), run 3's precheck sees usage 2
    # (2 >= 2) → refused with a BUDGET_EXHAUSTED record, no invocation.
    budget = AI2BudgetSpec(max_provider_invocations=2, max_iterations=8, max_wall_seconds=1800)
    runner = _runner(budget=budget)
    r1 = await runner.execute_run(_run_input(record_id="rec-1"), DummyMarketService(), transport=_valid_transport)
    r2 = await runner.execute_run(_run_input(record_id="rec-2", sha=SHA_B), DummyMarketService(), transport=_valid_transport)
    assert (r1.ok, r2.ok) == (True, True)
    assert runner.loop_status().stage2_invocations_used == 2

    r3 = await runner.execute_run(
        _run_input(record_id="rec-3", sha="c" * 64), DummyMarketService(), transport=_valid_transport
    )
    assert r3.outcome == "budget_exhausted"
    assert r3.ok is False
    assert r3.ledger_status == "BUDGET_EXHAUSTED"
    assert r3.record is not None
    assert r3.record.status == "BUDGET_EXHAUSTED"
    assert "budget_exhausted_pre_run" in r3.record.notes
    assert runner.loop_status().stage2_invocations_used == 2  # unchanged
    assert runner.loop_status().budget_now == "BUDGET_EXHAUSTED"


@pytest.mark.asyncio
async def test_budget_exhaustion_by_wall_seconds(_shadow_env) -> None:
    # max_wall_seconds=100; the fake clock advances 60s per run:
    # run 1 precheck 0.0 < 100 → runs (usage 60); run 2 precheck 60 < 100 →
    # runs (usage 120); run 3 precheck 120 >= 100 → refused.
    budget = AI2BudgetSpec(max_provider_invocations=8, max_iterations=8, max_wall_seconds=100)
    runner = _runner(budget=budget, clock=FakeClock(step=60.0))
    r1 = await runner.execute_run(_run_input(record_id="rec-1"), DummyMarketService(), transport=_valid_transport)
    r2 = await runner.execute_run(_run_input(record_id="rec-2", sha=SHA_B), DummyMarketService(), transport=_valid_transport)
    assert (r1.ok, r2.ok) == (True, True)
    r3 = await runner.execute_run(
        _run_input(record_id="rec-3", sha="c" * 64), DummyMarketService(), transport=_valid_transport
    )
    assert r3.outcome == "budget_exhausted"
    assert runner.loop_status().wall_seconds_used == 120.0


@pytest.mark.asyncio
async def test_run_context_mismatch_refused(_shadow_env) -> None:
    runner = _runner()
    outcome = await runner.execute_run(
        _run_input(run_id="run-other"),
        DummyMarketService(),
        transport=_valid_transport,
        run_context=_context(RUN),
    )
    assert outcome.outcome == "run_context_mismatch"
    assert outcome.refusal_reason == "run_context_mismatch"
    assert outcome.record is None
    assert runner.loop_status().stage2_invocations_used == 0
    assert len(runner.ledger.records) == 0


@pytest.mark.asyncio
async def test_run_context_binding_accepted_when_matching(_shadow_env) -> None:
    runner = _runner()
    outcome = await runner.execute_run(
        _run_input(),
        DummyMarketService(),
        transport=_valid_transport,
        run_context=_context(RUN),
    )
    assert outcome.ok is True
    assert outcome.record is not None
    assert outcome.record.run_id == RUN


@pytest.mark.asyncio
async def test_ledger_record_id_conflict_is_contained(_shadow_env) -> None:
    runner = _runner()
    first = await runner.execute_run(_run_input(record_id="rec-1"), DummyMarketService(), transport=_valid_transport)
    assert first.ok is True
    # Same record_id, different content (different input snapshot) → the
    # ledger would conflict; the runner refuses instead of raising.
    second = await runner.execute_run(
        _run_input(record_id="rec-1", sha=SHA_B), DummyMarketService(), transport=_valid_transport
    )
    assert second.outcome == "ledger_record_conflict"
    assert second.refusal_reason == "ledger_record_conflict"
    assert second.record is None
    assert len(runner.ledger.records) == 1  # unchanged
    assert runner.loop_status().records_appended == 1


# ---------------------------------------------------------------------------
# Failure mapping + recovery decisions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_gate_records_gated_not_executed_and_escalates(_disabled_env) -> None:
    runner = _runner()

    def _spy_transport(payload):  # pragma: no cover — must never be called
        raise AssertionError("transport must not run while AI2 disabled")

    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=_spy_transport)
    assert outcome.outcome == "gated_not_executed"
    assert outcome.ok is False
    assert outcome.ledger_status == "GATED_NOT_EXECUTED"
    assert outcome.record is not None
    assert outcome.record.status == "GATED_NOT_EXECUTED"
    assert outcome.execution_label == "SYNTHETIC_OR_PAPER"  # never LIVE
    # Deterministic-gate refusal → never retried (fail-closed).
    assert outcome.recovery == "ESCALATE_FAIL_CLOSED"


@pytest.mark.asyncio
async def test_provider_failure_recovery_math_is_exact(_shadow_env) -> None:
    # max_provider_invocations=3. Each failed run increments failed count:
    # after run 1: recovery_decision(failed=1) → 1+1 <= 3 → RETRY_WITHIN_BUDGET
    # after run 2: failed=2 → 2+1 <= 3 → RETRY_WITHIN_BUDGET
    # after run 3: failed=3 → 3+1  > 3 → ESCALATE_FAIL_CLOSED
    def _timeout_transport(payload):
        raise TimeoutError("timeout")

    runner = _runner()
    r1 = await runner.execute_run(_run_input(record_id="rec-1"), DummyMarketService(), transport=_timeout_transport)
    assert r1.outcome == "failed_provider"
    assert r1.ledger_status == "FAILED"
    assert r1.recovery == "RETRY_WITHIN_BUDGET"
    r2 = await runner.execute_run(_run_input(record_id="rec-2", sha=SHA_B), DummyMarketService(), transport=_timeout_transport)
    assert r2.recovery == "RETRY_WITHIN_BUDGET"
    r3 = await runner.execute_run(
        _run_input(record_id="rec-3", sha="c" * 64), DummyMarketService(), transport=_timeout_transport
    )
    assert r3.recovery == "ESCALATE_FAIL_CLOSED"
    status = runner.loop_status()
    assert status.stage2_invocations_used == 3
    assert status.budget_now == "BUDGET_EXHAUSTED"  # 3 >= max_provider_invocations


@pytest.mark.asyncio
async def test_runner_internal_error_is_contained(_shadow_env, monkeypatch) -> None:
    runner = _runner()

    async def _boom(request, market_service, *, transport=None):
        raise RuntimeError("synthetic internal fault")

    monkeypatch.setattr(runner._service, "run", _boom)
    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport)
    assert outcome.outcome == "runner_error"
    assert outcome.ok is False
    assert outcome.ledger_status == "FAILED"
    assert "runner_internal_error:RuntimeError" in (outcome.record.notes if outcome.record else "")
    assert outcome.recovery == "ESCALATE_FAIL_CLOSED"
    assert runner.loop_status().stage2_invocations_used == 1  # attempt accounted


@pytest.mark.asyncio
async def test_cancellation_propagates_and_accounting_stays_honest(_shadow_env, monkeypatch) -> None:
    runner = _runner()

    async def _slow(request, market_service, *, transport=None):
        await asyncio.sleep(5)
        raise AssertionError("must be cancelled")

    monkeypatch.setattr(runner._service, "run", _slow)
    task = asyncio.ensure_future(runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    status = runner.loop_status()
    # The cancelled attempt consumed nothing (no record, no invocation
    # accounted — the mapping never observed an outcome).
    assert status.stage2_invocations_used == 0
    assert status.runs_attempted == 1
    assert len(runner.ledger.records) == 0


# ---------------------------------------------------------------------------
# Clock discipline + archive composition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wall_time_measured_only_by_injected_clock(_shadow_env) -> None:
    clock = FakeClock(start=500.0, step=2.5)
    runner = _runner(clock=clock)
    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport)
    # Exactly two clock reads bracket the invocation: 2.5 elapsed, no more.
    assert outcome.elapsed_wall_seconds == pytest.approx(2.5)
    assert runner.loop_status().wall_seconds_used == pytest.approx(2.5)
    assert clock.calls >= 2


@pytest.mark.asyncio
async def test_archive_receives_synthetic_labeled_evidence(_shadow_env) -> None:
    runner = _runner(archive=EpisodicRunArchive())
    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport)
    assert outcome.archived_evidence is True
    # Appends produce NEW immutable archive instances; the runner adopts each
    # new instance (visible via the runner's current archive view).
    archive = runner.archive
    assert archive is not None
    assert len(archive.entries) == 1
    entry = archive.entries[0]
    assert entry.entry_id == f"episodic-{outcome.record.record_id}"
    assert entry.run_id == RUN
    assert "SYNTHETIC_OR_PAPER" in entry.notes  # synthetic/paper label carried through
    assert entry.trust_state == "mock"  # observed trust from the service provenance
    assert entry.recorded_at_utc == NOW  # injected now_utc
    # Information cutoff comes from the result provenance (≤ recorded instant).
    assert entry.information_cutoff_utc <= entry.recorded_at_utc
    assert outcome.record.artifact is None  # ledger record stays artifact-free


@pytest.mark.asyncio
async def test_archive_not_appended_for_gated_outcome(_disabled_env) -> None:
    runner = _runner(archive=EpisodicRunArchive())
    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=None)
    assert outcome.ok is False
    assert outcome.archived_evidence is False
    assert runner.archive is not None
    assert len(runner.archive.entries) == 0


@pytest.mark.asyncio
async def test_archive_append_conflict_is_refused_not_raised(_shadow_env) -> None:
    # Pre-seed the archive with a conflicting entry for the same entry_id.
    from app.domain.research_memory import EpisodicRunArtifact
    from app.domain.run_governance import ArtifactRef

    conflicting = EpisodicRunArtifact(
        entry_id="episodic-rec-1",
        run_id=RUN,
        run_kind="AI2_INTERPRETATION",
        artifact=ArtifactRef(artifact_id="other", kind="x", ref="artifact://other"),
        input_snapshot_sha256=SHA_A,
        trust_state="mock",
        policy_version="gov-1",
        information_cutoff_utc=NOW,
        recorded_at_utc=NOW,
    )
    runner = _runner(archive=EpisodicRunArchive((conflicting,)))
    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=_valid_transport)
    assert outcome.ok is True  # the run itself succeeded
    assert outcome.archived_evidence is False
    assert runner.archive is not None
    assert len(runner.archive.entries) == 1  # unchanged (still the seed only)
    assert [r.reason for r in runner.loop_status().refusals] == ["archive_append_refused"]


# ---------------------------------------------------------------------------
# Ledger idempotency helper + honest status + runner hygiene
# ---------------------------------------------------------------------------


def test_append_record_idempotent_helper() -> None:
    """Pure helper: append / byte-identical no-op / conflict refusal."""
    from app.domain.ai2_governance import AI2RunRecord

    ledger = AI2RunLedger()

    def record(record_id: str, sha: str, notes: str = "n1") -> AI2RunRecord:
        return AI2RunRecord(
            record_id=record_id,
            run_id=RUN,
            run_kind="AI2_INTERPRETATION",
            policy_version="gov-1",
            task="analyst",
            input_snapshot_sha256=sha,
            trust_state="mock",
            approval_state="NOT_REQUIRED",
            status="LEDGERED",
            recorded_at_utc=NOW,
            notes=notes,
        )

    ledger2, appended, conflict = append_record_idempotent(ledger, record("r1", SHA_A))
    assert appended is True and conflict is False and len(ledger2.records) == 1
    # Byte-identical re-append → idempotent no-op.
    ledger3, appended, conflict = append_record_idempotent(ledger2, record("r1", SHA_A))
    assert appended is True and conflict is False and ledger3 is ledger2
    # Conflicting reuse → refused, unchanged.
    ledger4, appended, conflict = append_record_idempotent(ledger3, record("r1", SHA_B))
    assert appended is False and conflict is True and ledger4 is ledger3


@pytest.mark.asyncio
async def test_loop_status_is_honest_across_mixed_history(_shadow_env) -> None:
    runner = _runner()
    await runner.execute_run(_run_input(record_id="rec-1"), DummyMarketService(), transport=_valid_transport)
    await runner.execute_run(_run_input(record_id="rec-2", sha=SHA_B), DummyMarketService(), transport=_valid_transport)
    refused = await runner.execute_run(_run_input(record_id="rec-3"), DummyMarketService(), transport=_valid_transport)
    assert refused.outcome == "duplicate_refused"
    status = runner.loop_status()
    assert status.runs_attempted == 3
    assert status.stage2_invocations_used == 2
    assert status.iterations_used == 2
    assert status.remaining_provider_invocations == 1
    assert status.budget_now == "WITHIN_BUDGET"
    assert status.ledger_size == 2
    assert status.records_appended == 2
    assert [r.reason for r in status.refusals] == ["duplicate_refused"]
    assert status.last_outcome == "duplicate_refused"


@pytest.mark.asyncio
async def test_runner_never_enables_ai2_or_touches_environment(_disabled_env) -> None:
    """With the REAL global settings (AI2_ENABLED=0, unpatched env), the
    runner composes the service honestly: the run is gated, nothing executes,
    and no setting/env/transport is mutated by the runner itself."""
    import app.services.ai2_research_loop as loop_module

    runner = _runner()
    outcome = await runner.execute_run(_run_input(), DummyMarketService(), transport=None)
    assert outcome.outcome == "gated_not_executed"
    # Code-level hygiene pins (AST — docstring prose is excluded): the runner
    # never calls time.time, never touches os.environ, never enables AI-2.
    import ast
    import inspect

    source = inspect.getsource(loop_module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = ast.unparse(node.func)
            assert fn != "time.time", f"forbidden clock read: {fn}"
            assert "environ" not in fn, f"forbidden env access: {fn}"
        if isinstance(node, ast.Attribute):
            assert node.attr != "environ", "forbidden os.environ access"
    assert "AI2_ENABLED=1" not in source  # the runner never enables AI-2
