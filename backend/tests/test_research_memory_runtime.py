"""AI-3 research-memory REAL runtime integration (owner directive
2026-11-08 §3: «اتصال واقعی و تست runtime الزامی است»).

Proves the DURABLE path end-to-end through the REAL running application:
factory default = SQLite/WAL + AES-256-GCM carrier + DURABLE tamper-evident
audit trail; every HTTP operation lands an audit row; ciphertext at rest
carries no plaintext; restart recovery preserves both carriers; the audit
gate closes fail-closed on tamper; the key-missing posture refuses typed;
D5 verified backup works over the live surface; no purge path exists.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.research_memory_service import (
    get_research_memory_service,
    reset_research_memory_service_cache,
)

client = TestClient(app, client=("ai3-runtime-memory", 12410))


def _reset_service_with_env():
    """In-test env change: the cached settings object must be rebuilt (the
    conftest autouse fixture cannot see a mid-test monkeypatch)."""
    get_settings.cache_clear()
    reset_research_memory_service_cache()

T0 = datetime(2026, 11, 8, 10, 0, 0, tzinfo=timezone.utc)


def _episodic_payload(entry_id: str = "EP-1", run_id: str = "run-ai3-1") -> dict:
    return {
        "entry_id": entry_id,
        "run_id": run_id,
        "run_kind": "AI2_RESEARCH_RUN",
        "artifact": {
            "artifact_id": f"{run_id}:s1",
            "kind": "aima.hypothesis_draft",
            "ref": f"inmem://aima/{run_id}/s1.json",
            "sha256": "ab" * 32,
        },
        "input_snapshot_sha256": "cd" * 32,
        "trust_state": "SYNTHETIC_OR_PAPER",
        "policy_version": "radar-policy-1",
        "information_cutoff_utc": T0.isoformat().replace("+00:00", "Z"),
        "recorded_at_utc": T0.isoformat().replace("+00:00", "Z"),
        "notes": "runtime integration test record",
    }


def _lesson_payload(lesson_id: str = "LES-1", version: int = 1) -> dict:
    return {
        "lesson_id": lesson_id,
        "version": version,
        "supersedes_version": None if version == 1 else version - 1,
        "statement": "الگو وارونگی در نمادهای SYNTHETIC با برچسب اعتماد پایین تأیید نشد — اگر تکرار شود ابطال می‌شود",
        "source_artifact_ids": ["EP-1"],
        "curated_by": "runtime",
        "curation_basis": "DETERMINISTIC_RULE",
        "created_at_utc": T0.isoformat().replace("+00:00", "Z"),
        "run_id": "run-ai3-1",
    }


# ---------------------------------------------------------------------------
# Factory / posture (durable default, honest refusal posture)
# ---------------------------------------------------------------------------


def test_posture_durable_default_with_env_key() -> None:
    r = client.get("/api/v10/memory/posture")
    assert r.status_code == 200
    body = r.json()
    posture = body["posture"]
    assert posture["ok"] is True
    assert posture["backend"] == "sqlite"
    assert posture["persistence_durable"] is True
    assert posture["audit_trail_durable"] is True
    assert posture["encryption_at_rest"] is True  # D4
    assert posture["data_trust_label"] == "SYNTHETIC_OR_PAPER"
    assert body["disclosures"]["no_purge_path"]


def test_key_missing_fail_closed_refusal_posture(tmp_path, monkeypatch) -> None:
    from app.services.research_memory_service import (
        reset_research_memory_service_cache,
    )

    monkeypatch.delenv("RADAR_RESEARCH_MEMORY_KEY", raising=False)
    monkeypatch.delenv("RESEARCH_MEMORY_DB_DIR", raising=False)
    monkeypatch.setenv("RESEARCH_MEMORY_DB_DIR", str(tmp_path / "rm"))
    _reset_service_with_env()
    try:
        service = get_research_memory_service()
        # In a keyless environment the surface refuses typed — never an
        # unencrypted or silent in-memory downgrade.
        if service.refused_reason is None:
            pytest.skip("OS keyring backend available in this environment")
        assert service.refused_reason == "research_memory_key_invalid"
        r = client.post("/api/v10/memory/episodic", json={"entry": _episodic_payload()})
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "research_memory_key_invalid"
    finally:
        get_settings.cache_clear()
        reset_research_memory_service_cache()


# ---------------------------------------------------------------------------
# Real HTTP cycle: append → audit row → read → integrity → backup
# ---------------------------------------------------------------------------


def test_episodic_append_lands_audit_row_and_is_readable() -> None:
    payload = _episodic_payload()
    r = client.post("/api/v10/memory/episodic", json={"entry": payload})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # the audited wrapper recorded the write in the DURABLE chain
    audit = client.get("/api/v10/memory/audit").json()
    assert audit["chain"]["durable"] is True
    ops = [e["operation"] for e in audit["entries"]]
    assert "EPISODIC_APPEND" in ops
    appends = [e for e in audit["entries"] if e["operation"] == "EPISODIC_APPEND"]
    assert appends[-1]["outcome"] == "OK"
    assert appends[-1]["object_ref"] == "EP-1"
    # refs only — never content (no notes body in the audit row)
    assert "runtime integration test record" not in json.dumps(audit)

    # readable through the real surface
    got = client.get("/api/v10/memory/episodic/EP-1").json()
    assert got["found"] is True
    assert got["entry"]["entry_id"] == "EP-1"
    by_run = client.get("/api/v10/memory/episodic/run/run-ai3-1").json()
    assert by_run["count"] == 1


def test_conflicting_episodic_rewrite_refused_and_audited() -> None:
    r1 = client.post("/api/v10/memory/episodic", json={"entry": _episodic_payload()})
    assert r1.status_code == 200
    conflicting = _episodic_payload()
    conflicting["notes"] = "different content under the same id"
    r2 = client.post("/api/v10/memory/episodic", json={"entry": conflicting})
    assert r2.status_code == 422
    assert r2.json()["detail"]["error"] == "episodic_append_refused"
    audit = client.get("/api/v10/memory/audit").json()
    refused = [e for e in audit["entries"] if e["outcome"] == "REFUSED"]
    assert refused, "the refusal must land as an honest REFUSED audit row"
    assert refused[-1]["refusal_reason"]


def test_lesson_register_version_chain_guards_are_honest() -> None:
    client.post("/api/v10/memory/episodic", json={"entry": _episodic_payload()})
    ok = client.post("/api/v10/memory/lessons", json={"lesson": _lesson_payload()})
    assert ok.status_code == 200
    # the version-chain guard is the contract's own: a duplicate first
    # version is refused (never silently overwritten)
    dup = _lesson_payload("LES-1", version=1)
    rd = client.post("/api/v10/memory/lessons", json={"lesson": dup})
    assert rd.status_code == 422
    assert rd.json()["detail"]["error"] == "lesson_register_refused"
    # and a successor must name its parent version (no orphan versions);
    # that guard lives in the MODEL (superseded_version must be earlier), so
    # the refusal is the payload-validation code
    orphan = _lesson_payload("LES-1", version=2)
    orphan["supersedes_version"] = 7
    ro = client.post("/api/v10/memory/lessons", json={"lesson": orphan})
    assert ro.status_code == 422
    assert ro.json()["detail"]["error"] == "lesson_payload_invalid"
    # the store-level refusal landed as an honest REFUSED audit row (the
    # model-level one is refused before the audited wrapper is reached)
    audit = client.get("/api/v10/memory/audit").json()
    refused = [e for e in audit["entries"] if e["outcome"] == "REFUSED"]
    assert len(refused) == 1 and refused[-1]["refusal_reason"] == "lesson_version_not_increasing"
    got = client.get("/api/v10/memory/lessons/LES-1").json()
    assert got["found"] is True and got["history_count"] == 1


def test_integrity_endpoint_verdict_and_audit_chain() -> None:
    client.post("/api/v10/memory/episodic", json={"entry": _episodic_payload()})
    r = client.get("/api/v10/memory/integrity").json()
    assert r["ok"] is True
    assert r["integrity"]["verify_ok"] is True
    assert r["audit_chain"]["verdict"] == "INTACT"
    assert r["audit_chain"]["first_broken_sequence"] is None


def test_backup_endpoint_writes_verified_parts() -> None:
    client.post("/api/v10/memory/episodic", json={"entry": _episodic_payload()})
    r = client.post("/api/v10/memory/backup")
    assert r.status_code == 200
    backup = r.json()["backup"]
    assert backup["verified"] is True
    parts = backup["parts"]
    assert set(parts) == {"memory_store", "audit_trail"}
    for part in parts.values():
        assert len(part["sha256"]) == 64
        assert Path(part["path"]).exists()
        assert part["byte_size"] > 0


# ---------------------------------------------------------------------------
# Restart recovery + ciphertext-at-rest + tamper closed gate
# ---------------------------------------------------------------------------


def test_restart_recovery_preserves_content_and_audit(tmp_path, monkeypatch) -> None:
    from app.services.research_memory_service import (
        reset_research_memory_service_cache,
    )

    rdir = tmp_path / "rm_restart"
    monkeypatch.setenv("RESEARCH_MEMORY_DB_DIR", str(rdir))
    _reset_service_with_env()
    try:
        payload = _episodic_payload("EP-RESTART", "run-restart")
        r = client.post("/api/v10/memory/episodic", json={"entry": payload})
        assert r.status_code == 200
        before = client.get("/api/v10/memory/audit").json()
        head_before = before["chain"]["head_digest"]

        # "restart": drop the cached service and re-open from disk
        reset_research_memory_service_cache()
        after = client.get("/api/v10/memory/audit").json()
        assert after["chain"]["head_digest"] == head_before
        got = client.get("/api/v10/memory/episodic/EP-RESTART").json()
        assert got["found"] is True
        integ = client.get("/api/v10/memory/integrity").json()
        assert integ["audit_chain"]["verdict"] == "INTACT"
        assert integ["integrity"]["entry_count"] >= 1
    finally:
        get_settings.cache_clear()
        reset_research_memory_service_cache()


def test_ciphertext_at_rest_contains_no_plaintext(tmp_path, monkeypatch) -> None:
    from app.services.research_memory_service import (
        reset_research_memory_service_cache,
    )

    rdir = tmp_path / "rm_crypto"
    monkeypatch.setenv("RESEARCH_MEMORY_DB_DIR", str(rdir))
    _reset_service_with_env()
    try:
        marker = "UNIQUE-PLAINTEXT-MARKER-4711"
        payload = _episodic_payload("EP-CRYPTO", "run-crypto")
        payload["notes"] = marker
        assert client.post("/api/v10/memory/episodic", json={"entry": payload}).status_code == 200
        # scan EVERY file of the carrier for the plaintext marker (D4)
        for f in rdir.rglob("*"):
            if f.is_file():
                assert marker.encode() not in f.read_bytes(), (
                    f"plaintext leaked into {f.name}"
                )
    finally:
        get_settings.cache_clear()
        reset_research_memory_service_cache()


def test_audit_chain_tamper_closes_gate_fail_closed(tmp_path, monkeypatch) -> None:
    from app.services.research_memory_service import (
        reset_research_memory_service_cache,
    )

    rdir = tmp_path / "rm_tamper"
    monkeypatch.setenv("RESEARCH_MEMORY_DB_DIR", str(rdir))
    _reset_service_with_env()
    try:
        assert client.post(
            "/api/v10/memory/episodic", json={"entry": _episodic_payload("EP-T1", "run-t1")}
        ).status_code == 200
        service = get_research_memory_service()
        audit_db = service.audit_db_path
        # storage-layer attacker: flip the digest column of the first entry
        conn = sqlite3.connect(audit_db)
        conn.execute("UPDATE audit_entries SET row_digest=? WHERE sequence=1", ("e" * 64,))
        conn.commit()
        conn.close()
        # a NEW service instance over the tampered carrier opens CLOSED
        reset_research_memory_service_cache()
        service2 = get_research_memory_service()
        # the tampered FIRST row is caught at open (row-digest check) — the
        # factory surfaces the typed corruption refusal honestly
        assert service2.refused_reason is not None
        r = client.get("/api/v10/memory/audit")
        assert r.status_code == 200  # the audit VIEW itself stays readable
        assert r.json()["count"] == 0  # nothing is served from a broken chain
    finally:
        get_settings.cache_clear()
        reset_research_memory_service_cache()


# ---------------------------------------------------------------------------
# Governance: no purge path in the runtime service
# ---------------------------------------------------------------------------


def test_service_module_has_no_delete_or_purge_path() -> None:
    import ast

    src = Path("app/services/research_memory_service.py").read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            up = node.value.upper()
            assert "DELETE FROM" not in up
            assert "DROP TABLE" not in up
    # the HTTP surface exposes no delete/purge route
    route_paths = [getattr(r, "path", "") for r in app.routes]
    memory_routes = [p for p in route_paths if p.startswith("/api/v10/memory")]
    assert memory_routes
    assert not any(p.endswith("/purge") or p.endswith("/delete") for p in memory_routes)
