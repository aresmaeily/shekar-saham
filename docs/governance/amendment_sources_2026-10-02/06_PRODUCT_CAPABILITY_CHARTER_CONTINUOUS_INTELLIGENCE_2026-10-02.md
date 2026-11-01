# RADAR_BOURSE — Product Capability Charter: Continuous Intelligence, Fundamentals & Product Improvement

Revision: 2026-10-02
Status: OWNER-DIRECTED PRODUCT REQUIREMENTS; IMPLEMENTATION NOT PROVEN

## 1. Purpose

Preserve all existing RADAR_BOURSE capabilities and explicitly extend the target product to a continuously operating, evidence-driven market and company intelligence system, governed research platform, and product improvement engine. This charter defines desired product behavior, not current implementation status.

## 2. Continuous market intelligence

The system must monitor market behavior without requiring a user prompt, using configured schedules and events where data feeds support them. Target signals include unusual money flow, buyer/seller strength, volume/value expansion, price/volume divergence, sector synchronization, relative strength, liquidity changes, regime transitions, and anomalies across related symbols.

Each detection must retain: event/run ID, timestamp and window, symbol/industry universe, source and data trust, baseline/reference period, deterministic feature values, explanation, confidence semantics, supporting and contradicting evidence, invalidation conditions, expiry and downstream action state.

## 3. Continuous external/web and company intelligence

The platform must maintain a versioned source registry that can expand over time. Initial source classes should include exchange/regulator disclosures, issuer announcements, official company investor-relations pages, audited/official financial statements, corporate-action and governance notices, reputable financial news, sector/industry sources, macroeconomic releases and other approved public sources.

The product must not claim literal coverage of the entire internet. It must report configured coverage, source discovery status, inaccessible sources, freshness, last successful retrieval, failures and known gaps. Respect access permissions, terms, rate limits, privacy and technical restrictions. Source access and crawl cadence must be configurable and bounded.

### Source hierarchy and reconciliation

1. Primary official/regulatory/issuer documents are preferred for reported company facts when available.
2. Independent reputable secondary sources provide corroboration and context, not silent replacement of primary values.
3. Duplicate reports should be clustered; copied syndications must not be mistaken for independent corroboration.
4. Contradictions remain explicit with source/time/period details until a deterministic rule or human review resolves them.
5. The system records publication time separately from retrieval time and financial reporting period.
6. Restatements and amended filings create new versions; historical analyses use only information available at their point-in-time cutoff.
7. Currency, units, fiscal calendars, consolidation status, auditor opinion, missing notes and uncertainty must be explicit.

## 4. Fundamental intelligence dossier

For each target or watchlisted company, the dossier should include, where available and source-supported:
- financial statements and trends;
- revenue, margins, operating profit, earnings, cash flow, debt, working capital and capital expenditure;
- valuation metrics with methodology, as-of time and peer/reference context;
- auditor opinion, qualifications, going-concern warnings, related-party items and material notes where reported;
- dividends, capital increases, corporate actions, management changes, governance events, guidance and material disclosures;
- sector/industry context, macro exposure and material risks;
- source agreement/conflict, missing data, freshness, Data Trust, PIT eligibility and limitations.

The system distinguishes three concepts: (a) stock/investment candidate, (b) company on a user's monitoring list, and (c) possible M&A/acquisition-target intelligence. They must never be conflated. An acquisition-target signal requires its own evidence and should not be inferred solely from a stock opportunity score.

AI explains and synthesizes; deterministic services own numeric calculations, normalization, PIT eligibility and risk metrics. No financial fact may be invented to fill a gap.

## 5. Market interpreter: reference then extension

TabloKhani-style board reading is the first reference behavior to map. The team should create a lawful capability matrix and Golden Set covering market-board interpretation, money flow, buyer/seller power, queues/liquidity, volume/value, price action and related market microstructure. The reference site is a benchmark, not the system's truth source or final capability ceiling.

The extension path adds validated fundamentals, cross-source company events, regime context, sector relationships, historical similarity, risk-adjusted opportunity clusters, research-memory evidence and prediction calibration. Every improvement must be measured against a versioned baseline. Do not claim the product is superior to reference sites until repeatable benchmark results support the exact claim.

## 6. Opportunity clusters and explainability

