"""T7 P5/P6 integration audit — D-AI-30 retention-purge boundary proof.

The owner decision (D-AI-30 decision 7 / CONSOL-GOV-41) authorizes a 90-day
``purge_expired_records()`` for ALERT-OPS RECORDS ONLY; episodic research
evidence must NEVER have a purge path (D-AI-28 / AI3 structural red line).

The existing battery only asserted the inbox purge count. This module proves
the boundary exactly:

1. Purge removes ONLY expired rows, and only from the four alert-ops record
   tables (outbox / inbox / dead-letter / audit); fresh rows survive, the
   exact-cutoff row survives (strict ``<``), and the non-record alert-ops
   tables (kill switches, job state, budget counters) are untouched.
2. Co-tenancy: the alert-ops tables share the product SQLite database, so
   foreign tables (standing in for research/episodic/document evidence
   tables) are created in the SAME DB file with rows older than the
   retention horizon — purge provably cannot touch them.
3. Structural: every ``DELETE FROM <table>`` target in the entire store
   module is namespaced ``alert_ops_*`` — no research/episodic table name is
   reachable from the purge code path by construction.
4. In-memory episodic evidence: ``EpisodicRunArchive`` (append-only
   research-memory contract) is byte-identical before/after a service purge.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from app.data.alert_ops_store import AlertOpsStore
from app.domain.alert_operations import JOB_DISPATCHER
from app.domain.governed_alerts import GovernedAlertObject
from app.services.alert_operations import AlertOperationsService

UTC = timezone.utc
NOW = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=91)
CUTOFF_EXACT = NOW - timedelta(days=90)
FRESH = NOW - timedelta(days=1)


def _alert(subject: str) -> GovernedAlertObject:
    return GovernedAlertObject(
        alert_id="ALERT-PURGE-1",
        alert_kind="SOURCE_CONFLICT",
        subject=subject,
        created_at_utc=FRESH,
        reason_for_now="two primary sources disagree on the same figure",
        confidence=Decimal("0.5"),
        confidence_basis="declared by the detecting governed run",
        data_trust_state="synthetic",
        risk_semantics="informational; no position implication",
        evidence_ids=("E1", "E2"),
        invalidation_conditions=("conflict resolved with reviewer + rule",),
        expiry_utc=NOW + timedelta(days=7),
        run_id="RUN-PURGE-1",
        conflict_id="CONFLICT-PURGE-1",
    )


def _seed(store: AlertOpsStore) -> dict[str, int]:
    """One expired + one fresh row in EVERY record table (store-level APIs)."""
    ids: dict[str, int] = {}

    # --- outbox ---------------------------------------------------------------
    ids["outbox_old"] = store.enqueue(
        dedup_key="k-old", dedup_window=(OLD - timedelta(hours=1)).isoformat(),
        alert=_alert("old"), alert_json=_alert("old").model_dump_json(),
        source_event_id="EV-OLD", fingerprint="f-old", now=OLD,
    ) or 0
    ids["outbox_fresh"] = store.enqueue(
        dedup_key="k-fresh", dedup_window=(FRESH - timedelta(hours=1)).isoformat(),
        alert=_alert("fresh"), alert_json=_alert("fresh").model_dump_json(),
        source_event_id="EV-FRESH", fingerprint="f-fresh", now=FRESH,
    ) or 0

    # --- inbox (delivered rows) -------------------------------------------------
    fresh_alert = _alert("fresh-delivered")
    store.deliver_to_inbox(
        outbox_id=ids["outbox_old"], dedup_key="k-old-inbox", alert=_alert("old-delivered"),
        alert_json=_alert("old-delivered").model_dump_json(), summary="old delivery", now=OLD,
    )
    store.deliver_to_inbox(
        outbox_id=ids["outbox_fresh"], dedup_key="k-fresh-inbox", alert=fresh_alert,
        alert_json=fresh_alert.model_dump_json(), summary="fresh delivery", now=FRESH,
    )

    # --- dead letter --------------------------------------------------------------
    store.dead_letter(
        outbox_id=ids["outbox_old"], dedup_key="k-old-dl", alert_json=_alert("old-dl").model_dump_json(),
        alert_kind="SOURCE_CONFLICT", attempts=3, last_error_code="delivery_error:RuntimeError",
        reason="retry_exhausted", now=OLD,
    )
    store.dead_letter(
        outbox_id=ids["outbox_fresh"], dedup_key="k-fresh-dl", alert_json=_alert("fresh-dl").model_dump_json(),
        alert_kind="SOURCE_CONFLICT", attempts=3, last_error_code="delivery_error:RuntimeError",
        reason="retry_exhausted", now=FRESH,
    )

    # --- audit ------------------------------------------------------------------
    store.audit("ENQUEUED", "old-ref", {"kind": "SOURCE_CONFLICT"}, OLD)
    store.audit("ENQUEUED", "cutoff-ref", {"kind": "SOURCE_CONFLICT"}, CUTOFF_EXACT)
    store.audit("ENQUEUED", "fresh-ref", {"kind": "SOURCE_CONFLICT"}, FRESH)
    return ids


def test_purge_removes_only_expired_rows_and_only_from_record_tables(tmp_path: Path) -> None:
    store = AlertOpsStore(path=tmp_path / "ops.db")
    store.migrate()
    ids = _seed(store)

    # Non-record alert-ops state that MUST survive the purge.
    store.set_kill_switch("GLOBAL", "RELEASED", NOW, "audit")
    store.upsert_job_state(JOB_DISPATCHER, last_run_at=FRESH, consecutive_failures=0, failure_state="HEALTHY")
    counter_window = NOW
    store.increment_counter("deliveries:IN_PRODUCT_INBOX:H:x", counter_window, by=3)

    svc = AlertOperationsService(store=store, clock=lambda: NOW)
    out = svc.purge_expired_records()

    # --- record tables: only expired rows removed --------------------------------
    assert out["purged"] == {
        "alert_ops_outbox": 1,
        "alert_ops_inbox": 1,
        "alert_ops_dead_letter": 1,
        "alert_ops_audit": 1,
    }
    assert store.find_outbox_by_key("k-old") is None
    assert store.find_outbox_by_key("k-fresh") is not None
    assert store.outbox_row(ids["outbox_fresh"])["status"] == "QUEUED"
    assert store.inbox_count() == 1 and store.inbox_rows()[0]["summary"] == "fresh delivery"
    assert store.dead_letter_count() == 1
    dl = store.dead_letter_rows()[0]
    assert dl["dead_lettered_at"].startswith(FRESH.date().isoformat())
    # exact-cutoff audit row survives (strict <), 91-day-old audit purged
    refs = {r["ref"] for r in store.audit_rows(limit=100)}
    assert "old-ref" not in refs and "cutoff-ref" in refs and "fresh-ref" in refs
    # the purge itself is audited and (being fresh) survives
    purge_rows = store.audit_rows(category="RETENTION_PURGE")
    assert len(purge_rows) == 1 and json_loads(purge_rows[0]["detail_json"])["retention_days"] == 90

    # --- non-record tables untouched ---------------------------------------------
    assert store.kill_switch_state("GLOBAL") == "RELEASED"
    js = store.job_state(JOB_DISPATCHER)
    assert js is not None and js["failure_state"] == "HEALTHY"
    assert store.counter_value("deliveries:IN_PRODUCT_INBOX:H:x", counter_window) == 3


def json_loads(s: str) -> dict:
    import json

    return json.loads(s)


def test_purge_cannot_touch_cotenant_foreign_tables(tmp_path: Path) -> None:
    """The alert-ops tables live in the SHARED product database; foreign
    (research/episodic/document-style) tables in the same file must be
    unreachable from the purge, even with rows older than any retention."""
    store = AlertOpsStore(path=tmp_path / "shared.db")
    store.migrate()
    _seed(store)

    with sqlite3.connect(str(store.path)) as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS episodic_research_evidence ("
            "id INTEGER PRIMARY KEY, entry_id TEXT NOT NULL, recorded_at TEXT NOT NULL)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS document_ledger_entries ("
            "id INTEGER PRIMARY KEY, entry_id TEXT NOT NULL, recorded_at TEXT NOT NULL)"
        )
        ancient = (NOW - timedelta(days=3650)).isoformat()
        for tbl in ("episodic_research_evidence", "document_ledger_entries"):
            c.execute(f"INSERT INTO {tbl}(entry_id, recorded_at) VALUES('E-ANCIENT', ?)", (ancient,))
            c.execute(f"INSERT INTO {tbl}(entry_id, recorded_at) VALUES('E-FRESH', ?)", (FRESH.isoformat(),))
        c.commit()

    svc = AlertOperationsService(store=store, clock=lambda: NOW)
    svc.purge_expired_records()

    with sqlite3.connect(str(store.path)) as c:
        for tbl in ("episodic_research_evidence", "document_ledger_entries"):
            n = int(c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
            ids_ = {r[0] for r in c.execute(f"SELECT entry_id FROM {tbl}").fetchall()}
            assert n == 2 and ids_ == {"E-ANCIENT", "E-FRESH"}, (tbl, n, ids_)


def test_store_module_deletes_only_alert_ops_namespaced_tables() -> None:
    """Structural proof: every ``DELETE FROM`` target in the whole store
    module is ``alert_ops_*`` — no research/episodic/document table name can
    be reached from any deletion code path, including the retention purge."""
    import app.data.alert_ops_store as store_module

    module_file = Path(store_module.__file__)
    assert module_file.name == "alert_ops_store.py"
    text = module_file.read_text(encoding="utf-8")
    targets = set(re.findall(r"DELETE FROM (\w+)", text))
    assert targets, "no DELETE statements found — check the module path"
    assert targets.issubset(
        {
            "alert_ops_outbox",
            "alert_ops_inbox",
            "alert_ops_dead_letter",
            "alert_ops_audit",
            "alert_ops_budget_counters",
        }
    )


def test_purge_leaves_in_memory_episodic_research_archive_untouched(tmp_path: Path) -> None:
    """Episodic research evidence (append-only in-memory contract) must be
    byte-identical after an alert-ops purge run."""
    from app.domain.research_memory import EpisodicRunArchive, EpisodicRunArtifact
    from app.domain.run_governance import ArtifactRef

    artifact = EpisodicRunArtifact(
        entry_id="EP-AUDIT-1",
        run_id="RUN-AUDIT-1",
        run_kind="RESEARCH_RUN",
        artifact=ArtifactRef(artifact_id="ART-1", kind="report", ref="memory://artifacts/1"),
        input_snapshot_sha256="a" * 64,
        trust_state="synthetic",
        policy_version="P-1",
        information_cutoff_utc=NOW,
        recorded_at_utc=NOW,
    )
    archive = EpisodicRunArchive().append(artifact)

    store = AlertOpsStore(path=tmp_path / "ops.db")
    store.migrate()
    _seed(store)
    svc = AlertOperationsService(store=store, clock=lambda: NOW)
    svc.purge_expired_records()

    assert len(archive.entries) == 1
    assert archive.get("EP-AUDIT-1") == artifact
