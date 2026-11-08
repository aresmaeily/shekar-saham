"""2026-11-08 owner directive (§4 Multi-Agent UI): per-step artifact CONTENT
viewers — the runtime threads the executors' bounded content payloads to the
API (server-provided only), keyed by step, surfaced through the REAL running
app; determinism of content digests pinned; failed branches never carry
content.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, client=("aima-contents", 12412))


def test_orchestrate_surfaces_per_step_artifact_contents() -> None:
    r = client.post("/api/v10/aima/orchestrate", json={"question": "آیا شاخص کل در فاز صعودی است؟"})
    assert r.status_code == 200
    body = r.json()
    contents = body.get("artifact_contents")
    assert isinstance(contents, dict)
    # all three shipped steps carry their bounded server-provided content
    assert set(contents) == {"s1_hypothesis", "s2_interpretation", "s3_challenge"}
    for step_id, wrap in contents.items():
        assert wrap["content"], f"{step_id} content must be non-empty"
        art = next((s.get("artifact") for s in body["steps"] if s["step_id"] == step_id), None)
        assert art is not None, "content is only collected for artifact-first successes"
        assert wrap["artifact_id"] == art["artifact_id"]
    # the content itself is exactly what the executors produced
    drafts = contents["s1_hypothesis"]["content"]["drafts"]
    assert isinstance(drafts, list) and len(drafts) == 2
    assert all(d["preregistered"] is True for d in drafts)
    readings = contents["s2_interpretation"]["content"]["readings"]
    assert isinstance(readings, list) and readings
    challenges = contents["s3_challenge"]["content"]
    assert "duplicate_groups" in challenges and "challenges" in challenges


def test_artifact_content_deterministic_across_runs() -> None:
    import hashlib

    def content_digest_of(question):
        body = client.post(
            "/api/v10/aima/orchestrate", json={"question": question}
        ).json()
        # CONTENT only (artifact_id legitimately carries per-run identity;
        # the run-INDEPENDENT content digest is the artifact sha256, pinned
        # by the WP-C suite) — the deterministic claim is about the payload.
        contents = {
            step: wrap["content"] for step, wrap in body["artifact_contents"].items()
        }
        canon = json.dumps(contents, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    d1 = content_digest_of("پرسش قطعی برای تعیین پایداری محتوا")
    d2 = content_digest_of("پرسش قطعی برای تعیین پایداری محتوا")
    assert d1 == d2  # content is deterministic for the same question


def test_failed_branch_never_carries_content() -> None:
    # an empty question is refused before dispatch (typed 422) — nothing to
    # surface; this pins that content collection only happens for real runs
    r = client.post("/api/v10/aima/orchestrate", json={"question": "  "})
    assert r.status_code == 422
    assert "artifact_contents" not in (r.json().get("detail") or {})
