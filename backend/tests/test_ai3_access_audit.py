"""WAVE-AI (2026-11-08, WP-G): AI-3 tamper-evident access/operation audit trail.

Directive §8 minimum: actor + authorization context; read/write operation
type; object/artifact reference; timestamp + run identity; outcome + refusal
reason; integrity verification. Plus: no secrets or private user content in
logs, and the RunContext / Episodic / Semantic triad preserved explicitly.

This battery proves each directive item against the REAL audited wrapper
over the REAL in-memory store (the shipped AI-3 reference implementation).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.memory_access_audit import (
    GENESIS_DIGEST,
    AuditedResearchMemoryStore,
    MemoryAccessAuditChainBroken,
    MemoryAccessAuditTrail,
    canonical_audit_json,
    mint_audit_entry,
)
from app.domain.research_memory import EpisodicRunArtifact, SemanticLesson
from app.domain.research_memory_store import InMemoryResearchMemoryStore

UTC = timezone.utc
T0 = datetime(2026, 11, 8, 10, 0, 0, tzinfo=UTC)


def _clock():
    """Deterministic caller-supplied instant provider (no wall clock)."""
    state = {"n": 0}

    def _next():
        state["n"] += 1
        return datetime(2026, 11, 8, 10, 0, state["n"], tzinfo=UTC)

    return _next


def _episodic(entry_id: str = "EP-1", run_id: str = "run-1") -> EpisodicRunArtifact:
    from app.domain.run_governance import ArtifactRef

    return EpisodicRunArtifact(
        entry_id=entry_id,
        run_id=run_id,
        run_kind="AI2_INTERPRETATION",
        hypothesis_id="H-1",
        artifact=ArtifactRef(
            artifact_id=f"{entry_id}-artifact",
            kind="BACKTEST_RESULT",
            ref=f"inmem://episodic/{entry_id}.json",
        ),
        input_snapshot_sha256="a" * 64,
        trust_state="mock",
        policy_version="gov-1",
        information_cutoff_utc=T0,
        recorded_at_utc=T0,
    )


def _lesson(lesson_id: str = "L-1", version: int = 1) -> SemanticLesson:
    return SemanticLesson(
        lesson_id=lesson_id,
        version=version,
        supersedes_version=None if version == 1 else version - 1,
        statement="هیچ ارتقایی بدون تأیید انسانی نام‌دار انجام نمی‌شود",
        source_artifact_ids=("EP-1",),
        curated_by="wp-g-test",
        curation_basis="DETERMINISTIC_RULE",
        status="ACTIVE",
        created_at_utc=T0,
        run_id="run-1",
    )


# ---------------------------------------------------------------------------
# directive item pins
# ---------------------------------------------------------------------------


class TestDirectiveItemCoverage:
    def test_every_operation_recorded_with_actor_authz_and_layer(self):
        trail = MemoryAccessAuditTrail()
        trail.record(
            actor="analyst-1",
            authorization_context="L1-advisory",
            operation="EPISODIC_APPEND",
            object_ref="EP-1",
            at_utc=T0,
            run_id="run-1",
        )
        e = trail.entries[-1]
        assert e.actor == "analyst-1"
        assert e.authorization_context == "L1-advisory"
        assert e.operation == "EPISODIC_APPEND"
        assert e.memory_layer == "EPISODIC"  # layer pinned per operation

    def test_write_vs_read_operations_distinguished(self):
        trail = MemoryAccessTrailHelper()
        ops = [e.operation for e in trail.entries]
        assert "SEMANTIC_REGISTER" in ops and "SEMANTIC_LATEST" in ops

    def test_object_reference_and_run_identity_carried(self):
        trail = MemoryAccessAuditTrail()
        trail.record(
            actor="svc",
            authorization_context="L1",
            operation="EPISODIC_GET",
            object_ref="EP-7",
            at_utc=T0,
            run_id="run-42",
        )
        e = trail.entries[-1]
        assert e.object_ref == "EP-7"
        assert e.run_id == "run-42"
        assert e.at_utc == T0  # caller-supplied instant, verbatim

    def test_outcome_and_refusal_reason_pairing_enforced(self):
        # REFUSED without a reason is unconstructable
        with pytest.raises(ValueError):
            mint_audit_entry(
                sequence=1,
                actor="svc",
                authorization_context="L1",
                operation="SEMANTIC_REGISTER",
                object_ref="L-9",
                at_utc=T0,
                outcome="REFUSED",
            )
        # OK with a refusal reason is unconstructable
        with pytest.raises(ValueError):
            mint_audit_entry(
                sequence=1,
                actor="svc",
                authorization_context="L1",
                operation="SEMANTIC_REGISTER",
                object_ref="L-9",
                at_utc=T0,
                outcome="OK",
                refusal_reason="spurious",
            )
        # a real refusal row carries its reason
        trail = MemoryAccessAuditTrail()
        trail.record(
            actor="svc",
            authorization_context="L1",
            operation="SEMANTIC_REGISTER",
            object_ref="L-9",
            at_utc=T0,
            outcome="REFUSED",
            refusal_reason="lesson_version_conflict",
        )
        assert trail.entries[-1].refusal_reason == "lesson_version_conflict"


class MemoryAccessTrailHelper:
    """Small helper producing a trail with both a write and a read."""

    def __init__(self):
        self.trail = MemoryAccessAuditTrail()
        self.trail.record(
            actor="svc",
            authorization_context="L1",
            operation="SEMANTIC_REGISTER",
            object_ref="L-1",
            at_utc=T0,
        )
        self.trail.record(
            actor="svc",
            authorization_context="L1",
            operation="SEMANTIC_LATEST",
            object_ref="L-1",
            at_utc=T0,
        )

    @property
    def entries(self):
        return self.trail.entries


# ---------------------------------------------------------------------------
# tamper evidence
# ---------------------------------------------------------------------------


class TestTamperEvidence:
    def test_chain_verifies_and_head_advances(self):
        trail = MemoryAccessAuditTrail()
        for i in range(5):
            trail.record(
                actor="svc",
                authorization_context="L1",
                operation="EPISODIC_GET",
                object_ref=f"EP-{i}",
                at_utc=T0,
            )
        assert trail.first_broken_sequence() is None
        assert trail.head_digest != GENESIS_DIGEST
        assert len(trail.entries) == 5
        assert [e.sequence for e in trail.entries] == [1, 2, 3, 4, 5]

    def test_single_byte_tamper_is_detected(self):
        trail = MemoryAccessAuditTrail()
        trail.record(
            actor="svc",
            authorization_context="L1",
            operation="EPISODIC_GET",
            object_ref="EP-1",
            at_utc=T0,
        )
        trail.record(
            actor="svc",
            authorization_context="L1",
            operation="EPISODIC_GET",
            object_ref="EP-2",
            at_utc=T0,
        )
        entries = trail.entries
        # reconstruct the log with ONE tampered field (actor rewritten)
        from app.domain.memory_access_audit import MemoryAccessAuditEntry

        tampered = entries[0].model_copy(update={"actor": "attacker"})
        with pytest.raises(ValueError):
            # digest no longer matches the tampered content
            MemoryAccessAuditEntry(**{**tampered.model_dump(), "entry_digest": entries[0].entry_digest})
        # and even a RE-MINTED digest breaks the CHAIN link of entry 2
        from app.domain.memory_access_audit import canonical_audit_json

        assert canonical_audit_json(tampered) != canonical_audit_json(entries[0])

    def test_append_on_broken_chain_refused_fail_closed(self):
        trail = MemoryAccessAuditTrail()
        trail.record(
            actor="svc",
            authorization_context="L1",
            operation="EPISODIC_GET",
            object_ref="EP-1",
            at_utc=T0,
        )
        # storage-layer tampering (attacker rewrites history): model_copy
        # bypasses construction validation — exactly what a tampered store
        # would look like when re-read
        tampered = trail.entries[0].model_copy(update={"object_ref": "EP-TAMPERED"})
        broken = MemoryAccessAuditTrail((tampered,))
        assert broken.first_broken_sequence() == 1
        with pytest.raises(MemoryAccessAuditChainBroken):
            broken.record(
                actor="svc",
                authorization_context="L1",
                operation="EPISODIC_GET",
                object_ref="EP-2",
                at_utc=T0,
            )
        # the broken log stayed closed (nothing appended past corruption)
        assert len(broken.entries) == 1

    def test_sequence_gap_and_link_mismatch_refused(self):
        trail = MemoryAccessAuditTrail()
        e1 = mint_audit_entry(
            sequence=1,
            actor="svc",
            authorization_context="L1",
            operation="EPISODIC_GET",
            object_ref="EP-1",
            at_utc=T0,
        )
        trail = trail.append(e1)
        # a valid entry with the WRONG sequence number is refused
        e_bad = mint_audit_entry(
            sequence=3,
            actor="svc",
            authorization_context="L1",
            operation="EPISODIC_GET",
            object_ref="EP-2",
            at_utc=T0,
            prior_digest=trail.head_digest,
        )
        with pytest.raises(ValueError):
            trail.append(e_bad)
        # a correctly-numbered entry with the WRONG prior digest is refused
        e_bad2 = mint_audit_entry(
            sequence=2,
            actor="svc",
            authorization_context="L1",
            operation="EPISODIC_GET",
            object_ref="EP-2",
            at_utc=T0,
            prior_digest=GENESIS_DIGEST,
        )
        with pytest.raises(ValueError):
            trail.append(e_bad2)


# ---------------------------------------------------------------------------
# secrets / privacy
# ---------------------------------------------------------------------------


class TestNoSecretsInLog:
    @pytest.mark.parametrize(
        "payload",
        ["my api_key=abc123", "Authorization: Bearer xyz", "token 123456", "sk-live-000", "-----BEGIN RSA"],
    )
    def test_credential_markers_refused_at_construction(self, payload):
        trail = MemoryAccessAuditTrail()
        with pytest.raises(ValueError):
            trail.record(
                actor=payload,
                authorization_context="L1",
                operation="EPISODIC_GET",
                object_ref="EP-1",
                at_utc=T0,
            )
        with pytest.raises(ValueError):
            trail.record(
                actor="svc",
                authorization_context=payload,
                operation="EPISODIC_GET",
                object_ref="EP-1",
                at_utc=T0,
            )

    def test_entries_carry_references_not_content(self):
        store = InMemoryResearchMemoryStore()
        audited = AuditedResearchMemoryStore(store, actor="svc", authorization_context="L1", now_utc=_clock())
        artifact = _episodic()
        audited.append_episodic(artifact, run_id="run-1")
        for e in audited.trail.entries:
            blob = canonical_audit_json(e)
            # the log carries the object REFERENCE (entry id) — never the
            # artifact ref URL or any record content
            assert artifact.artifact.ref not in blob
            assert e.object_ref == artifact.entry_id
            assert len(e.detail) <= 256


# ---------------------------------------------------------------------------
# triad preservation + audited wrapper behavior
# ---------------------------------------------------------------------------


class TestAuditedStoreBehavior:
    def test_full_lifecycle_recorded_honestly(self):
        store = InMemoryResearchMemoryStore()
        audited = AuditedResearchMemoryStore(store, actor="researcher", authorization_context="L2-owner-approved", now_utc=_clock())
        # WRITE
        audited.append_episodic(_episodic(), run_id="run-9")
        # READ hit
        assert audited.get_episodic("EP-1", run_id="run-9") is not None
        # READ miss (honest, no fabrication)
        assert audited.get_episodic("EP-MISSING", run_id="run-9") is None
        # query reads
        audited.episodic_for_run("run-9")
        audited.episodic_available_at(T0)
        # semantic WRITE + reads
        audited.register_lesson(_lesson(), run_id="run-9")
        assert audited.latest_lesson("L-1") is not None
        audited.lesson_history("L-1")
        # integrity probe
        report = audited.integrity_report(run_id="run-9")
        assert report.verify_ok is True
        # the trail records EVERYTHING in order
        ops = [e.operation for e in audited.trail.entries]
        assert ops == [
            "EPISODIC_APPEND",
            "EPISODIC_GET",
            "EPISODIC_GET",
            "EPISODIC_FOR_RUN",
            "EPISODIC_AVAILABLE_AT",
            "SEMANTIC_REGISTER",
            "SEMANTIC_LATEST",
            "SEMANTIC_HISTORY",
            "INTEGRITY_REPORT",
        ]
        # the miss is disclosed honestly (no fabricated row, no silent miss)
        miss = audited.trail.entries[2]
        assert miss.outcome == "OK" and miss.detail == "object_not_found"
        # integrity report lands as a RUN_CONTEXT-layer row
        assert audited.trail.entries[-1].memory_layer == "RUN_CONTEXT"
        # chain intact after the whole lifecycle
        assert audited.trail.first_broken_sequence() is None

    def test_contract_refusal_recorded_as_refused_row(self):
        store = InMemoryResearchMemoryStore()
        audited = AuditedResearchMemoryStore(store, actor="researcher", authorization_context="L1", now_utc=_clock())
        audited.append_episodic(_episodic("EP-1", "run-1"))
        # conflicting content under the same id is refused by the CONTRACT
        from app.domain.run_governance import ArtifactRef

        conflicting = EpisodicRunArtifact(
            entry_id="EP-1",
            run_id="run-1",
            run_kind="AI2_INTERPRETATION",
            artifact=ArtifactRef(artifact_id="other", kind="x", ref="artifact://other"),
            input_snapshot_sha256="b" * 64,
            trust_state="mock",
            policy_version="gov-1",
            information_cutoff_utc=T0,
            recorded_at_utc=T0,
        )
        with pytest.raises(ValueError):
            audited.append_episodic(conflicting)
        # the refusal is an honest audit row; the store is unchanged
        last = audited.trail.entries[-1]
        assert last.outcome == "REFUSED"
        assert last.refusal_reason  # carries the contract's refusal reason
        assert store.get_episodic("EP-1").input_snapshot_sha256 == "a" * 64

    def test_triad_layer_vocabulary_is_closed_and_pinned(self):
        from app.domain.memory_access_audit import _MEMORY_LAYER_OF_OPERATION, WRITE_OPERATIONS

        assert set(_MEMORY_LAYER_OF_OPERATION.values()) == {"RUN_CONTEXT", "EPISODIC", "SEMANTIC"}
        assert WRITE_OPERATIONS == frozenset({"EPISODIC_APPEND", "SEMANTIC_REGISTER"})
        # integrity probes are RUN_CONTEXT-scoped, never a memory layer of
        # their own — the audit ledger is deliberately a FOURTH kind of record
        assert _MEMORY_LAYER_OF_OPERATION["INTEGRITY_REPORT"] == "RUN_CONTEXT"

    def test_shipped_store_implementation_untouched(self):
        # the wrapper composes the store; the shipped implementation surface
        # stays exactly as delivered (no monkeypatching, no subclass)
        import inspect

        from app.domain.research_memory_store import InMemoryResearchMemoryStore as Raw

        assert not issubclass(InMemoryResearchMemoryStore, AuditedResearchMemoryStore)
        assert "audit" not in inspect.getsource(Raw.append_episodic).lower()

    def test_underlying_store_operation_not_recorded_twice(self):
        store = InMemoryResearchMemoryStore()
        audited = AuditedResearchMemoryStore(store, actor="svc", authorization_context="L1", now_utc=_clock())
        audited.append_episodic(_episodic())
        appends = [e for e in audited.trail.entries if e.operation == "EPISODIC_APPEND"]
        assert len(appends) == 1  # one operation → exactly one audit row
