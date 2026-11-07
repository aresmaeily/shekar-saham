"""Declared source-registry fixtures for the AI-6 coverage surface (WP-G).

WAVE-AB4 (2026-11-08): the audit recorded "no concrete registered source
instances anywhere in runtime — the registry is populated only in tests".
These DECLARED descriptors give the honest coverage report a real surface
WITHOUT activating anything:

- every descriptor is CONFIGURED with its kill switch ENGAGED (fail-closed
  default — none of them is runnable until an owner act releases both the
  source switch and the R-3/R-7 entitlement);
- no credentials, no URLs with secrets, no access methods beyond the
  declared permission state;
- WAVE-AI (2026-11-08, WP-E): every descriptor now declares its FRESHNESS
  TARGET — a policy declaration (how old may cached data get before the
  source is classified stale), NOT a measurement and never evidence of any
  retrieval; staleness stays honestly unevaluated until real uptime
  evidence exists;
- the set is versioned (DECLARED-SOURCES-2) and appended-to-only.
"""

from __future__ import annotations

from datetime import timedelta

from app.domain.source_registry import SourceDescriptor

DECLARED_SOURCES_VERSION = "DECLARED-SOURCES-2"

_DECLARED_SOURCES: tuple[SourceDescriptor, ...] = (
    SourceDescriptor(
        source_id="src.tsetmc.public",
        name="TSETMC عمومی (بورد و نمادها)",
        tier="PRIMARY_REGULATOR",
        precedence_class="PRIMARY",
        ownership="بورس و فرابورس ایران",
        permitted_access="public unauthenticated read of board/symbol pages",
        access_terms_version="declared-2026-11-08",
        refresh_policy="SCHEDULED",
        respects_robots=True,
        credentials_required=False,
        freshness_target=timedelta(minutes=15),  # DECLARED policy target — board/symbol pages are expected stale after 15min
        notes="DECLARED fixture — no retrieval performed; kill switch ENGAGED",
    ),
    SourceDescriptor(
        source_id="src.codal.disclosures",
        name="کدال (اطلاعات و صورت‌های مالی رسمی ناشران)",
        tier="PRIMARY_REGULATOR",
        precedence_class="PRIMARY",
        ownership="سازمان بورس و اوراق بهادار",
        permitted_access="public unauthenticated read of published disclosures",
        access_terms_version="declared-2026-11-08",
        refresh_policy="EVENT_DRIVEN",
        respects_robots=True,
        credentials_required=False,
        freshness_target=timedelta(hours=1),  # DECLARED policy target — disclosures polled at most hourly once activated
        notes="DECLARED fixture — real filings require R-3/R-7 authorization",
    ),
    SourceDescriptor(
        source_id="src.issuer.ir.pages",
        name="صفحه‌های روابط عمومی ناشران (Issuer IR)",
        tier="OFFICIAL_COMPANY_IR",
        precedence_class="PRIMARY",
        ownership="per-issuer",
        permitted_access="public unauthenticated read of issuer pages",
        access_terms_version="declared-2026-11-08",
        refresh_policy="SCHEDULED",
        respects_robots=True,
        credentials_required=False,
        freshness_target=timedelta(hours=6),  # DECLARED policy target — IR pages expected stale after 6h
        notes="DECLARED fixture — per-issuer robots.txt respected at runtime",
    ),
    SourceDescriptor(
        source_id="src.approved.news",
        name="خبرگزاری‌های مالی تأییدشده",
        tier="REPUTABLE_FINANCIAL_NEWS",
        precedence_class="SECONDARY",
        ownership="per-agency",
        permitted_access="public unauthenticated read of approved agencies",
        access_terms_version="declared-2026-11-08",
        refresh_policy="SCHEDULED",
        respects_robots=True,
        credentials_required=False,
        freshness_target=timedelta(minutes=30),  # DECLARED policy target — news corroboration expected stale after 30min
        notes="DECLARED fixture — secondary corroboration only, never primary",
    ),
)


def declared_source_descriptors() -> tuple[SourceDescriptor, ...]:
    """The declared fixture set (frozen; append-only by convention)."""
    return _DECLARED_SOURCES
