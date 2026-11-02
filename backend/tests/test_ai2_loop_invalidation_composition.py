"""AI-2 loop-level invalidation/recovery composition tests (WS5-T1).

Scope (authorized by the master audit — "AI-2 invalidation/recovery surface
tests at loop level ... loop-level invalidation composition tests could be
added additively (no wiring)"): this file ONLY composes existing public
surfaces — no production file, no existing test, and no wiring is touched:

    AI2ResearchLoopRunner.execute_run / loop_status  (app.services.ai2_research_loop)
      → invalidates / AI2InvalidationRule            (app.domain.ai2_governance)
      → recovery_decision                            (app.domain.ai2_governance)
      → classify_duplicate / AI2RunLedger            (app.domain.ai2_governance)
      → governed_acceptance                          (app.domain.ai2_governance)

What is pinned (composition of already-tested units, at the loop level):
1. A loop-produced outcome (a stored ledger record with its production trust
   state and dataset version) feeds ``invalidates()``: a later observation
   that degrades trust below the production level fires TRUST_STATE_CHANGED +
   TRUST_DOWNGRADED, the fired codes mint a valid ``AI2InvalidationRule``, and
   the label lands as a NEW append-only INVALIDATED ledger record while the
   original stays byte-identical. A result whose production trust still holds
   fires nothing — and the validator itself refuses to mint a vacuous
   (empty-reason) rule for it.
2. ``AI2InvalidationRule`` validation refusals (empty reasons, duplicate
   codes, unknown codes, unnamed declarer, frozen label).
3. ``recovery_decision`` composed directly against loop-shaped inputs: the
   loop's failure outcome labels (runner_error, gated_not_executed,
   failed_provider within/at the invocation ceiling, budget_exhausted,
   duplicate_refused) map onto the documented recovery classes
   deterministically.
4. State-machine honesty: an invalidated prior result can NEVER be laundered
   into an accepted outcome through duplicate reuse — the identical
   (task, snapshot) pair is refused BEFORE execution, a re-asked question
   lands DUPLICATE_FLAGGED (which can never carry an artifact, hence never
   COMPLETED), and ``governed_acceptance`` refuses the INVALIDATED label.
5. The loop's no-observation trust sentinel ("unobserved") — an unknown
   string in the canonical coarse trust map — composes strictly BELOW every
   named trust state in ``invalidates()`` (documented fail-closed divergence,
   D-16-3 sub-choice iii-B), on real loop outcome labels.

Determinism: synthetic data only; injected FakeClock and a fixed far-future
now_utc; no network (conftest.py pins DATA_SOURCE=mock); the only waits are
the loop's own awaits. AI2_ENABLED stays 0 in the REAL config — the
``_shadow_env`` seam is the same in-memory SimpleNamespace patch the existing
loop tests use, never a settings/environment write.
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
    AI2InvalidationRule,
    AI2RunLedger,
    AI2RunRecord,
    classify_duplicate,
    governed_acceptance,
    invalidates,
    recovery_decision,
)
from app.domain.run_governance import RunContext
from app.services import ai2_service as ai2_module
from app.services.ai2_research_loop import AI2ResearchLoopRunner, AI2ResearchRunInput
from app.services.ai2_service import AI2Request, AI2Service

UTC = timezone.utc
# Far-future fixed instant (same discipline as tests/test_ai2_research_loop.py):
# deterministic, and guaranteed >= any service provenance stamp.
NOW = datetime(2027, 2, 1, 12, 0, 0, tzinfo=UTC)
RUN = "run-ai2-inval-compose"
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
DS_V1 = "ds-2026-10"
DS_V2 = "ds-2026-11"
BUDGET = AI2BudgetSpec(max_provider_invocations=3, max_iterations=8, max_wall_seconds=1800)
DECLARER = "deterministic-rule:trust-watch"

VALID_OUTPUT = {
    "summary": "Structured second-stage interpretation of deterministic context.",
    "observations": ["Entry score is elevated."],
    "risks": ["Data trust is not independently verified."],
    "confidence": 0.42,
}


class DummyMarketService:
    """Same convention as tests/test_ai2_research_loop.py DummyMarketService."""

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

    async def get_analysis(self, force: bool = False):
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

    def run_user_filter(self, expr, limit: int = 10):
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


def _timeout_transport(payload):
    raise TimeoutError("synthetic provider timeout")


@pytest.fixture
def _shadow_env(monkeypatch):
    """Synthetic-transport path ONLY (mirrors tests/test_ai2_research_loop.py):
    in-memory ai2_enabled=True settings + external provider env so the seam
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
        dataset_version=DS_V1,
    )
    base.update(over)
    return AI2ResearchRunInput(**base)  # type: ignore[arg-type]