Opportunity output should be organized into explainable clusters, not only a top-N list. Example candidate classes include early accumulation, breakout candidate, relative strength, volume expansion, industry rotation, oversold recovery and material fundamental/event change. Each class requires a formal definition, data prerequisites, time horizon, evidence, confidence semantics, risk, invalidation, expiry and historical evaluation.

The output should explain “why now?”, “what could invalidate this?”, “what evidence disagrees?”, “what is the risk-adjusted interpretation?”, and “what information is missing?”.

## 7. Research, filter science and feedback

Every financial hypothesis must be preregistered before outcome observation. The evaluation path uses deterministic Backtest, OOS/Walk-Forward, Forward Test, costs/slippage, liquidity and risk controls, holdout isolation, multiple-testing controls and regime-sliced analysis where applicable. All results link to code/config/data versions and immutable run artifacts.

For each prediction/opportunity, define the prediction timestamp, target/outcome horizon, evaluation metric, event-maturity rule and invalidation rule in advance. After the outcome matures, compare prediction to reality, analyze error categories, assess calibration/drift, and create a new research proposal if warranted. Never change the original prediction record or use future data in the original assessment.

## 8. AI Product Intelligence & whole-product audit

A recurring Product Intelligence loop audits the software itself. Separate the domains:
- filters and strategies: backtest/WFO/forward test, false positives, stability, regime dependence, costs and risk;
- AI interpretation: Golden Set accuracy, source grounding, confidence calibration, contradiction handling and invalidation;
- data/provider layer: freshness, trust, missing coverage, latency, failure/recovery and cost;
- UX/product flows: privacy-safe task completion, friction, repeated actions, errors, adoption and user feedback where lawfully collected;
- software quality: regression, performance, reliability, security, compatibility and release readiness.

Backtest is not a universal test for all software components. The evaluator must match the domain. Each audit produces ranked proposals with baseline, evidence, expected impact, uncertainty, cost, risk, experiment design, rollback and human approval state. Production changes and releases remain human-controlled.

## 9. Cadence and operations

The schedule is configurable and resource-bounded. Candidate operating modes:
- event-triggered ingestion/analysis for material disclosures and market anomalies where supported;
- scheduled market/source freshness scans;
- weekly or owner-configured matured filter/prediction outcome reviews;
- monthly or owner-configured cross-product health and UX audits.

Every job needs idempotency, retry ceilings, timeout, concurrency/rate limits, run identity, audit trace, last-success status, failure alert, kill switch and explicit source/data boundaries. Cadence must not be hard-coded before operational requirements and budgets are approved.

## 10. Governance and security

- G2 remains a hard gate before real-data AI-2 execution until independent validation and owner acceptance.
- External documents and web content are untrusted data, never executable instructions.
- Use approved tools only; preserve provenance and source references; apply prompt-injection isolation and the Two-Key Rule where required.
- No broker orders, autonomous real-money trading, auto-promotion, production mutation, self-escalation or self-modifying production logic.
- Product telemetry is minimum-necessary, privacy-safe, access-controlled, retention-limited and policy-compliant.
- Provider failure, low Data Trust, stale data, contradictory sources, budget exhaustion or missing provenance must fail closed or degrade explicitly.

## 11. Acceptance gates

### Monitoring
A repeatable run demonstrates configured coverage, event detection, timestamps, freshness, rate/budget limits, failure/recovery, observability and kill switch.

### Fundamental intelligence
A test corpus demonstrates primary-source extraction, point-in-time correctness, version/restatement handling, cross-source corroboration, contradiction visibility, citation completeness, unit/currency normalization and safe behavior when a source is missing.

### Market interpretation
A versioned Golden Set demonstrates baseline and extended capability metrics, false positives/negatives, confidence calibration where probabilistic claims are made, and invalidation quality.

### Research and feedback
Reproducible runs demonstrate preregistration, deterministic evaluation, outcome maturity, holdout protection, error analysis, versioned artifacts, independent validation and approval gates.

### Product Intelligence
A recurring audit produces a traceable baseline, domain-appropriate tests, prioritized proposals and evidence of evaluation without production mutation.

No capability becomes IMPLEMENTED, RUNTIME_VERIFIED, LIVE_VERIFIED or PROVEN solely because this charter or its implementation code exists.
