"""AI-1 gap-closure acceptance tests — run governance + memory interfaces.

Derived from the 2026-10-02 amendment corpus (byte-verified), NOT from the
implementation:
- 00_OWNER_ROADMAP_DECISION §Binding principles 9 (one RunContext/
  RunProvenance per governed run).
- 02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE rules 10/12 (canonical binding;
  traceable to run_id) and §Memory (episodic immutable / semantic
  curated-versioned).
- 03_AI_GOVERNANCE_BOUNDARIES §Run provenance (missing provenance blocks
  acceptance) and §Autonomy levels (no silent increase; L4 human-controlled).
- D-AI-22, D-AI-28 (05 register).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.memory_interfaces import (
    EpisodicMemoryLog,
    EpisodicMemoryRecord,
    MemoryOperationKind,
    SemanticMemoryEntry,
    SemanticMemoryStore,
)
from app.domain.run_governance import (
    ArtifactRef,
    RunContext,
    RunProvenance,
    assert_autonomy_permitted,
    bind_provenance,
    missing_required_provenance,
    provenance_complete,
)

UTC = timezone.utc
T0 = datetime(2026, 10, 18, 9, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 18, 9, 5, 0, tzinfo=UTC)
SHA = "a" * 64
COMMIT = "b" * 40


def ctx(**over: object) -> RunContext:
    base = dict(
        run_id="run-1",
        run_kind="SYMBOL_INTERPRETATION",
        policy_version="gov-1",
        created_at_utc=T0,
    )
    base.update(over)
    return RunContext(**base)  # type: ignore[arg-type]


def prov(**over: object) -> RunProvenance:
    base = dict(
        run_id="run-1",
        policy_version="gov-1",
        started_at_utc=T0,
        finished_at_utc=T1,
    )
    base.update(over)
    return RunProvenance(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RunContext — canonical run identity
# ---------------------------------------------------------------------------


def test_run_context_frozen() -> None:
    c = ctx()
    with pytest.raises(ValidationError):
        c.run_id = "run-2"  # type: ignore[misc]


def test_run_context_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        ctx(created_at_utc=datetime(2026, 10, 18, 9, 0, 0))


def test_run_context_run_kind_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        ctx(run_kind="symbol_interpretation")
    with pytest.raises(ValidationError):
        ctx(run_kind="1BAD KIND")


def test_run_context_artifact_ref_sha256_shape() -> None:
    ok = ctx(artifacts=(ArtifactRef(artifact_id="a1", kind="backtest", ref="file:///x", sha256=SHA),))
    assert ok.artifacts[0].sha256 == SHA
    with pytest.raises(ValidationError):
        ArtifactRef(artifact_id="a2", kind="backtest", ref="file:///x", sha256="zz" * 32)


def test_run_context_duplicate_artifact_ids_rejected() -> None:
    a = ArtifactRef(artifact_id="a1", kind="backtest", ref="file:///x")
    with pytest.raises(ValidationError):
        ctx(artifacts=(a, a))


def test_l4_requires_recorded_human_approval() -> None:
    with pytest.raises(ValidationError, match="l4_requires_recorded_human_approval"):
        ctx(autonomy_level="L4")
    ok = ctx(
        autonomy_level="L4",
        approval_state="APPROVED",
        approved_by="owner",
        approval_ref="decision-7",
    )
    assert ok.autonomy_level == "L4"


def test_approved_state_requires_approver() -> None:
    with pytest.raises(ValidationError, match="approved_state_requires_approver"):
        ctx(approval_state="APPROVED")


def test_parent_run_id_accepted_for_two_level_hierarchy() -> None:
    c = ctx(parent_run_id="orch-9")
    assert c.parent_run_id == "orch-9"


# ---------------------------------------------------------------------------
# Autonomy ceiling — 03 §Autonomy levels
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("level", "ceiling", "ok"),
    [("L0", "L1", True), ("L2", "L2", True), ("L2", "L1", False), ("L3", "L4", True)],
)
def test_autonomy_ceiling_guard(level: str, ceiling: str, ok: bool) -> None:
    c = ctx(autonomy_level=level)  # type: ignore[arg-type]
    if ok:
        assert_autonomy_permitted(c, ceiling)  # type: ignore[arg-type]
    else:
        with pytest.raises(ValueError, match="autonomy_level_exceeds_declared_ceiling"):
            assert_autonomy_permitted(c, ceiling)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RunProvenance + completeness gate — 03 §Run provenance
# ---------------------------------------------------------------------------


def test_provenance_code_commit_shape() -> None:
    assert prov(code_commit=COMMIT).code_commit == COMMIT
    with pytest.raises(ValidationError):
        prov(code_commit="nothex")
    with pytest.raises(ValidationError):
        prov(code_commit="b" * 39)


def test_provenance_interval_both_or_none_and_order() -> None:
    with pytest.raises(ValidationError):
        prov(started_at_utc=T0, finished_at_utc=None)
    with pytest.raises(ValidationError):
        prov(started_at_utc=T1, finished_at_utc=T0)


def test_bind_provenance_run_id_mismatch() -> None:
    bind_provenance(ctx(), prov())
    with pytest.raises(ValueError, match="provenance_run_id_mismatch"):
        bind_provenance(ctx(), prov(run_id="run-2"))
    with pytest.raises(ValueError, match="provenance_parent_run_id_mismatch"):
        bind_provenance(ctx(parent_run_id="p1"), prov(parent_run_id="p2"))


def test_missing_required_provenance_blocks_acceptance() -> None:
    incomplete = prov(policy_version=None, started_at_utc=None, finished_at_utc=None)
    missing = missing_required_provenance(ctx(), incomplete)
    assert set(missing) == {"policy_version", "started_at_utc", "finished_at_utc"}
    assert not provenance_complete(ctx(), incomplete)
    assert provenance_complete(ctx(), prov())
    with pytest.raises(ValueError):
        bind_provenance(ctx(), prov(run_id="other"))
    assert missing_required_provenance(ctx(), prov(run_id="other")) == ("run_id_binding",)


def test_missing_required_provenance_extended_per_run_kind() -> None:
    missing = missing_required_provenance(
        ctx(), prov(), additionally_required=("dataset_version", "evaluation_version")
    )
    assert set(missing) == {"dataset_version", "evaluation_version"}


# ---------------------------------------------------------------------------
# Episodic memory — immutable research evidence (D-AI-28)
# ---------------------------------------------------------------------------


def epi(record_id: str = "e1", **over: object) -> EpisodicMemoryRecord:
    base = dict(
        record_id=record_id,
        run_id="run-1",
        memory_kind="RESEARCH_RUN_EVIDENCE",
        stored_at_utc=T0,
        payload_ref="artifact://run-1/evidence.json",
        payload_sha256=SHA,
    )
    base.update(over)
    return EpisodicMemoryRecord(**base)  # type: ignore[arg-type]


def test_episodic_record_requires_run_id_and_frozen() -> None:
    with pytest.raises(ValidationError):
        epi(run_id="")
    r = epi()
    with pytest.raises(ValidationError):
        r.summary = "mutated"  # type: ignore[misc]


def test_episodic_append_and_idempotent_reappend() -> None:
    log = EpisodicMemoryLog().append(epi())
    again = log.append(epi())
    assert again is log  # idempotent no-op returns the same log
    assert len(log.records) == 1


def test_episodic_conflict_rejected_history_never_rewritten() -> None:
    log = EpisodicMemoryLog().append(epi())
    with pytest.raises(ValueError, match="episodic_record_conflict"):
        log.append(epi(summary="different content"))
    assert len(log.records) == 1
    assert log.records[0].summary == ""


def test_episodic_log_has_no_update_or_delete_path() -> None:
    log = EpisodicMemoryLog().append(epi())
    public = {name for name in dir(log) if not name.startswith("_")}
    assert "append" in public and "get" in public and "history_for_run" in public
    for forbidden in ("update", "remove", "delete", "pop", "clear", "rewrite"):
        assert forbidden not in public


def test_episodic_history_traceable_to_run_id() -> None:
    log = EpisodicMemoryLog().append(epi("e1")).append(epi("e2", run_id="run-2"))
    assert [r.record_id for r in log.history_for_run("run-1")] == ["e1"]
    assert [r.record_id for r in log.history_for_run("run-2")] == ["e2"]


def test_episodic_payload_sha256_shape() -> None:
    with pytest.raises(ValidationError):
        epi(payload_sha256="SHORT")


# ---------------------------------------------------------------------------
# Semantic memory — curated and versioned (D-AI-28)
# ---------------------------------------------------------------------------


def sem(version: int = 1, entry_id: str = "s1", **over: object) -> SemanticMemoryEntry:
    base = dict(
        entry_id=entry_id,
        version=version,
        supersedes_version=None if version == 1 else version - 1,
        statement="Regime classification X correlates with money-flow shift Y.",
        knowledge_ref="research://findings/f1",
        curated_by="deterministic-rule:r1",
        curation_basis="DETERMINISTIC_RULE",
        created_at_utc=T1,
    )
    base.update(over)
    return SemanticMemoryEntry(**base)  # type: ignore[arg-type]


def test_semantic_version_one_must_not_supersede() -> None:
    with pytest.raises(ValidationError, match="version_one_must_not_supersede"):
        sem(version=1, supersedes_version=0)


def test_semantic_later_version_requires_parent() -> None:
    with pytest.raises(ValidationError, match="later_version_requires_superseded_version"):
        sem(version=2, supersedes_version=None)
    with pytest.raises(ValidationError, match="superseded_version_must_be_earlier"):
        sem(version=2, supersedes_version=3)


def test_semantic_curation_frozen() -> None:
    e = sem()
    with pytest.raises(ValidationError):
        e.statement = "mutated"  # type: ignore[misc]


def test_semantic_store_register_and_supersede_chain() -> None:
    store = SemanticMemoryStore().register(sem(version=1))
    assert store.latest("s1") is not None and store.latest("s1").version == 1
    store2 = store.register(sem(version=2))
    latest = store2.latest("s1")
    assert latest is not None and latest.version == 2
    history = store2.history("s1")
    assert [e.version for e in history] == [1, 2]
    assert history[0].status == "SUPERSEDED"
    assert history[1].status == "ACTIVE"
    # The superseded version's content is unchanged (history never rewritten).
    assert history[0].statement == history[1].statement


def test_semantic_store_rejects_bad_chains() -> None:
    store = SemanticMemoryStore().register(sem(version=1))
    with pytest.raises(ValueError, match="semantic_entry_version_not_increasing"):
        store.register(sem(version=1))
    with pytest.raises(ValueError, match="first_registered_version_must_be_one"):
        SemanticMemoryStore().register(sem(version=2))
    with pytest.raises(ValueError, match="semantic_supersession_parent_mismatch"):
        # Model-valid entry (2 < 3) whose parent is not the store's current
        # version (1) — the store-level chain guard is what must fire.
        store.register(sem(version=3, supersedes_version=2))


def test_semantic_history_preserved_after_two_supersedations() -> None:
    store = (
        SemanticMemoryStore()
        .register(sem(version=1))
        .register(sem(version=2))
        .register(sem(version=3))
    )
    assert [e.version for e in store.history("s1")] == [1, 2, 3]
    assert store.history("s1")[-1].status == "ACTIVE"


# ---------------------------------------------------------------------------
# Closed memory-operation set — 03 §Memory (no production mutation possible)
# ---------------------------------------------------------------------------


def test_memory_operation_kind_cannot_express_production_mutation() -> None:
    from typing import get_args

    allowed = set(get_args(MemoryOperationKind))
    assert allowed == {"APPEND_EPISODIC", "REGISTER_SEMANTIC", "SUPERSEDE_SEMANTIC"}
    assert not any("PRODUCTION" in op or "MUTATE" in op or "DEPLOY" in op for op in allowed)


def test_memory_records_carry_schema_version() -> None:
    assert epi().schema_version
    assert sem().schema_version
    assert ctx().schema_version