def _runner(
    service: AI2Service | None = None,
    ledger: AI2RunLedger | None = None,
    budget: AI2BudgetSpec = BUDGET,
    clock: FakeClock | None = None,
) -> AI2ResearchLoopRunner:
    return AI2ResearchLoopRunner(
        service if service is not None else AI2Service(),
        ledger if ledger is not None else AI2RunLedger(),
        budget,
        None,
        clock=clock if clock is not None else FakeClock(),
        now_utc=_now_utc,
    )


def _context() -> RunContext:
    return RunContext(
        run_id=RUN,
        run_kind="AI2_INTERPRETATION",
        policy_version="gov-1",
        created_at_utc=NOW,
    )


def _invalidation_label(
    original: AI2RunRecord,
    reason_codes: tuple[str, ...],
    *,
    observed_trust_state: str,
    observed_dataset_version: str | None,
) -> tuple[AI2InvalidationRule, AI2RunRecord]:
    """Compose the invalidation LABEL exactly as the governance surface
    prescribes: a validated ``AI2InvalidationRule`` carrying the fired reason
    codes, plus a NEW append-only INVALIDATED ledger record binding the same
    run identity (invalidation is never a rewrite or a deletion — the ledger
    keeps the original record as immutable history)."""
    rule = AI2InvalidationRule(
        reason_codes=reason_codes,  # type: ignore[arg-type]
        declared_by=DECLARER,
        declared_at_utc=NOW,
    )
    successor = AI2RunRecord(
        record_id=f"{original.record_id}-invalidated",
        run_id=original.run_id,
        run_kind=original.run_kind,
        policy_version=original.policy_version,
        task=original.task,
        input_snapshot_sha256=original.input_snapshot_sha256,
        trust_state=observed_trust_state,
        dataset_version=observed_dataset_version,
        approval_state=original.approval_state,
        status="INVALIDATED",
        recorded_at_utc=NOW,
        notes=(
            f"invalidation_of={original.record_id}; reasons={','.join(reason_codes)}; "
            "append-only label — the original record remains immutable history"
        ),
    )
    return rule, successor


# ---------------------------------------------------------------------------
# 1. Loop outcome → invalidates() → AI2InvalidationRule → INVALIDATED label
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stored_result_downgraded_below_production_trust_is_invalidated(
    _shadow_env,
) -> None:
    """A loop-produced shadow outcome stored under production trust "stale"
    is later observed under "mock" — a strictly lower canonical coarse trust
    level (live > mixed/stale/unavailable > mock/synthetic). The fired codes
    mint a valid AI2InvalidationRule and the label lands as a NEW INVALIDATED
    ledger record; the original record stays byte-identical and the
    invalidated label itself is structurally un-acceptable."""
    runner = _runner()
    outcome = await runner.execute_run(
        _run_input("rec-1", SHA_A),
        DummyMarketService(trust_state="stale"),
        transport=_valid_transport,
    )
    assert outcome.ok is True
    assert outcome.outcome == "executed_shadow"
    assert outcome.record is not None
    stored = outcome.record
    assert stored.status == "LEDGERED"
    assert stored.trust_state == "stale"  # production trust carried on the record
    assert stored.dataset_version == DS_V1

    # Later observation point: same dataset, degraded trust.
    reasons = invalidates(stored.trust_state, "mock", stored.dataset_version, DS_V1)
    assert reasons == ("TRUST_STATE_CHANGED", "TRUST_DOWNGRADED")

    rule, successor = _invalidation_label(
        stored, reasons, observed_trust_state="mock", observed_dataset_version=DS_V1
    )
    assert rule.reason_codes == reasons
    assert rule.declared_by == DECLARER
    ledger = runner.ledger.append(successor)
    assert len(ledger.records) == 2
    assert ledger.get(stored.record_id) == stored  # original untouched
    invalidated = ledger.get(successor.record_id)
    assert invalidated is not None and invalidated.status == "INVALIDATED"
    # Fail-closed status consultation: only COMPLETED has acceptable outputs.
    assert governed_acceptance(_context(), invalidated) == ("run_status_not_completed",)


