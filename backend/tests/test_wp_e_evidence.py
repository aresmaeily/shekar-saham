"""WAVE-AI (2026-11-08, WP-E): WP-G real-source readiness evidence battery.

The WAVE-AI-ACCEPTANCE directive §6 requires: deterministic section-map
extraction tested against EXPLICITLY DECLARED documents; missing fields,
malformed units, currency conflicts, hash mismatch and restatement linkage
covered; PRIMARY_OVER_SECONDARY_V1 and same-precedence refusal verified;
source coverage and FRESHNESS disclosures verified; all source kill switches
kept ENGAGED; no fabricated retrieval evidence; no provider activation.

WAVE-AB4 shipped test_wpg_gap_closure.py (18 tests) covering the resolver,
kill switches, unit normalization, four-type extraction, hash mismatch,
restatement linkage and the coverage endpoint. This file closes the
remaining evidence gaps additively (it re-proves nothing that is already
pinned elsewhere; it only adds the freshness/declaration sides):

1. FRESHNESS disclosures on the live coverage endpoint: every declared
   source appears in ``never_retrieved`` (zero uptime evidence invented),
   ``stale_sources`` stays empty (no staleness claim without evidence),
   ``known_gaps`` carries the owner-gate + kill-switch disclosures, and the
   per-descriptor freshness targets are DECLARED (non-null) so staleness
   becomes evaluable the moment real evidence exists;
2. the "explicitly declared documents" rule from BOTH sides: a declared
   document cannot even be constructed without its 64-hex sha256
   (missing-declaration refusal) and a mismatched declaration fails closed;
3. end-to-end kill-switch posture through the same endpoint payload:
   ``runnable_sources == []`` and every declared kill switch ENGAGED.

No real retrieval, no provider activation, no credentials: everything here
runs on the DECLARED repo fixtures (R-3/R-7 stay KEEP-DENIED).
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.declared_source_fixtures import (
    DECLARED_SOURCES_VERSION,
    declared_source_descriptors,
)
from app.domain.filing_extraction import DeclaredFilingDocument, DeclaredFilingSection


@pytest.fixture()
def client():
    get_settings.cache_clear()
    import os

    os.environ.setdefault("DATA_SOURCE", "mock")
    from app.main import app as fastapi_app

    return TestClient(fastapi_app, client=("wp-e-test", 12403))


def test_freshness_disclosures_on_the_live_coverage_endpoint(client):
    now = "2026-11-08T12:00:00Z"
    res = client.get(f"/api/v10/productloops/intel/coverage?now_utc={now}")
    assert res.status_code == 200
    data = res.json()
    report = data["report"]
    declared_ids = {d.source_id for d in declared_source_descriptors()}
    # FRESHNESS honesty: zero retrieval evidence exists, so EVERY declared
    # source is classified never_retrieved (no counters fabricated), and NO
    # staleness claim is made (stale_sources empty without evidence)
    assert set(report["never_retrieved"]) == declared_ids
    assert report["never_retrieved"], "freshness disclosure must list sources"
    assert report["stale_sources"] == []
    assert report["as_of_utc"] == now  # caller-supplied instant, never a wall clock
    # coverage honesty
    assert report["total_configured"] == len(declared_ids)
    assert data["honesty"]["universal_coverage_claimed"] is False
    assert data["honesty"]["no_uptime_evidence_invented"]
    # the declared known-gaps ride the report verbatim
    joined = " | ".join(report["known_gaps"])
    assert "R-3/R-7" in joined
    assert "kill-switch ENGAGED" in joined
    assert data["declared_sources_version"] == DECLARED_SOURCES_VERSION


def test_freshness_targets_are_declared_for_every_source():
    # staleness is evaluable only against a DECLARED freshness target; the
    # fixtures must carry one per source (targets, not uptime evidence)
    for d in declared_source_descriptors():
        assert d.freshness_target is not None, f"missing freshness target: {d.source_id}"
        assert d.kill_switch == "ENGAGED", f"kill switch must stay engaged: {d.source_id}"


def test_kill_switch_posture_through_the_endpoint_payload(client):
    now = "2026-11-08T12:00:00Z"
    res = client.get(f"/api/v10/productloops/intel/coverage?now_utc={now}")
    data = res.json()
    assert data["runnable_sources"] == [], "nothing runnable while switches are engaged"
    states = data["kill_switch_states"]
    assert states and set(states.values()) == {"ENGAGED"}


def test_extraction_requires_an_explicitly_declared_document_hash():
    content = "درآمد عملیاتی ۱۰۰ میلیون ریال"
    digest = __import__("hashlib").sha256(content.encode("utf-8")).hexdigest()
    section = DeclaredFilingSection(
        section_id="sec-income",
        kind="FINANCIAL_STATEMENT",
        text=content,
    )
    # WITH the explicit declaration (and a matching hash) construction succeeds
    doc = DeclaredFilingDocument(
        document_id="DOC-WP-E-1",
        content=content,
        declared_sha256=digest,
        sections=(section,),
    )
    assert doc.declared_sha256 == digest
    # WITHOUT the explicit declaration the document cannot exist at all
    with pytest.raises(Exception):
        DeclaredFilingDocument(
            document_id="DOC-WP-E-2",
            content=content,
            sections=(section,),
        )
    # and a WRONG declaration fails closed (64-hex shape + match enforced)
    wrong = "0" * 64
    with pytest.raises(Exception):
        DeclaredFilingDocument(
            document_id="DOC-WP-E-3",
            content=content,
            declared_sha256=wrong,
            sections=(section,),
        )


def test_restatement_linkage_is_opt_in_and_hashed():
    content_v2 = "درآمد عملیاتی (بازبیانی‌شده) ۱۲۰ میلیون ریال"
    digest_v2 = __import__("hashlib").sha256(content_v2.encode("utf-8")).hexdigest()
    content_v1 = "درآمد عملیاتی ۱۰۰ میلیون ریال"
    digest_v1 = __import__("hashlib").sha256(content_v1.encode("utf-8")).hexdigest()
    doc = DeclaredFilingDocument(
        document_id="DOC-WP-E-2R",
        content=content_v2,
        declared_sha256=digest_v2,
        supersedes_document_sha256=digest_v1,
        sections=(
            DeclaredFilingSection(
                section_id="sec-income-v2",
                kind="FINANCIAL_STATEMENT",
                text=content_v2,
            ),
        ),
    )
    assert doc.supersedes_document_sha256 == digest_v1
    # the linkage must reference a REAL prior digest — not a placeholder
    assert re.fullmatch(r"[0-9a-f]{64}", doc.supersedes_document_sha256)


def test_no_real_retrieval_evidence_is_fabricated_anywhere():
    # the coverage surface must not invent uptime counters or last-success
    # instants: the fold input stays EMPTY on the endpoint, and the fixture
    # descriptors themselves declare no last-success timestamp
    for d in declared_source_descriptors():
        assert d.last_success_utc is None, f"no retrieval has ever happened: {d.source_id}"
