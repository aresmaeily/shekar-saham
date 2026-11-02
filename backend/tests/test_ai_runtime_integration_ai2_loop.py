"""AI-2 research-loop E2E integration test — full synthetic session (WP-4/T3).

INTEGRATION scope (composes existing public APIs in-process; nothing new is
wired, nothing existing is modified):

    AI2ResearchLoopRunner  (app.services.ai2_research_loop)
      → AI2Service.run      (app.services.ai2_service; synthetic TEST ONLY
                             transport injected per call — the same seam the
                             existing acceptance tests use)
      → AI2RunLedger        (app.domain.ai2_governance; append-only)
      → EpisodicRunArchive  (app.domain.research_memory; append-only)
      → governed_acceptance (app.domain.ai2_governance)

Governance invariants asserted end-to-end (never weakened):
- AI2_ENABLED stays 0 in the REAL config (the only ``ai2_enabled=True`` here
  is the in-memory SimpleNamespace seam of the existing tests, patched onto
  the service module ONLY for the synthetic-transport path; nothing is
  written to the environment, config, or any file);
- a synthetic shadow run lands as LEDGERED — never COMPLETED — and
  ``governed_acceptance`` refuses it (``run_status_not_completed``);
- episodic artifacts are appended for service-OK runs (executed_shadow
  included, honest LEDGERED label carried) and NEVER for refused runs;
- budget exhaustion refuses further runs with a BUDGET_EXHAUSTED ledger
  record and zero further stage-2 invocations;
- the injected clock/now_utc are the ONLY time sources of the loop module
  (wall-clock reads are patched to raise inside the loop module for the
  duration of the run).

Deterministic throughout: no network, no LLM, no production mutation, no
self-escalation, no purge/expiry.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.ai2_governance import (
    AI2BudgetSpec,
    AI2RunLedger,
    AI2RunRecord,
    governed_acceptance,
)
from app.domain.research_memory import (
    EpisodicRunArchive,
    SemanticLessonStore,
    derive_lesson,
)
from app.domain.research_memory_store import (
    InMemoryResearchMemoryStore,
    verify_integrity,
)
from app.domain.run_governance import RunContext
from app.services import ai2_research_loop as loop_module
from app.services import ai2_service as ai2_module
from app.services.ai2_research_loop import AI2ResearchLoopRunner, AI2ResearchRunInput
from app.services.ai2_service import AI2Request, AI2Service

UTC = timezone.utc
# Far-future fixed instant: guaranteed >= the service's real provenance stamp
# (information_cutoff_utc <= recorded_at_utc must hold on archive appends).
NOW = datetime(2027, 3, 1, 12, 0, 0, tzinfo=UTC)
RUN = "run-ai2-e2e"
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64

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

    def __call__(self) -> float:
        t = self.t
        self.t += self.step
        return t


def _now_utc() -> datetime:
    return NOW


def _valid_transport(payload):
    return {"text": json.dumps(VALID_OUTPUT)}


@pytest.fixture
def _shadow_env(monkeypatch):
    """Synthetic-transport path ONLY (mirrors tests/test_ai2_research_loop.py):
    ai2_enabled=True in in-memory settings + external provider env so the seam
    reaches the injected test transport. No network occurs; the real config
    default AI2_ENABLED=0 is untouched."""
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "unit-test-key")
    monkeypatch.setattr(ai2_module, "get_settings", lambda: SimpleNamespace(ai2_enabled=True))


def _run_input(
    record_id: str,
    sha: str,
    task: str = "analyst",
    **over: Any,
) -> AI2ResearchRunInput:
    base = dict(
        record_id=record_id,
        run_id=RUN,
        policy_version="gov-1",
        task=task,
        request=AI2Request(task=task, symbol="فملی"),
        input_snapshot_sha256=sha,
    )
    base.update(over)
    return AI2ResearchRunInput(**base)


def _runner(
    budget: AI2BudgetSpec,
    archive: EpisodicRunArchive | None,
    clock: FakeClock,
) -> AI2ResearchLoopRunner:
    return AI2ResearchLoopRunner(
        AI2Service(),
        AI2RunLedger(),
        budget,
        archive,
        clock=clock,
        now_utc=_now_utc,
    )


def _context() -> RunContext:
    return RunContext(
        run_id=RUN,
        run_kind="AI2_INTERPRETATION",
        policy_version="gov-1",
        created_at_utc=NOW,
    )


# ---------------------------------------------------------------------------
# E2E synthetic session: candidate generation → duplicate pre-classification →
# budget verdicts → executed shadow run → non-COMPLETED ledger mapping →
# governed acceptance refusal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_synthetic_session_e2e(_shadow_env) -> None:
    """One session: shadow execution, duplicate refusal, repeated-question
    flagging, then budget exhaustion — every stage honest and bounded."""
    clock = FakeClock(step=0.5)
    budget = AI2BudgetSpec(max_provider_invocations=2, max_iterations=8, max_wall_seconds=1800)
    runner = _runner(budget, EpisodicRunArchive(), clock)

    # -- run 1: candidate executes as a SYNTHETIC shadow run ---------------
    transport_calls: list[Any] = []

    def _counting_transport(payload):
        transport_calls.append(payload)
        return {"text": json.dumps(VALID_OUTPUT)}

    r1 = await runner.execute_run(
        _run_input("rec-1", SHA_A), DummyMarketService(), transport=_counting_transport
    )
    assert r1.outcome == "executed_shadow"
    assert r1.ok is True
    assert len(transport_calls) == 1  # exactly one stage-2 provider invocation
    # Non-COMPLETED ledger mapping: executed_shadow → LEDGERED (NEVER COMPLETED)
    assert r1.ledger_status == "LEDGERED"
    assert r1.record is not None and r1.record.status == "LEDGERED"
    assert r1.record.artifact is None  # LEDGERED cannot carry an artifact
    assert r1.execution_label == "SYNTHETIC_OR_PAPER"
    assert "synthetic_shadow_run_never_completed" in r1.record.notes
    # Injected clock is the only duration source
    assert r1.elapsed_wall_seconds == 0.5
    assert r1.record.recorded_at_utc == NOW
    # Governed acceptance CANNOT accept the shadow record
    blocking = governed_acceptance(_context(), r1.record)
    assert "run_status_not_completed" in blocking

    # -- run 2: identical (task, input snapshot) → refused BEFORE execution -
    r2 = await runner.execute_run(
        _run_input("rec-dup", SHA_A), DummyMarketService(), transport=_counting_transport
    )
    assert r2.outcome == "duplicate_refused"
    assert r2.ok is False
    assert r2.duplicate_class == "DUPLICATE_IDENTICAL"
    assert len(transport_calls) == 1  # nothing ran again
    assert r2.record is None  # nothing appended
    assert r2.archived_evidence is False

    # -- run 3: same question, different snapshot → flagged but visible ----
    r3 = await runner.execute_run(
        _run_input("rec-2", SHA_B), DummyMarketService(), transport=_counting_transport
    )
    assert r3.outcome == "executed_shadow"
    assert r3.duplicate_class == "DUPLICATE_REPEATED_QUESTION"
    assert r3.ledger_status == "DUPLICATE_FLAGGED"
    assert len(transport_calls) == 2  # one more stage-2 invocation (budget: 2/2)

    # -- run 4: budget exhausted pre-run; a BUDGET_EXHAUSTED record is filed
    r4 = await runner.execute_run(
        _run_input("rec-3", SHA_C), DummyMarketService(), transport=_counting_transport
    )
    assert r4.outcome == "budget_exhausted"
    assert r4.ok is False
    assert len(transport_calls) == 2  # NO further stage-2 invocation
    assert r4.ledger_status == "BUDGET_EXHAUSTED"
    assert r4.record is not None and r4.record.status == "BUDGET_EXHAUSTED"
    assert "budget_exhausted_pre_run" in r4.record.notes
    assert "no stage-2 invocation was performed" in r4.record.notes
    blocking4 = governed_acceptance(_context(), r4.record)
    assert "run_status_not_completed" in blocking4

    # -- honest session status ----------------------------------------------
    status = runner.loop_status()
    assert status.runs_attempted == 4
    assert status.stage2_invocations_used == 2
    assert status.budget_now == "BUDGET_EXHAUSTED"
    assert status.remaining_provider_invocations == 0
    assert status.records_appended == 3  # rec-1, rec-2, rec-3
    assert status.last_outcome == "budget_exhausted"
    refusal_reasons = [ref.reason for ref in status.refusals]
    assert refusal_reasons == ["duplicate_refused"]

    # -- ledger mapping: NO record ever reached COMPLETED --------------------
    assert all(rec.status != "COMPLETED" for rec in runner.ledger.records)
    assert {rec.status for rec in runner.ledger.records} == {
        "LEDGERED",
        "DUPLICATE_FLAGGED",
        "BUDGET_EXHAUSTED",
    }


@pytest.mark.asyncio
async def test_episodic_artifact_appended_on_ok_runs_never_on_refused(_shadow_env) -> None:
    """Episodic evidence: appended for executed shadow runs (honest LEDGERED
    label carried through), never for refused/failed runs."""
    budget = AI2BudgetSpec(max_provider_invocations=4, max_iterations=8, max_wall_seconds=1800)
    runner = _runner(budget, EpisodicRunArchive(), FakeClock())

    ok = await runner.execute_run(
        _run_input("rec-1", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert ok.archived_evidence is True
    assert runner.archive is not None
    assert len(runner.archive.entries) == 1
    entry = runner.archive.entries[0]
    assert entry.entry_id == "episodic-rec-1"
    assert entry.run_id == RUN
    assert entry.trust_state == "mock"
    assert entry.information_cutoff_utc <= entry.recorded_at_utc
    assert "execution_label=SYNTHETIC_OR_PAPER" in entry.notes
    assert "ledger_status=LEDGERED" in entry.notes

    refused_dup = await runner.execute_run(
        _run_input("rec-dup", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert refused_dup.outcome == "duplicate_refused"
    assert refused_dup.archived_evidence is False
    assert len(runner.archive.entries) == 1  # unchanged

    # A failed-schema run (service ok=False) must not archive either.
    bad_output = {"summary": 5}  # violates AI2Interpretation schema
    failed = await runner.execute_run(
        _run_input("rec-2", SHA_B),
        DummyMarketService(),
        transport=lambda _p: {"text": json.dumps(bad_output)},
    )
    assert failed.outcome == "failed_schema"
    assert failed.ok is False
    assert failed.archived_evidence is False
    assert len(runner.archive.entries) == 1


@pytest.mark.asyncio
async def test_ai2_archive_feeds_deterministic_lesson_curation_and_store(_shadow_env) -> None:
    """Connected edge AI-2 loop → research memory: the runner-appended
    episodic artifact is citable by ``derive_lesson`` (which refuses unknown
    artifacts) and verifiable through the in-memory research-memory store."""
    budget = AI2BudgetSpec(max_provider_invocations=2, max_iterations=4, max_wall_seconds=1800)
    runner = _runner(budget, EpisodicRunArchive(), FakeClock())
    r1 = await runner.execute_run(
        _run_input("rec-1", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert r1.archived_evidence is True and runner.archive is not None

    lesson = derive_lesson(
        runner.archive,
        lesson_id="lesson-ai2-e2e",
        statement="Synthetic shadow runs are ledgered and never governed-accepted.",
        source_artifact_ids=("episodic-rec-1",),
        curated_by="deterministic-curation",
        curation_basis="DETERMINISTIC_RULE",
        at_utc=NOW,
        run_id=RUN,
    )
    # Citing an artifact that the loop never archived is refused.
    with pytest.raises(ValueError, match="lesson_cites_unknown_artifacts"):
        derive_lesson(
            runner.archive,
            lesson_id="lesson-ghost",
            statement="No such artifact.",
            source_artifact_ids=("episodic-ghost",),
            curated_by="deterministic-curation",
            curation_basis="DETERMINISTIC_RULE",
            at_utc=NOW,
        )

    store = InMemoryResearchMemoryStore(
        archive=runner.archive, lessons=SemanticLessonStore().register(lesson)
    )
    report = store.integrity_report()
    assert report.verify_ok is True
    assert report.entry_count == 1

    expected = dict(report.entry_digests)
    assert verify_integrity(store, expected).verify_ok is True
    tampered = verify_integrity(store, {"episodic-rec-1": "f" * 64})
    assert tampered.verify_ok is False
    assert tampered.mismatched_entry_ids == ("episodic-rec-1",)
    assert "digest_mismatch" in tampered.refusal_reasons


# ---------------------------------------------------------------------------
# AI2_ENABLED=0 default gates the loop end-to-end (no self-escalation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_disabled_config_gates_everything_even_with_transport() -> None:
    """With the REAL default settings (AI2_ENABLED=0) the runner refuses every
    run as gated_not_executed — even when a test transport is offered — and
    no provider invocation, ledger artifact, or archive append occurs."""
    calls: list[Any] = []

    def _spy_transport(payload):
        calls.append(payload)
        return {"text": json.dumps(VALID_OUTPUT)}

    budget = AI2BudgetSpec(max_provider_invocations=2, max_iterations=4, max_wall_seconds=1800)
    runner = _runner(budget, EpisodicRunArchive(), FakeClock())
    outcome = await runner.execute_run(
        _run_input("rec-gated", SHA_A), DummyMarketService(), transport=_spy_transport
    )
    assert calls == []  # gate precedes any provider invocation
    assert outcome.outcome == "gated_not_executed"
    assert outcome.ok is False
    assert outcome.ledger_status == "GATED_NOT_EXECUTED"
    assert outcome.record is not None and outcome.record.status == "GATED_NOT_EXECUTED"
    assert outcome.archived_evidence is False
    assert runner.archive is not None and len(runner.archive.entries) == 0
    blocking = governed_acceptance(_context(), outcome.record)
    assert "run_status_not_completed" in blocking


# ---------------------------------------------------------------------------
# Injected clocks are the loop's only time sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_module_uses_only_injected_clocks(_shadow_env, monkeypatch) -> None:
    """Wall-clock reads inside the LOOP module are patched to raise: the run
    completes using the injected FakeClock/_now_utc alone (the service module
    keeps its own provenance stamp; the loop's duration/timestamps are
    deterministic)."""

    def _raise_monotonic():  # pragma: no cover - must never be called
        raise AssertionError("time.monotonic read inside ai2_research_loop")

    class _NoWallDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # pragma: no cover - must never be called
            raise AssertionError("datetime.now read inside ai2_research_loop")

    monkeypatch.setattr(loop_module, "time", SimpleNamespace(monotonic=_raise_monotonic))
    monkeypatch.setattr(loop_module, "datetime", _NoWallDatetime)

    budget = AI2BudgetSpec(max_provider_invocations=1, max_iterations=2, max_wall_seconds=1800)
    runner = _runner(budget, None, FakeClock(step=0.25))
    outcome = await runner.execute_run(
        _run_input("rec-1", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert outcome.outcome == "executed_shadow"
    assert outcome.elapsed_wall_seconds == 0.25
    assert outcome.record is not None
    assert outcome.record.recorded_at_utc == NOW
    assert outcome.result is not None
    assert outcome.result.provenance is not None


# ---------------------------------------------------------------------------
# Gate order: identity binding → duplicate → budget (first refusal wins)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_order_identity_precedes_duplicate_and_budget(_shadow_env) -> None:
    budget = AI2BudgetSpec(max_provider_invocations=1, max_iterations=2, max_wall_seconds=1800)
    runner = _runner(budget, None, FakeClock())
    first = await runner.execute_run(
        _run_input("rec-1", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert first.ok is True  # budget now exhausted (1/1)

    # Mismatched identity + identical duplicate + exhausted budget, all at
    # once: the RunContext identity binding is checked FIRST.
    other_context = RunContext(
        run_id="run-other",
        run_kind="AI2_INTERPRETATION",
        policy_version="gov-1",
        created_at_utc=NOW,
    )
    outcome = await runner.execute_run(
        _run_input("rec-2", SHA_A),
        DummyMarketService(),
        transport=_valid_transport,
        run_context=other_context,
    )
    assert outcome.outcome == "run_context_mismatch"
    assert outcome.refusal_reason == "run_context_mismatch"
    status = runner.loop_status()
    assert status.refusals[-1].reason == "run_context_mismatch"
    assert status.refusals[-1].at_utc == NOW

    # With the MATCHING context, the duplicate gate refuses before the
    # budget gate would (identical pair already ledgered).
    outcome2 = await runner.execute_run(
        _run_input("rec-2", SHA_A),
        DummyMarketService(),
        transport=_valid_transport,
        run_context=_context(),
    )
    assert outcome2.outcome == "duplicate_refused"


# ---------------------------------------------------------------------------
# governed_acceptance: EVERY non-COMPLETED ledger status is refused
# ---------------------------------------------------------------------------


def test_governed_acceptance_refuses_every_non_completed_status() -> None:
    context = _context()
    non_completed = (
        "LEDGERED",
        "DUPLICATE_FLAGGED",
        "BUDGET_EXHAUSTED",
        "INVALIDATED",
        "GATED_NOT_EXECUTED",
        "FAILED",
    )
    for status in non_completed:
        record = AI2RunRecord(
            record_id=f"rec-{status.lower()}",
            run_id=RUN,
            run_kind="AI2_INTERPRETATION",
            policy_version="gov-1",
            task="analyst",
            input_snapshot_sha256=SHA_D,
            trust_state="mock",
            approval_state="NOT_REQUIRED",
            status=status,
            recorded_at_utc=NOW,
        )
        blocking = governed_acceptance(context, record)
        assert "run_status_not_completed" in blocking, status

    # And COMPLETED is un-mintable without an evidence artifact (validator),
    # so a shadow session structurally cannot produce an acceptable record.
    with pytest.raises(ValidationError, match="completed_run_requires_evidence_artifact"):
        AI2RunRecord(
            record_id="rec-completed",
            run_id=RUN,
            run_kind="AI2_INTERPRETATION",
            policy_version="gov-1",
            task="analyst",
            input_snapshot_sha256=SHA_D,
            trust_state="mock",
            approval_state="NOT_REQUIRED",
            status="COMPLETED",
            recorded_at_utc=NOW,
        )
