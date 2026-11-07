"""WAVE-AB4 (2026-11-08): WP-G / AI-6 gap-closure tests.

Closes the audit's WP-G gaps with deterministic, synthetic-only evidence:

1. G3 primary-precedence resolver (was: mapping existed, nothing resolved);
2. G1 per-source kill switch on SourceDescriptor (was: job-level only);
3. G1 coverage report surfaced at runtime (was: ZERO production callers);
4. G2 declared unit/currency normalization (was: mandatory-but-unconverted);
5. G2 deterministic filing extraction for the four ContentKind targets
   (was: vocabulary only, no implementation);
6. G4 first-class dossier content sections (business overview / valuation /
   capital structure / confidence vocabulary).

All evidence is synthetic/declared; nothing touches real providers.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings

ROOT = Path(__file__).resolve().parents[2]

_RESOLVED_AT = datetime(2026, 11, 8, 10, 0, 0, tzinfo=timezone.utc)

_TIER_PRECEDENCE = {
    "PRIMARY_REGULATOR": "PRIMARY",
    "REPUTABLE_FINANCIAL_NEWS": "SECONDARY",
}


def _evidence(evidence_id: str, source_id: str, tier: str, *, pub: datetime | None = None):
    from app.domain.evidence import EvidenceItem

    return EvidenceItem(
        evidence_id=evidence_id,
        source_id=source_id,
        source_identifier=f"identifier-{source_id}",
        publisher=source_id,
        retrieval_time_utc=datetime(2026, 11, 7, tzinfo=timezone.utc),
        publication_time_utc=pub,
        publication_status="KNOWN" if pub is not None else "UNAVAILABLE",
        source_tier=tier,
        extraction_method="deterministic-test",
        corroboration_status="UNVERIFIED",
        trust_status="UNVERIFIED",
        citations=("citation-1",),
    )


def _conflict(conflict_id: str, ids: tuple[str, ...]):
    from app.domain.evidence import EvidenceConflict

    return EvidenceConflict(
        conflict_id=conflict_id,
        evidence_ids=ids,
        description="differing reported revenue for the same period",
        status="OPEN",
    )


# ---------------------------------------------------------------------------
# 1) Primary-precedence deterministic resolver
# ---------------------------------------------------------------------------


def test_primary_outranks_secondary_and_resolution_is_auditable():
    from app.domain.evidence_resolution import (
        PRIMARY_OVER_SECONDARY_V1,
        resolve_conflict_by_precedence,
    )

    primary = _evidence("ev-primary", "src.codal", "PRIMARY_REGULATOR", pub=datetime(2026, 11, 1, tzinfo=timezone.utc))
    secondary = _evidence("ev-news", "src.news", "REPUTABLE_FINANCIAL_NEWS", pub=datetime(2026, 11, 2, tzinfo=timezone.utc))
    conflict = _conflict("c-1", ("ev-primary", "ev-news"))
    resolved, record = resolve_conflict_by_precedence(
        conflict, [secondary, primary], tier_precedence=_TIER_PRECEDENCE, resolved_by="deterministic-rule-v1", resolved_at_utc=_RESOLVED_AT
    )
    assert resolved.status == "RESOLVED_DETERMINISTIC"
    assert resolved.resolution_rule == PRIMARY_OVER_SECONDARY_V1
    assert record.winner_evidence_id == "ev-primary"
    assert record.winner_precedence == "PRIMARY"
    assert record.loser_evidence_ids == ("ev-news",)
    # loser values preserved: the note names winners AND losers explicitly
    assert "ev-news" in resolved.notes and "loser" in resolved.notes.lower()
    # original conflict untouched (frozen immutability)
    assert conflict.status == "OPEN"


def test_same_precedence_conflict_refused_and_stays_open():
    from app.domain.evidence_resolution import resolve_conflict_by_precedence

    a = _evidence("ev-a", "src.codal", "PRIMARY_REGULATOR", pub=datetime(2026, 11, 1, tzinfo=timezone.utc))
    b = _evidence("ev-b", "src.tsetmc", "PRIMARY_REGULATOR", pub=datetime(2026, 11, 2, tzinfo=timezone.utc))
    conflict = _conflict("c-2", ("ev-a", "ev-b"))
    with pytest.raises(ValueError, match="rule_not_applicable_same_precedence"):
        resolve_conflict_by_precedence(
            conflict, [a, b], tier_precedence=_TIER_PRECEDENCE, resolved_by="rule", resolved_at_utc=_RESOLVED_AT
        )


def test_missing_party_and_unknown_tier_refuse():
    from app.domain.evidence_resolution import resolve_conflict_by_precedence

    conflict = _conflict("c-3", ("ev-x", "ev-missing"))
    with pytest.raises(ValueError, match="evidence_missing"):
        resolve_conflict_by_precedence(
            conflict, [_evidence("ev-x", "s", "PRIMARY_REGULATOR")], tier_precedence=_TIER_PRECEDENCE, resolved_by="r", resolved_at_utc=_RESOLVED_AT
        )
    unknown_tier = _evidence("ev-u", "s", "UNDECLARED_TIER_XYZ")
    with pytest.raises(ValueError, match="tier_not_in_precedence_map"):
        resolve_conflict_by_precedence(
            _conflict("c-4", ("ev-u", "ev-news")),
            [unknown_tier, _evidence("ev-news", "n", "REPUTABLE_FINANCIAL_NEWS")],
            tier_precedence=_TIER_PRECEDENCE,
            resolved_by="r",
            resolved_at_utc=_RESOLVED_AT,
        )


def test_batch_resolution_deterministic_with_honest_refusal_rows():
    from app.domain.evidence_resolution import resolve_conflicts_by_precedence

    primary = _evidence("ev-p", "src.codal", "PRIMARY_REGULATOR", pub=datetime(2026, 11, 1, tzinfo=timezone.utc))
    secondary = _evidence("ev-s", "src.news", "REPUTABLE_FINANCIAL_NEWS", pub=datetime(2026, 11, 1, tzinfo=timezone.utc))
    same = _evidence("ev-s2", "src.news2", "REPUTABLE_FINANCIAL_NEWS")
    resolvable = _conflict("c-b", ("ev-p", "ev-s"))
    unresolvable = _conflict("c-a", ("ev-s", "ev-s2"))
    resolved, records, refusals = resolve_conflicts_by_precedence(
        [resolvable, unresolvable],
        [primary, secondary, same],
        tier_precedence=_TIER_PRECEDENCE,
        resolved_by="rule",
        resolved_at_utc=_RESOLVED_AT,
    )
    assert [c.conflict_id for c in resolved] == ["c-b"]
    assert len(records) == 1 and records[0].conflict_id == "c-b"
    assert refusals == ({"conflict_id": "c-a", "reason": "rule_not_applicable_same_precedence"},)


# ---------------------------------------------------------------------------
# 2) Per-source kill switch (default ENGAGED — fail-closed)
# ---------------------------------------------------------------------------


def test_source_kill_switch_defaults_engaged_and_runnable_fail_closed():
    from app.domain.declared_source_fixtures import declared_source_descriptors

    for d in declared_source_descriptors():
        assert d.kill_switch == "ENGAGED"
        assert d.is_runnable() is False


def test_kill_switch_release_makes_configured_source_runnable_and_retired_refuses():
    from app.domain.source_registry import SourceDescriptor

    base = dict(
        source_id="s1",
        name="n",
        tier="PRIMARY_REGULATOR",
        precedence_class="PRIMARY",
        ownership="o",
        permitted_access="p",
        access_terms_version="v",
        refresh_policy="ON_DEMAND",
    )
    released = SourceDescriptor(**base, kill_switch="RELEASED")
    assert released.is_runnable() is True
    with pytest.raises(ValueError, match="retired_source_cannot_be_kill_switch_released"):
        SourceDescriptor(**base, status="RETIRED", kill_switch="RELEASED")


# ---------------------------------------------------------------------------
# 3) Coverage report surfaced at runtime
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    get_settings.cache_clear()
    os.environ.setdefault("DATA_SOURCE", "mock")
    return TestClient(__import__("app.main", fromlist=["app"]).app, client=("wpg-test", 12405))


def test_coverage_endpoint_honest_and_fail_closed(client):
    res = client.get("/api/v10/productloops/intel/coverage", params={"now_utc": "2026-11-08T00:00:00Z"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    report = data["report"]
    assert report["universal_coverage_claimed"] is False
    # every declared source has never been retrieved — nothing invented
    assert len(report["never_retrieved"]) >= 4
    assert data["runnable_sources"] == []
    assert set(data["kill_switch_states"].values()) == {"ENGAGED"}
    assert data["honesty"]["universal_coverage_claimed"] is False


def test_coverage_endpoint_requires_instant(client):
    res = client.get("/api/v10/productloops/intel/coverage")
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# 4) Unit/currency normalization
# ---------------------------------------------------------------------------


def test_money_units_collapse_to_rial_with_exact_integer_scales():
    from app.domain.unit_normalization import DeclaredQuantity, normalize_quantity

    q = DeclaredQuantity(value=Decimal("12.5"), unit="MILLION_RIAL", currency="IRR")
    n = normalize_quantity(q)
    assert n.unit == "RIAL"
    assert n.value == Decimal("12500000")
    assert n.scale_factor_applied == 1_000_000
    persian = DeclaredQuantity(value=Decimal("2"), unit="میلیون ریال", currency="IRR")
    assert normalize_quantity(persian).value == Decimal("2000000")


def test_cross_currency_and_dimension_mismatch_refuse():
    from app.domain.unit_normalization import DeclaredQuantity, normalize_comparable

    irr = DeclaredQuantity(value=Decimal("1"), unit="RIAL", currency="IRR")
    usd = DeclaredQuantity(value=Decimal("1"), unit="RIAL", currency="USD")
    with pytest.raises(ValueError, match="cross_currency_comparison_refused"):
        normalize_comparable(irr, usd)
    money = DeclaredQuantity(value=Decimal("1"), unit="RIAL", currency="IRR")
    ratio = DeclaredQuantity(value=Decimal("1"), unit="RATIO", currency="IRR")
    with pytest.raises(ValueError, match="dimension_mismatch"):
        normalize_comparable(money, ratio)


def test_unknown_unit_refused_never_guessed():
    from app.domain.unit_normalization import DeclaredQuantity

    with pytest.raises(ValueError, match="unknown_unit"):
        DeclaredQuantity(value=Decimal("1"), unit="LIGHT_YEARS", currency="IRR")


# ---------------------------------------------------------------------------
# 5) Deterministic filing extraction
# ---------------------------------------------------------------------------


def _document(sections, *, supersede: str | None = None) -> "object":
    from app.domain.filing_extraction import DeclaredFilingDocument

    content = json.dumps([s.model_dump(mode="json") for s in sections], ensure_ascii=False)
    return DeclaredFilingDocument(
        document_id="doc-1",
        content=content,
        declared_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        published_at_utc=datetime(2026, 11, 5, tzinfo=timezone.utc),
        reporting_period="Q2-1405",
        currency="IRR",
        supersedes_document_sha256=supersede,
        sections=tuple(sections),
    )


def test_extraction_covers_all_four_g2_types_with_provenance():
    from app.domain.filing_extraction import (
        DeclaredFilingSection,
        extract_filing_document,
    )

    sections = [
        DeclaredFilingSection(
            section_id="revenue",
            kind="FINANCIAL_STATEMENT",
            declared_value=Decimal("1500000000000"),
            declared_unit="RIAL",
            declared_currency="IRR",
        ),
        DeclaredFilingSection(section_id="note-impairment", kind="NOTE", text="ذاخیره کاهش ارزش در قالب یادداشت شماره ۹"),
        DeclaredFilingSection(section_id="event-plant", kind="MATERIAL_EVENT", text="افتتاح خط تولید جدید"),
        DeclaredFilingSection(section_id="guidance-fy", kind="GUIDANCE", text="پیش‌بینی فروش سالانه افزایش می‌یابد"),
    ]
    doc = _document(sections)
    result = extract_filing_document(doc)
    assert len(result.financial_facts) == 1
    fact = result.financial_facts[0]
    assert fact.value == Decimal("1500000000000") and fact.unit == "RIAL" and fact.currency == "IRR"
    assert fact.document_sha256 == doc.declared_sha256
    assert fact.extraction_method == "DETERMINISTIC_SECTION_MAP_V1"
    assert fact.extraction_model_version is None
    assert len(result.notes) == 1 and len(result.material_events) == 1 and len(result.guidance) == 1
    assert result.refusals == ()
    # restatement linkage carried
    assert result.supersedes_document_sha256 is None


def test_financial_statement_without_value_is_an_honest_refusal_row():
    from app.domain.filing_extraction import (
        DeclaredFilingSection,
        extract_filing_document,
    )

    doc = _document([DeclaredFilingSection(section_id="revenue", kind="FINANCIAL_STATEMENT", text="درآمد: …")])
    result = extract_filing_document(doc)
    assert result.financial_facts == ()
    assert [r.reason for r in result.refusals] == ["financial_statement_without_declared_value"]


def test_document_hash_mismatch_fails_closed_at_construction():
    from app.domain.filing_extraction import DeclaredFilingDocument, DeclaredFilingSection

    with pytest.raises(ValueError, match="declared_sha256_mismatch"):
        DeclaredFilingDocument(
            document_id="doc-bad",
            content="anything",
            declared_sha256="0" * 64,
            sections=(),
        )


def test_extraction_is_deterministic_on_repeat():
    from app.domain.filing_extraction import (
        DeclaredFilingSection,
        extract_filing_document,
    )

    sections = [DeclaredFilingSection(section_id="n1", kind="NOTE", text="یادداشت"), DeclaredFilingSection(section_id="g1", kind="GUIDANCE", text="پیش‌بینی")]
    doc = _document(sections)
    r1 = extract_filing_document(doc).model_dump(mode="json")
    r2 = extract_filing_document(doc).model_dump(mode="json")
    assert r1 == r2


def test_restatement_linkage_carried_on_extraction():
    from app.domain.filing_extraction import (
        DeclaredFilingSection,
        extract_filing_document,
    )

    old = _document([DeclaredFilingSection(section_id="n", kind="NOTE", text="x")])
    doc = _document([], supersede=old.declared_sha256)
    result = extract_filing_document(doc)
    assert result.supersedes_document_sha256 == old.declared_sha256


# ---------------------------------------------------------------------------
# 6) Dossier first-class content sections
# ---------------------------------------------------------------------------


def test_dossier_metric_row_requires_evidence_and_dossier_carries_declared_sections():
    from app.domain.fundamental_dossier import DeclaredMetricRow

    with pytest.raises(ValueError):
        DeclaredMetricRow(metric="P/E", value=Decimal("7.5"), unit="RATIO", source_evidence_ids=())
    row = DeclaredMetricRow(
        metric="P/E", value=Decimal("7.5"), unit="RATIO", source_evidence_ids=("fact-1",)
    )
    assert row.currency == "N/A"


def test_dossier_confidence_is_a_closed_vocabulary():
    from app.domain.fundamental_dossier import CompanyIdentity, CompanyDossier

    base = dict(
        dossier_id="d1",
        company_id="c1",
        information_cutoff_utc=datetime(2026, 11, 8, tzinfo=timezone.utc),
        identity=CompanyIdentity(
            company_id="c1",
            symbols=("فملی",),
            resolution_basis="MANUAL_OWNER_INPUT",
            ambiguity_status="UNAMBIGUOUS",
            resolved_at_utc=datetime(2026, 11, 1, tzinfo=timezone.utc),
            source_evidence_ids=("identity-evidence-1",),
        ),
        data_trust_ref="SYNTHETIC/DECLARED (repo fixture)",
        pit_eligible=True,
        limitations=("declared fixture",),
    )
    dossier = CompanyDossier(**base, confidence="LOW")
    assert dossier.confidence == "LOW"
    with pytest.raises(ValueError):
        CompanyDossier(**base, confidence="CERTAIN")
