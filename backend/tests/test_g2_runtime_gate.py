"""Runtime G2 gate tests (GOV-32 Phase 3C).

Covers every fail-closed denial class of ``app.domain.g2_gate`` and the
service-level entry point (``AI2Service.run``) — positive AND negative:

- missing / malformed / stale / contradictory / unverifiable gate evidence;
- the honest designed denial (``g2_gate_not_passed``);
- a fully valid PASSED fixture (the only allowance path);
- the production entry point refuses real-data AI-2 while the gate denies,
  including when AI2_ENABLED=1 and when verified-LIVE trust is hand-minted
  (the future path) — no bypass through configuration or transport labeling;
- the synthetic/paper entry point stays explicitly labeled SYNTHETIC_OR_PAPER
  and never LIVE;
- retry determinism (repeated runs refuse identically);
- the tracked state document parses and is mechanically verified at the default
  path (post-transition: allowance ONLY via the full verifying chain — committed
  owner-decision document, exact hash binding, matching running commit; any
  unknown/mismatched running commit still denies as stale);
- protected governance pins are untouched by the runtime gate (hash checks).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.g2_gate import (
    G2GateState,
    G2OwnerDecision,
    PROCEDURE_IDENTITY,
    PROCEDURE_VERSION_APPROVED,
    evaluate_g2_gate,
    execution_mode,
    owner_decision_document_complete,
    sha256_text,
)
from app.domain.evidence import SCHEMA_VERSION

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
SHA1 = "1" * 64
SHA2 = "2" * 64

NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)

VALID_OWNER_DECISION_TEXT = (
    "# OWNER G2 DECISION (fixture)\n\n"
    "G2 verdict: PASSED\n"
    "Approving authority: Project Owner (Role 1)\n"
    "Approval date (UTC): 2026-10-29\n"
    "Approval evidence / locus: convened review record\n"
)


def owner_decision(**overrides) -> G2OwnerDecision:
    base = dict(
        decision="G2_PASSED",
        authority="Project Owner (Role 1)",
        decided_at_utc=NOW,
        decision_document="docs/active/OWNER_G2_DECISION_fixture.md",
        decision_document_sha256=sha256_text(VALID_OWNER_DECISION_TEXT),
    )
    base.update(overrides)
    return G2OwnerDecision(**base)


def gate_state(**overrides) -> G2GateState:
    base = dict(
        verdict="PASSED",
        recorded_at_utc=NOW,
        recorded_by="owner-recorded state transition",
        procedure_identity=PROCEDURE_IDENTITY,
        procedure_version=PROCEDURE_VERSION_APPROVED,
        reviewer_identity="independent reviewer (fixture)",
        reviewer_acknowledgement_utc=NOW,
        coi_adjudication="D-O3 recorded (fixture)",
        convened_review_commit=COMMIT_A,
        evidence_harness_report_sha256=SHA1,
        owner_decision=owner_decision(),
        previous_state_sha256=None,
    )
    base.update(overrides)
    return G2GateState(**base)


# ---------------------------------------------------------------------------
# Domain evaluator — denial classes
# ---------------------------------------------------------------------------


class TestDenialClasses:
    def test_missing_state_denies(self):
        allowed, tags = evaluate_g2_gate(None, current_commit=COMMIT_A)
        assert allowed is False
        assert tags == ("gate_state_missing",)

    def test_honest_not_passed_denies(self):
        state = gate_state(verdict="NOT_PASSED", owner_decision=None)
        allowed, tags = evaluate_g2_gate(state, current_commit=COMMIT_A)
        assert allowed is False
        assert tags == ("g2_gate_not_passed",)

    def test_stale_commit_denies(self):
        allowed, tags = evaluate_g2_gate(gate_state(), current_commit=COMMIT_B)
        assert allowed is False
        assert "gate_state_stale" in tags

    def test_unknown_running_commit_denies_passed_state(self):
        allowed, tags = evaluate_g2_gate(gate_state(), current_commit=None)
        assert allowed is False
        assert "gate_state_stale" in tags

    def test_missing_owner_decision_denies(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(owner_decision=None), current_commit=COMMIT_A
        )
        assert allowed is False
        assert "owner_verdict_not_recorded" in tags

    def test_contradictory_owner_decision_denies(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(owner_decision=owner_decision(decision="G2_NOT_PASSED")),
            current_commit=COMMIT_A,
        )
        assert allowed is False
        assert "gate_state_contradictory" in tags

    def test_wrong_procedure_denies(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(procedure_version="0.2"), current_commit=COMMIT_A
        )
        assert allowed is False
        assert "procedure_not_approved" in tags

    def test_missing_reviewer_acknowledgement_denies(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(reviewer_identity=None, reviewer_acknowledgement_utc=None),
            current_commit=COMMIT_A,
        )
        assert allowed is False
        assert "reviewer_acknowledgement_missing" in tags

    def test_missing_coi_adjudication_denies(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(coi_adjudication=None), current_commit=COMMIT_A
        )
        assert allowed is False
        assert "coi_adjudication_missing" in tags

    def test_unverifiable_owner_document_denies(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(), current_commit=COMMIT_A, owner_decision_text=None
        )
        assert allowed is False
        assert "owner_decision_unverifiable" in tags

    def test_owner_document_hash_mismatch_denies(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(), current_commit=COMMIT_A, owner_decision_text="tampered"
        )
        assert allowed is False
        assert "owner_decision_unverifiable" in tags

    def test_owner_document_incomplete_block_denies(self):
        incomplete = VALID_OWNER_DECISION_TEXT.replace(
            "Approving authority: Project Owner (Role 1)\n", ""
        )
        state = gate_state(
            owner_decision=owner_decision(decision_document_sha256=sha256_text(incomplete))
        )
        allowed, tags = evaluate_g2_gate(
            state, current_commit=COMMIT_A, owner_decision_text=incomplete
        )
        assert allowed is False
        assert "owner_decision_unverifiable" in tags

    def test_all_refusal_tags_collected_not_first_failure(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(
                procedure_version="0.2",
                coi_adjudication=None,
                owner_decision=owner_decision(decision_document_sha256=SHA2),
            ),
            current_commit=COMMIT_B,
            owner_decision_text=None,
        )
        assert allowed is False
        assert tags == (
            "gate_state_stale",
            "procedure_not_approved",
            "coi_adjudication_missing",
            "owner_decision_unverifiable",
        )


# ---------------------------------------------------------------------------
# Positive path
# ---------------------------------------------------------------------------


class TestPositivePath:
    def test_fully_valid_passed_state_allows(self):
        allowed, tags = evaluate_g2_gate(
            gate_state(),
            current_commit=COMMIT_A,
            owner_decision_text=VALID_OWNER_DECISION_TEXT,
        )
        assert allowed is True
        assert tags == ()

    def test_owner_document_complete_accepts_valid_block(self):
        assert owner_decision_document_complete(VALID_OWNER_DECISION_TEXT) is True

    def test_owner_document_complete_rejects_underscore_placeholder(self):
        text = VALID_OWNER_DECISION_TEXT.replace(
            "Approving authority: Project Owner (Role 1)",
            "Approving authority: ________",
        )
        assert owner_decision_document_complete(text) is False

    def test_owner_document_complete_rejects_missing_verdict(self):
        text = VALID_OWNER_DECISION_TEXT.replace("G2 verdict: PASSED\n", "")
        assert owner_decision_document_complete(text) is False

    def test_owner_document_complete_rejects_not_passed_verdict(self):
        text = VALID_OWNER_DECISION_TEXT.replace("G2 verdict: PASSED", "G2 verdict: NOT PASSED")
        assert owner_decision_document_complete(text) is False

    def test_owner_document_complete_rejects_caveat_prefixed_verdict(self):
        # F-RV4 regression: only an exact "PASSED" verdict records a pass —
        # caveat-prefixed values are not a recorded G2 pass.
        text = VALID_OWNER_DECISION_TEXT.replace(
            "G2 verdict: PASSED", "G2 verdict: PASSED_WITH_CAVEATS"
        )
        assert owner_decision_document_complete(text) is False


# ---------------------------------------------------------------------------
# Model-level structural validation (malformed class)
# ---------------------------------------------------------------------------


class TestSchemaStrictness:
    def test_non_hex_commit_rejected(self):
        with pytest.raises(ValidationError):
            gate_state(convened_review_commit="ZZ" * 20)

    def test_wrong_commit_length_rejected(self):
        with pytest.raises(ValidationError):
            gate_state(convened_review_commit="ab" * 10)

    def test_non_hex_sha_rejected(self):
        with pytest.raises(ValidationError):
            gate_state(evidence_harness_report_sha256="zz" * 32)

    def test_invalid_verdict_rejected(self):
        with pytest.raises(ValidationError):
            gate_state(verdict="MAYBE")

    def test_invalid_owner_decision_label_rejected(self):
        with pytest.raises(ValidationError):
            owner_decision(decision="SURE_WHATEVER")

    def test_gate_literal_fixed(self):
        with pytest.raises(ValidationError):
            gate_state()
            G2GateState(**{**gate_state().model_dump(), "gate": "G1"})

    def test_naive_datetime_rejected(self):
        # Domain discipline: naive timestamps are rejected (ensure_utc), so
        # every recorded instant is unambiguous.
        with pytest.raises(ValidationError):
            gate_state(recorded_at_utc=datetime(2026, 10, 29, 12, 0, 0))

    def test_unknown_state_fields_rejected(self):
        # F-RV5 regression: unknown fields are malformed (extra=forbid), not
        # silently ignored — a doctored state cannot smuggle semantics in.
        with pytest.raises(ValidationError):
            G2GateState(**{**gate_state().model_dump(), "verdict_override": "PASSED"})


# ---------------------------------------------------------------------------
# Execution-mode labeling
# ---------------------------------------------------------------------------


class TestExecutionMode:
    def test_live_only_when_verified(self):
        assert execution_mode(True) == "LIVE"

    def test_everything_else_explicitly_synthetic_or_paper(self):
        assert execution_mode(False) == "SYNTHETIC_OR_PAPER"


# ---------------------------------------------------------------------------
# Service entry point (AI2Service.run)
# ---------------------------------------------------------------------------


class _AIRequest:
    question = "q"
    symbol = "فملی"
    filter_expr = None
    backtest_result = None
    language = "en"
    task = "analyst"
    depth = "standard"


class _MarketService:
    """Same convention as tests/test_ai2_service.py DummyMarketService."""

    def __init__(self, trust_state="mock", live_verified=False):
        self._data_trust = {
            "state": trust_state,
            "trust_level": "synthetic" if trust_state in {"mock", "synthetic"} else "mixed",
            "source": "mock_fallback",
            "provider": "mock_fallback",
            "is_live": live_verified,
            "live_verified": live_verified,
            "is_generated": trust_state in {"mock", "synthetic"},
            "warning": f"{trust_state.upper()} data",
        }

    async def get_analysis(self, force=False):
        return None

    def status(self):
        return {"source": "mock_fallback", "trust_level": "synthetic", "symbol_count": 1}

    def data_trust_context(self):
        return self._data_trust

    def get_symbol(self, symbol):
        if symbol != "فملی":
            return None
        return {
            "snapshot": {"l18": "فملی", "pl": 1000, "plp": -1.5},
            "metrics": {"entry_score": 75, "exit_score": 20, "buy_power": 2.1},
            "tablocastic": {"grade": "A"},
            "data_trust": self._data_trust,
        }

    def run_user_filter(self, expr, limit=10):
        return {"ok": True, "count": 1, "rows": [], "data_trust": self._data_trust}


@pytest.fixture
def _openai_env(monkeypatch):
    """Configure an external provider so the seam accepts the test transport
    (same convention as the AI-2 service tests). No network occurs."""
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "unit-test-key")


def _state_settings(monkeypatch, tmp_path: Path, state_doc: str, *, ai2_enabled=True,
                    runtime_commit=COMMIT_A):
    from types import SimpleNamespace

    from app.services import ai2_service as ai2_module

    state_path = tmp_path / "G2_GATE_STATE.json"
    state_path.write_text(state_doc, encoding="utf-8")
    settings = SimpleNamespace(
        ai2_enabled=ai2_enabled,
        g2_gate_state_path=str(state_path),
        runtime_commit=runtime_commit,
    )
    monkeypatch.setattr(ai2_module, "get_settings", lambda: settings)
    return ai2_module


def _write_owner_doc(tmp_path: Path, state_doc: str) -> str:
    doc_path = tmp_path / "OWNER_G2_DECISION_fixture.md"
    doc_path.write_text(VALID_OWNER_DECISION_TEXT, encoding="utf-8")
    return json.dumps(
        json.loads(state_doc)
        | {"owner_decision": {
            "decision": "G2_PASSED",
            "authority": "Project Owner (Role 1)",
            "decided_at_utc": "2026-10-29T12:00:00Z",
            "decision_document": str(doc_path),
            "decision_document_sha256": sha256_text(VALID_OWNER_DECISION_TEXT),
          }},
        indent=2,
    )


def _passed_state_doc(tmp_path: Path) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "G2",
            "verdict": "PASSED",
            "recorded_at_utc": "2026-10-29T12:00:00Z",
            "recorded_by": "owner-recorded state transition",
            "procedure_identity": PROCEDURE_IDENTITY,
            "procedure_version": PROCEDURE_VERSION_APPROVED,
            "reviewer_identity": "independent reviewer (fixture)",
            "reviewer_acknowledgement_utc": "2026-10-29T12:00:00Z",
            "coi_adjudication": "D-O3 recorded (fixture)",
            "convened_review_commit": COMMIT_A,
            "evidence_harness_report_sha256": SHA1,
            "owner_decision": None,
            "previous_state_sha256": None,
        },
        indent=2,
    )


@pytest.mark.asyncio
async def test_production_path_refuses_on_honest_not_passed_state(monkeypatch, tmp_path):
    """Real-data AI-2 (no transport) refuses while the formal verdict is
    NOT_PASSED — even with AI2_ENABLED=1 (no bypass via configuration)."""
    ai2_module = _state_settings(
        monkeypatch, tmp_path, _passed_state_doc(tmp_path).replace("PASSED", "NOT_PASSED"),
        ai2_enabled=True,
    )
    svc = ai2_module.AI2Service()
    res = await svc.run(_AIRequest(), _MarketService(), transport=None)
    assert res.status == "gated_not_executed"
    assert res.error_code == "g2_independent_validation_required"
    gate = res.provenance.gate
    assert gate["g2_gate_verdict"] == "NOT_PASSED"
    assert gate["g2_gate_refusals"] == ["g2_gate_not_passed"]
    assert gate["execution_mode"] == "SYNTHETIC_OR_PAPER"
    assert any("Runtime G2 gate refused" in w for w in res.warnings)


@pytest.mark.asyncio
async def test_missing_state_file_denies_production_path(monkeypatch, tmp_path):
    from app.services import ai2_service as ai2_module

    class _S:
        ai2_enabled = True
        g2_gate_state_path = str(tmp_path / "does_not_exist.json")
        runtime_commit = COMMIT_A

    monkeypatch.setattr(ai2_module, "get_settings", lambda: _S())
    res = await ai2_module.AI2Service().run(_AIRequest(), _MarketService(), transport=None)
    assert res.status == "gated_not_executed"
    assert res.provenance.gate["g2_gate_load_error"] == "gate_state_missing"
    assert res.provenance.gate["g2_gate_refusals"] == ["gate_state_missing"]


@pytest.mark.asyncio
async def test_malformed_state_file_denies_production_path(monkeypatch, tmp_path):
    ai2_module = _state_settings(
        monkeypatch, tmp_path, "{ this is not json", ai2_enabled=True
    )
    res = await ai2_module.AI2Service().run(_AIRequest(), _MarketService(), transport=None)
    assert res.status == "gated_not_executed"
    assert res.provenance.gate["g2_gate_load_error"] == "gate_state_malformed"
    assert res.provenance.gate["g2_gate_refusals"] == ["gate_state_malformed"]


@pytest.mark.asyncio
async def test_future_live_path_still_blocked_without_gate_allowance(monkeypatch, tmp_path):
    """Hand-minted verified-LIVE trust through the production seam is still
    refused while the gate denies — the structural live-verified gate alone
    is no longer the only control (no bypass route)."""
    ai2_module = _state_settings(
        monkeypatch, tmp_path, _passed_state_doc(tmp_path).replace("PASSED", "NOT_PASSED"),
        ai2_enabled=True,
    )
    invoked: list = []
    monkeypatch.setattr(ai2_module, "invoke_ai_provider", lambda *a, **k: invoked.append(a))
    res = await ai2_module.AI2Service().run(
        _AIRequest(), _MarketService(trust_state="live", live_verified=True), transport=None
    )
    assert res.status == "gated_not_executed"
    assert res.error_code == "g2_independent_validation_required"
    assert invoked == []


@pytest.mark.asyncio
async def test_future_live_path_allowed_only_with_full_valid_gate(monkeypatch, tmp_path):
    """Positive entry-point test: with a fully valid PASSED state (matching
    commit, approved procedure, reviewer ack, COI, verifying owner decision
    document) the production seam becomes reachable — and ONLY then."""
    ai2_module = _state_settings(
        monkeypatch, tmp_path, _write_owner_doc(tmp_path, _passed_state_doc(tmp_path)),
        ai2_enabled=True, runtime_commit=COMMIT_A,
    )

    def _seam(payload, **kwargs):
        return {
            "ok": True, "status": "executed", "error_code": None,
            "text": json.dumps({
                "summary": "ok",
                "observations": [], "risks": [], "confidence": 0.5,
            }),
            "live_llm": False, "test_only": False,
            "requested": "openai", "attempts": 1,
        }

    monkeypatch.setattr(ai2_module, "invoke_ai_provider", _seam)
    res = await ai2_module.AI2Service().run(
        _AIRequest(), _MarketService(trust_state="live", live_verified=True), transport=None
    )
    assert res.status == "executed"
    gate = res.provenance.gate
    assert gate["g2_gate_verdict"] == "PASSED"
    assert gate["g2_gate_refusals"] == []
    assert gate["execution_mode"] == "LIVE"


@pytest.mark.asyncio
async def test_synthetic_transport_path_labeled_never_live(monkeypatch, tmp_path, _openai_env):
    """Synthetic/paper execution (injected test transport) proceeds pre-G2 as
    policy allows — but is explicitly labeled SYNTHETIC_OR_PAPER and the gate
    state is recorded, never represented as LIVE."""

    def _valid_transport(payload):
        return {
            "text": json.dumps({
                "summary": "ok",
                "observations": [], "risks": [], "confidence": 0.5,
            })
        }

    ai2_module = _state_settings(
        monkeypatch, tmp_path, _passed_state_doc(tmp_path).replace("PASSED", "NOT_PASSED"),
        ai2_enabled=True,
    )
    res = await ai2_module.AI2Service().run(
        _AIRequest(), _MarketService(), transport=_valid_transport
    )
    assert res.status == "executed_shadow"
    assert res.provenance.test_only_transport is True
    assert res.provenance.gate["execution_mode"] == "SYNTHETIC_OR_PAPER"
    assert res.provenance.gate["g2_gate_verdict"] == "NOT_PASSED"
    assert res.provenance.live_verified is False


@pytest.mark.asyncio
async def test_retry_determinism_refusal_is_stable(monkeypatch, tmp_path):
    """The deterministic-gate refusal NEVER becomes retryable: repeated
    production runs refuse identically (recovery_decision semantics)."""
    ai2_module = _state_settings(
        monkeypatch, tmp_path, _passed_state_doc(tmp_path).replace("PASSED", "NOT_PASSED"),
        ai2_enabled=True,
    )
    svc = ai2_module.AI2Service()
    first = await svc.run(_AIRequest(), _MarketService(), transport=None)
    second = await svc.run(_AIRequest(), _MarketService(), transport=None)
    assert first.status == second.status == "gated_not_executed"
    assert first.error_code == second.error_code
    assert first.provenance.gate["g2_gate_refusals"] == second.provenance.gate["g2_gate_refusals"]


# ---------------------------------------------------------------------------
# Tracked honest state document (integration, default path)
# ---------------------------------------------------------------------------


class TestTrackedStateDocument:
    REPO_ROOT = Path(__file__).resolve().parents[2]

    def test_tracked_state_document_parses_and_allows_only_via_valid_chain(self):
        # Post-transition (CONSOL-GOV-37 owner decision record): the tracked
        # state is PASSED and the evaluator allows ONLY via the full verifying
        # chain — the referenced owner-decision document must exist, hash-match
        # its recorded SHA-256, and the running commit must bind the convened
        # commit. Fail-closed behavior is asserted in the same test.
        from app.services.ai2_service import _DEFAULT_G2_GATE_STATE_PATH

        assert _DEFAULT_G2_GATE_STATE_PATH.name == "G2_GATE_STATE.json"
        text = _DEFAULT_G2_GATE_STATE_PATH.read_text(encoding="utf-8")
        state = G2GateState.model_validate(json.loads(text))
        assert state.verdict == "PASSED"
        assert state.owner_decision is not None
        assert state.owner_decision.decision == "G2_PASSED"
        decision_text = (self.REPO_ROOT / state.owner_decision.decision_document).read_text(
            encoding="utf-8"
        )
        assert sha256_text(decision_text) == state.owner_decision.decision_document_sha256
        allowed, tags = evaluate_g2_gate(
            state,
            current_commit=state.convened_review_commit,
            owner_decision_text=decision_text,
        )
        assert allowed is True
        assert tags == ()
        allowed_stale, tags_stale = evaluate_g2_gate(
            state, current_commit=None, owner_decision_text=decision_text
        )
        assert allowed_stale is False
        assert tags_stale == ("gate_state_stale",)

    def test_tracked_state_binds_reviewed_target_and_decision_document(self):
        text = (self.REPO_ROOT / "docs/active/G2_GATE_STATE.json").read_text(
            encoding="utf-8"
        )
        state = json.loads(text)
        # The state binds the reviewed final target (GOV-32/33 terminal target
        # 9e7c6a2…, convened by the recorded owner decision) and a 64-hex
        # harness-report reference (the report itself lives in the cycle
        # evidence package, outside the tracked tree).
        assert state["convened_review_commit"] == "9e7c6a21b8b61e2ccb4dc5f1d2249e6af8773242"
        assert len(state["evidence_harness_report_sha256"]) == 64
        assert all(c in "0123456789abcdef" for c in state["evidence_harness_report_sha256"])
        # Integration-level anti-tamper check: the referenced owner-decision
        # document exists in the tracked tree and its committed content
        # hash-matches the reference recorded in the state document.
        doc = (self.REPO_ROOT / state["owner_decision"]["decision_document"]).read_text(
            encoding="utf-8"
        )
        assert (
            hashlib.sha256(doc.encode("utf-8")).hexdigest()
            == state["owner_decision"]["decision_document_sha256"]
        )

    def test_default_path_resolution_from_docs_active(self):
        from app.services.ai2_service import _DEFAULT_G2_GATE_STATE_PATH

        # parents[2] of docs/active/G2_GATE_STATE.json is the repo root
        assert (_DEFAULT_G2_GATE_STATE_PATH.parents[2] / "backend").is_dir()


# ---------------------------------------------------------------------------
# Protected governance pins untouched by the runtime gate
# ---------------------------------------------------------------------------


class TestProtectedPinsUnchanged:
    PIN_AI2_GOVERNANCE = (
        "39ef15cdf617b9978c88e15d09aadb60e9f7dc8c6c4e60bc5ab065dca772bac2"
    )
    PIN_RUN_GOVERNANCE = (
        "6f320a494940d900d81821cb2196fa8cb59e9f2bcccc5206ae9a5e86285071f8"
    )

    def test_domain_pins_zero_drift(self):
        domain_dir = Path(__file__).resolve().parents[1] / "app" / "domain"
        assert (
            hashlib.sha256((domain_dir / "ai2_governance.py").read_bytes()).hexdigest()
            == self.PIN_AI2_GOVERNANCE
        )
        assert (
            hashlib.sha256((domain_dir / "run_governance.py").read_bytes()).hexdigest()
            == self.PIN_RUN_GOVERNANCE
        )

    def test_config_gate_defaults_preserved(self):
        config_text = (
            Path(__file__).resolve().parents[1] / "app" / "core" / "config.py"
        ).read_text(encoding="utf-8")
        assert '_env_bool("AI2_ENABLED", "0")' in config_text
        assert "verified = False" in config_text