@pytest.mark.asyncio
async def test_result_at_held_trust_is_not_invalidated(_shadow_env) -> None:
    """Counter-case: the same production trust is still observed at the later
    point — ``invalidates()`` returns NO reason codes for the stored loop
    record, and the validator itself refuses to mint a vacuous (empty-reason)
    invalidation rule for the still-valid result. Same-canonical-level trust
    changes are changes, never downgrades; no INVALIDATED successor exists."""
    runner = _runner()
    outcome = await runner.execute_run(
        _run_input("rec-1", SHA_A),
        DummyMarketService(trust_state="stale"),
        transport=_valid_transport,
    )
    assert outcome.record is not None
    stored = outcome.record
    assert stored.trust_state == "stale"

    assert invalidates(stored.trust_state, "stale", stored.dataset_version, DS_V1) == ()
    # The empty evaluation cannot mint a rule: the empty-reasons refusal is
    # the documented guard against vacuous invalidation.
    with pytest.raises(ValidationError, match="invalidation_requires_reason"):
        AI2InvalidationRule(reason_codes=(), declared_by=DECLARER, declared_at_utc=NOW)
    # Same canonical coarse level (stale ≡ mixed ≡ unavailable; mock ≡
    # synthetic): a change fires TRUST_STATE_CHANGED only — never a downgrade.
    assert invalidates("stale", "mixed", None, None) == ("TRUST_STATE_CHANGED",)
    assert invalidates("mock", "synthetic", None, None) == ("TRUST_STATE_CHANGED",)
    # The ledger holds exactly the still-valid stored record.
    assert len(runner.ledger.records) == 1
    assert all(rec.status != "INVALIDATED" for rec in runner.ledger.records)


# ---------------------------------------------------------------------------
# 2. AI2InvalidationRule validation refusals
# ---------------------------------------------------------------------------


