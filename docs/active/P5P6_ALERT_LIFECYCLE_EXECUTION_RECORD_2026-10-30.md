# P5/P6 Execution Record — Governed Alert Taxonomy Contract (additive)

**Date:** 2026-10-30 (Asia/Tehran) · **Directive:** CONSOL-GOV-39 Phase 3 · **Scope report:** `docs/active/P5P6_ALERT_LIFECYCLE_SCOPE_DERIVATION.md` (published before implementation, same commit)

## What was executed

WP-1 from the P5/P6 gap matrix (requirement R4 — "operational alert coverage as governed amendment-class contracts"): one additive domain module + corpus-derived acceptance tests, in the same authorized work class as P0-AMD-1/AI1-GC (deterministic contract layer; no LLM, no live data, no route, no scheduler, no delivery).

- `backend/app/domain/governed_alerts.py` (new, additive):
  - Closed nine-member `AlertKind` set exactly mirroring `02:148–149` (market anomalies; material company disclosures; filing/report publication; source conflicts; source staleness; significant financial-statement changes; watchlist changes; opportunity creation/expiry; research-result maturity). Unknown kinds unrepresentable.
  - `GovernedAlertObject` frozen contract: evidence ids (≥1, distinct, never self-referential), UTC-enforced timestamp, confidence [0,1] + declared basis, data trust state, risk semantics, invalidation conditions (≥1), explicit expiry decision (dated or explicitly open-ended), reason-for-now, run identity.
  - Per-kind dedicated trigger bindings bound to the existing governed layers BY ID (reuse-over-rewrite): `detector_ref`; `content_kind` (reuses `external_intelligence.ContentKind`, domain-restricted per kind: filing-class vs disclosure-class); `conflict_id` (`evidence.EvidenceConflict`); `stale_source_ids` (`source_registry.CoverageReport.stale_sources`); `fact_id`+`superseded_fact_id` (`fundamental_dossier.FundamentalFact` restatement chain, self-reference refused); `watchlist_ref`+`change_kind`; `opportunity_object_id`+`lifecycle_transition` (`opportunity.OpportunityObject` lifecycle); `prediction_id`+`outcome_id` (`prediction` maturity). A kind's binding field is REQUIRED for that kind and MUST stay empty on every other kind (no cross-kind trigger laundering).
  - 06 §4 M&A non-conflation carried into the alert layer: an `OPPORTUNITY_LIFECYCLE` alert referencing `CORPORATE_MA_ACQUISITION_TARGET_SIGNAL` is refused without dedicated `ma_signal_evidence_ids`.
  - Deterministic lifecycle helpers `is_expired`/`active_at` mirroring the opportunity layer; module `__all__` exposes contracts + pure helpers only — no send/publish/schedule/deliver surface (D-AI-30 / 06 §9 owner-gated cadence/delivery stays out of the contract layer).
- `backend/tests/test_p5p6_governed_alerts.py` (new, 40 tests): closed-kind set (9 representable + unknown refused), honesty-field guards (freeze, UTC, confidence bounds, evidence presence/distinctness/self-reference, invalidation presence, explicit expiry), all nine per-kind binding requirements, cross-kind contamination refusals (7-way parametrized + MA-evidence placement), M&A non-conflation refusal + acceptance, deterministic expiry helpers, and a code-shape check that the contract layer dispatches nothing.

## Boundaries preserved (verified)

- No existing module modified (imports read-only: `evidence`, `external_intelligence`, `opportunity`); no route; no config change; no workflow change; no protected bootstrap path; no governance record rewritten; no AI-2 change (`AI2_ENABLED=0`, `verified=False` untouched); no live provider contact; no delivery/cadence operationalization (D-AI-30 remains owner-gated); no P4 invented (P4 remains not-defined-in-corpus per `P0_AMENDMENT_CONTRACTS_SCOPE_DERIVATION_REPORT.md:12`).

## Test evidence at this commit

- Focused: `pytest tests/test_p5p6_governed_alerts.py` → **40 passed**; + AI1-GC opportunity/monitoring regression → **67 passed**.
- Static: `compileall` (new files) exit 0; `pyflakes` (new files) 0 findings.
- Full battery + G2 suites re-run at the final HEAD of this cycle — see the CONSOL-GOV-39 test execution matrix and `gov39_evidence/` (battery, focused, static, bootstrap, providers, pip-audit, pins, gates).

## Explicitly NOT done (owner/external, unchanged)

- Operational alert cadence/budget/launch configuration (D-AI-30 — owner).
- Alert delivery integration into notifier/ws_hub and any scheduling (owner-gated; P3.60).
- Live-data alerting (R3 live credentials — owner; `verified=False` preserved).
- Windows CI execution (B5/B6 push — externally blocked; no run exists; none claimed).