def test_invalidation_rule_validation_refusals() -> None:
    """Documented AI2InvalidationRule validators, exercised with the loop's
    reason-code vocabulary: empty reasons, duplicate codes, unknown codes, an
    unnamed declarer, and the frozen (immutable) label contract."""
    with pytest.raises(ValidationError, match="invalidation_requires_reason"):
        AI2InvalidationRule(reason_codes=(), declared_by=DECLARER, declared_at_utc=NOW)
    with pytest.raises(ValidationError, match="reason_codes_duplicates"):
        AI2InvalidationRule(
            reason_codes=("TRUST_STATE_CHANGED", "TRUST_STATE_CHANGED"),
            declared_by=DECLARER,
            declared_at_utc=NOW,
        )
    with pytest.raises(ValidationError):
        AI2InvalidationRule(
            reason_codes=("NOT_A_DOCUMENTED_REASON",),  # type: ignore[list-item]
            declared_by=DECLARER,
            declared_at_utc=NOW,
        )
    with pytest.raises(ValidationError):
        AI2InvalidationRule(
            reason_codes=("TRUST_DOWNGRADED",), declared_by="", declared_at_utc=NOW
        )
    rule = AI2InvalidationRule(
        reason_codes=("TRUST_STATE_CHANGED", "TRUST_DOWNGRADED"),
        declared_by=DECLARER,
        declared_at_utc=NOW,
    )
    with pytest.raises(ValidationError):
        rule.declared_by = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. recovery_decision composed against loop-shaped inputs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_error_outcome_composes_with_fail_closed_recovery_class(
    monkeypatch,
) -> None:
    """The loop's runner-error containment (outcome "runner_error", recovery
    hard-wired ESCALATE_FAIL_CLOSED, ledger status FAILED) composes with the
    recovery contract: the deterministic-gate class of ``recovery_decision``
    yields exactly that label, while the budget-retryable provider-failure
    class WOULD have said RETRY — the loop deliberately takes the stricter
    class because the stage-2 outcome is UNKNOWN after an internal fault.
    The stored no-observation sentinel trust composes fail-closed too."""
    service = AI2Service()

    async def _boom(request, market_service, *, transport=None):
        raise RuntimeError("synthetic internal fault")

    monkeypatch.setattr(service, "run", _boom)
    runner = _runner(service=service)
    outcome = await runner.execute_run(
        _run_input("rec-err", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert outcome.outcome == "runner_error"
    assert outcome.ok is False
    assert outcome.ledger_status == "FAILED"
    assert outcome.recovery == "ESCALATE_FAIL_CLOSED"
    assert outcome.record is not None
    assert outcome.record.status == "FAILED"
    assert outcome.record.trust_state == "unobserved"
    # The attempt was honestly accounted (one stage-2 invocation consumed).
    assert runner.loop_status().stage2_invocations_used == 1

    # Loop-shaped recovery reading: the deterministic-gate class produces the
    # same label the loop attached.
    assert (
        recovery_decision(
            failed_invocations=runner.loop_status().stage2_invocations_used,
            budget=BUDGET,
            failure_is_deterministic_gate=True,
        )
        == "ESCALATE_FAIL_CLOSED"
        == outcome.recovery
    )
    # The non-gate class would have retried (1+1 <= 3): the loop's choice is
    # the stricter, fail-closed class.
    assert (
        recovery_decision(failed_invocations=1, budget=BUDGET, failure_is_deterministic_gate=False)
        == "RETRY_WITHIN_BUDGET"
    )
    # The sentinel-trust FAILED record composes with invalidates() in the
    # fail-closed direction (unknown state ranks below every named state).
    assert invalidates("live", outcome.record.trust_state, None, None) == (
        "TRUST_STATE_CHANGED",
        "TRUST_DOWNGRADED",
    )


@pytest.mark.asyncio
async def test_gated_outcome_recovery_is_computed_through_recovery_decision() -> None:
    """With the REAL default config (AI2_ENABLED=0) the loop's gated refusal
    computes its recovery through ``recovery_decision`` itself (deterministic
    gate → ESCALATE_FAIL_CLOSED). The composed outcome label must equal a
    direct call with the loop's own counters — the two surfaces agree by
    construction, deterministically. The attempt is still honestly accounted
    (the service.run call happened; its gate refused it)."""
    calls: list[Any] = []

    def _spy_transport(payload):  # pragma: no cover — must never be called
        calls.append(payload)
        raise AssertionError("transport must not run while AI2 disabled")

    runner = _runner()
    outcome = await runner.execute_run(
        _run_input("rec-gated", SHA_A), DummyMarketService(), transport=_spy_transport
    )
    assert calls == []  # the gate precedes any provider invocation
    assert outcome.outcome == "gated_not_executed"
    assert outcome.ok is False
    assert outcome.ledger_status == "GATED_NOT_EXECUTED"
    assert outcome.recovery == "ESCALATE_FAIL_CLOSED"
    assert runner.loop_status().stage2_invocations_used == 1
    assert len(runner.ledger.records) == 1
    assert (
        recovery_decision(
            failed_invocations=runner.loop_status().stage2_invocations_used,
            budget=BUDGET,
            failure_is_deterministic_gate=True,
        )
        == outcome.recovery
    )


@pytest.mark.asyncio
async def test_provider_failure_recovery_math_composes_with_budget_exhaustion(
    _shadow_env,
) -> None:
    """Hand-verified session (max_provider_invocations=2): failed run 1 →
    RETRY_WITHIN_BUDGET (1+1 <= 2); failed run 2 → ESCALATE_FAIL_CLOSED
    (2+1 > 2, ceiling inclusive); run 3 is refused pre-run as budget_exhausted
    with recovery None — no stage-2 invocation happened, so there is no failed
    step to recover. Every direct recovery_decision reading of the exhausted
    session state is fail-closed."""
    budget = AI2BudgetSpec(max_provider_invocations=2, max_iterations=8, max_wall_seconds=1800)
    runner = _runner(budget=budget)
    r1 = await runner.execute_run(
        _run_input("rec-1", SHA_A), DummyMarketService(), transport=_timeout_transport
    )
    r2 = await runner.execute_run(
        _run_input("rec-2", SHA_B), DummyMarketService(), transport=_timeout_transport
    )
    assert r1.outcome == "failed_provider" and r1.recovery == "RETRY_WITHIN_BUDGET"
    assert r2.outcome == "failed_provider" and r2.recovery == "ESCALATE_FAIL_CLOSED"
    # The loop-shaped inputs behind each label reproduce it exactly.
    assert (
        recovery_decision(failed_invocations=1, budget=budget, failure_is_deterministic_gate=False)
        == r1.recovery
    )
    assert (
        recovery_decision(failed_invocations=2, budget=budget, failure_is_deterministic_gate=False)
        == r2.recovery
    )

    r3 = await runner.execute_run(
        _run_input("rec-3", SHA_C), DummyMarketService(), transport=_timeout_transport
    )
    assert r3.outcome == "budget_exhausted"
    assert r3.ok is False
    assert r3.ledger_status == "BUDGET_EXHAUSTED"
    assert r3.recovery is None  # nothing ran → no failed step to recover
    assert r3.record is not None and r3.record.status == "BUDGET_EXHAUSTED"
    status = runner.loop_status()
    assert status.budget_now == "BUDGET_EXHAUSTED"
    assert status.stage2_invocations_used == 2
    # Every recovery_decision reading of the exhausted session is fail-closed,
    # whichever failure class is assigned.
    assert (
        recovery_decision(failed_invocations=2, budget=budget, failure_is_deterministic_gate=False)
        == "ESCALATE_FAIL_CLOSED"
    )
    assert (
        recovery_decision(failed_invocations=2, budget=budget, failure_is_deterministic_gate=True)
        == "ESCALATE_FAIL_CLOSED"
    )


@pytest.mark.asyncio
async def test_duplicate_refusal_is_deterministic_gate_class_not_a_retryable_failure(
    _shadow_env,
) -> None:
    """A duplicate refusal never ran a provider step, so the loop records no
    recovery for it — and the refusal itself derives from a deterministic,
    content-keyed classification (``classify_duplicate`` is a pure function of
    the ledger). Composed with the recovery contract, that places the refusal
    in the deterministic-gate class (never retried), NOT in the budget-
    retryable provider-failure class; the refusal consumes no invocation."""
    runner = _runner()
    first = await runner.execute_run(
        _run_input("rec-1", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert first.ok is True
    second = await runner.execute_run(
        _run_input("rec-2", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert second.outcome == "duplicate_refused"
    assert second.duplicate_class == "DUPLICATE_IDENTICAL"
    assert second.recovery is None  # no provider step failed — nothing to recover
    assert second.record is None  # nothing appended
    # The classification the refusal is derived from is reproducible directly.
    assert (
        classify_duplicate(runner.ledger, task="analyst", input_snapshot_sha256=SHA_A)
        == "DUPLICATE_IDENTICAL"
    )
    # Deterministic-gate class → fail-closed (never retried); the loop did NOT
    # model the refusal as a retryable provider failure (that class would
    # retry at failed_invocations=0).
    assert (
        recovery_decision(failed_invocations=0, budget=BUDGET, failure_is_deterministic_gate=True)
        == "ESCALATE_FAIL_CLOSED"
    )
    assert (
        recovery_decision(failed_invocations=0, budget=BUDGET, failure_is_deterministic_gate=False)
        == "RETRY_WITHIN_BUDGET"
    )
    # The refusal consumed no stage-2 invocation.
    assert runner.loop_status().stage2_invocations_used == 1


# ---------------------------------------------------------------------------
# 4. State-machine honesty: invalidation is no duplicate-success shortcut
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidated_result_cannot_be_accepted_as_duplicate_success(
    _shadow_env,
) -> None:
    """Composition property: invalidating a stored result does not open a
    duplicate-success shortcut. (a) The INVALIDATED label is refused by
    ``governed_acceptance``. (b) The identical (task, snapshot) pair is still
    content-keyed as DUPLICATE_IDENTICAL and the loop refuses the re-attempt
    BEFORE execution — no silent re-run, no re-acceptance. (c) A re-asked
    question (same task, different snapshot) executes but lands
    DUPLICATE_FLAGGED, which can never carry an artifact and hence never
    reach COMPLETED — ``governed_acceptance`` refuses it too."""
    runner = _runner()
    first = await runner.execute_run(
        _run_input("rec-1", SHA_A),
        DummyMarketService(trust_state="stale"),
        transport=_valid_transport,
    )
    assert first.record is not None
    stored = first.record

    # Invalidate the stored result (production trust later observed degraded).
    reasons = invalidates(stored.trust_state, "mock", stored.dataset_version, DS_V1)
    assert reasons == ("TRUST_STATE_CHANGED", "TRUST_DOWNGRADED")
    rule, successor = _invalidation_label(
        stored, reasons, observed_trust_state="mock", observed_dataset_version=DS_V1
    )
    ledger = runner.ledger.append(successor)

    # (a) The invalidated label itself is structurally un-acceptable.
    invalidated = ledger.get(successor.record_id)
    assert invalidated is not None
    assert governed_acceptance(_context(), invalidated) == ("run_status_not_completed",)

    # (b) Content-keyed duplicate classification is blind to status: the
    # invalidated-but-ledgered pair still classifies identical, and the loop
    # refuses the re-attempt before execution (nothing runs, nothing appends).
    assert (
        classify_duplicate(ledger, task="analyst", input_snapshot_sha256=SHA_A)
        == "DUPLICATE_IDENTICAL"
    )
    re_attempt = await runner.execute_run(
        _run_input("rec-dup", SHA_A), DummyMarketService(), transport=_valid_transport
    )
    assert re_attempt.outcome == "duplicate_refused"
    assert re_attempt.record is None
    assert len(runner.ledger.records) == 1  # unchanged by the refused attempt

    # (c) A re-asked question (different snapshot) runs and is flagged —
    # never COMPLETED, never accepted.
    re_asked = await runner.execute_run(
        _run_input("rec-2", SHA_B), DummyMarketService(), transport=_valid_transport
    )
    assert re_asked.duplicate_class == "DUPLICATE_REPEATED_QUESTION"
    assert re_asked.ledger_status == "DUPLICATE_FLAGGED"
    assert re_asked.record is not None and re_asked.record.artifact is None
    assert governed_acceptance(_context(), re_asked.record) == ("run_status_not_completed",)

    # The rule stayed a validated label throughout (invalidation is a label,
    # never a deletion or a rewrite of acceptance semantics).
    assert rule.reason_codes == ("TRUST_STATE_CHANGED", "TRUST_DOWNGRADED")
    assert ledger.get(stored.record_id) == stored


# ---------------------------------------------------------------------------
# 5. Unknown trust sentinel ("unobserved") composed with loop outcome labels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unobserved_trust_sentinel_ranks_below_every_named_state(_shadow_env) -> None:
    """The loop stamps refusal records with the declared no-observation
    sentinel trust state ("unobserved") — an UNKNOWN string in the canonical
    coarse trust map, deliberately ranked below mock/synthetic (documented
    fail-closed divergence, D-16-3 iii-B). Composed with real loop outcome
    labels: a budget-exhausted refusal record and a runner-error FAILED record
    both carry the sentinel, and ``invalidates()`` treats ANY named prior
    state's loss to the sentinel as change + downgrade — while reaching a
    named state FROM the sentinel is a change, never a downgrade."""
    budget = AI2BudgetSpec(max_provider_invocations=1, max_iterations=4, max_wall_seconds=1800)
    runner = _runner(budget=budget)
    failed = await runner.execute_run(
        _run_input("rec-1", SHA_A), DummyMarketService(), transport=_timeout_transport
    )
    assert failed.outcome == "failed_provider"
    exhausted = await runner.execute_run(
        _run_input("rec-2", SHA_B), DummyMarketService(), transport=_timeout_transport
    )
    assert exhausted.outcome == "budget_exhausted"
    assert exhausted.record is not None
    assert exhausted.record.trust_state == "unobserved"  # the no-observation sentinel

    sentinel = exhausted.record.trust_state
    # Unknown string composes STRICTER than the named floor: any named state
    # → sentinel is both a change and a downgrade (rank −1, below mock's 0).
    assert invalidates("mock", sentinel, None, None) == (
        "TRUST_STATE_CHANGED",
        "TRUST_DOWNGRADED",
    )
    assert invalidates("live", sentinel, None, None) == (
        "TRUST_STATE_CHANGED",
        "TRUST_DOWNGRADED",
    )
    # The reverse direction: sentinel → named state is a change, never a
    # downgrade; and the sentinel is stable against itself.
    assert invalidates(sentinel, "synthetic", None, None) == ("TRUST_STATE_CHANGED",)
    assert invalidates(sentinel, sentinel, None, None) == ()
    # The fired codes mint a valid rule (the sentinel downgrade is a
    # documentable invalidation reason set).
    rule = AI2InvalidationRule(
        reason_codes=invalidates("live", sentinel, None, None),  # type: ignore[arg-type]
        declared_by=DECLARER,
        declared_at_utc=NOW,
    )
    assert rule.reason_codes == ("TRUST_STATE_CHANGED", "TRUST_DOWNGRADED")

    # Same sentinel composition on a runner_error record (FAILED; the stage-2
    # outcome — and with it the observed trust — was never obtained).
    service = AI2Service()

    async def _boom(request, market_service, *, transport=None):
        raise RuntimeError("synthetic internal fault")

    service.run = _boom  # type: ignore[method-assign]
    err_runner = _runner(service=service)
    err = await err_runner.execute_run(
        _run_input("rec-err", SHA_C), DummyMarketService(), transport=_valid_transport
    )
    assert err.outcome == "runner_error"
    assert err.record is not None and err.record.status == "FAILED"
    assert err.record.trust_state == "unobserved"
    assert invalidates("stale", err.record.trust_state, None, None) == (
        "TRUST_STATE_CHANGED",
        "TRUST_DOWNGRADED",
    )


# ---------------------------------------------------------------------------
# 6. Dataset supersession composes with intact trust
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dataset_supersession_invalidates_record_with_intact_trust(
    _shadow_env,
) -> None:
    """Invalidation also fires on deterministic dataset supersession even when
    trust is intact: the stored loop record's dataset version is observed
    superseded → DATASET_SUPERSEDED only (no trust codes); the label lands as
    a NEW INVALIDATED successor, the run's history keeps both records, and a
    None previous version is never silently treated as equal to a named one."""
    runner = _runner()
    outcome = await runner.execute_run(
        _run_input("rec-1", SHA_A),
        DummyMarketService(trust_state="mock"),
        transport=_valid_transport,
    )
    assert outcome.record is not None
    stored = outcome.record
    assert stored.trust_state == "mock" and stored.dataset_version == DS_V1

    assert invalidates(stored.trust_state, stored.trust_state, stored.dataset_version, DS_V2) == (
        "DATASET_SUPERSEDED",
    )
    # Honesty about unknowns: a None previous version is NOT treated as equal
    # to a named version — nothing fires rather than an invented match.
    assert invalidates(stored.trust_state, stored.trust_state, None, DS_V2) == ()

    rule, successor = _invalidation_label(
        stored,
        ("DATASET_SUPERSEDED",),
        observed_trust_state=stored.trust_state,
        observed_dataset_version=DS_V2,
    )
    assert rule.reason_codes == ("DATASET_SUPERSEDED",)
    ledger = runner.ledger.append(successor)
    history = ledger.history_for_run(RUN)
    assert [rec.status for rec in history] == ["LEDGERED", "INVALIDATED"]
    assert ledger.get(stored.record_id) == stored
    invalidated = ledger.get(successor.record_id)
    assert invalidated is not None
    assert governed_acceptance(_context(), invalidated) == ("run_status_not_completed",)


# ---------------------------------------------------------------------------
# 7. recovery_decision purity/determinism over the loop's label vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("loop_label", "failed_invocations", "deterministic_gate", "expected"),
    [
        ("runner_error", 1, True, "ESCALATE_FAIL_CLOSED"),
        ("gated_not_executed", 0, True, "ESCALATE_FAIL_CLOSED"),
        ("duplicate_refused", 0, True, "ESCALATE_FAIL_CLOSED"),
        ("failed_provider_within_budget", 1, False, "RETRY_WITHIN_BUDGET"),
        ("failed_provider_at_ceiling", 2, False, "ESCALATE_FAIL_CLOSED"),
        ("budget_exhausted", 2, False, "ESCALATE_FAIL_CLOSED"),
    ],
)
def test_recovery_decision_is_deterministic_over_loop_shaped_inputs(
    loop_label: str, failed_invocations: int, deterministic_gate: bool, expected: str
) -> None:
    """Documented recovery contract read against loop-shaped inputs: the
    loop's failure labels map onto (failed_invocations, budget,
    failure_is_deterministic_gate); deterministic-gate-class labels are NEVER
    retried, provider-style labels retry only while the invocation ceiling
    allows (inclusive comparison). The function is pure: repeated evaluation
    of the same loop-shaped input yields the identical label."""
    budget = AI2BudgetSpec(max_provider_invocations=2, max_iterations=8, max_wall_seconds=1800)
    first = recovery_decision(
        failed_invocations=failed_invocations,
        budget=budget,
        failure_is_deterministic_gate=deterministic_gate,
    )
    second = recovery_decision(
        failed_invocations=failed_invocations,
        budget=budget,
        failure_is_deterministic_gate=deterministic_gate,
    )
    assert first == second == expected, loop_label
