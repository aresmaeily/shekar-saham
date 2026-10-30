# CONSOL-GOV-41 — OWNER-DIRECTED RELEASE & SYNTHETIC ALERT OPERATIONS CLOSURE — OWNER DECISION AMENDMENT (ADDITIVE)

**Date:** 2026-10-30 (Asia/Tehran) · **Authority:** explicit owner decision issued in the current project conversation on 2026-10-30 (directive CONSOL-GOV-41) · **Repository:** `aresmaeily/shekar-saham` · **Execution mode:** one integrated implementation/validation/documentation/publication/Windows-CI cycle; no intermediate owner selections; all decisions below are final owner selections.

**Amendment discipline:** this record is ADDITIVE. Sealed governance evidence, historical decision records, the amendment corpus (`docs/governance/amendment_sources_2026-10-02/`, untracked bootstrap path), the G2 owner decision document (sha256 `1f5da5c0…`) and `G2_GATE_STATE.json` are preserved byte-unchanged. Where an older record conflicts, this dated amendment governs FORWARD-LOOKING state only; the historical text remains the record of its own time.

---

## A1. P4 = N/A — NOT DEFINED AS AN INDEPENDENT WORK PACKAGE

Owner ruling: `P4 = N/A — NOT DEFINED AS AN INDEPENDENT WORK PACKAGE`.

- No P4 functionality, acceptance criteria, or implementation scope may be invented. This ratifies the corpus finding (`P0_AMENDMENT_CONTRACTS_SCOPE_DERIVATION_REPORT.md:12` — P4 undefined; `P5P6_ALERT_LIFECYCLE_SCOPE_DERIVATION.md` — "P4 preserved as NOT DEFINED in the corpus").
- Historical references to P4 remain preserved wherever they appear.
- **Mapping note (binding):** release synchronization and Windows CI belong to **Release Control** (the release/CI cycle record: `GOV40_RELEASE_WINDOWS_CI_STATUS_2026-10-30.md` and its GOV-41 successors) — NOT to an invented "P4 product phase". Any document that would otherwise describe such work under a P4 heading must attribute it to Release Control.

## A2. D-AI-30 (`OA-ALERT-OPERATIONS`) — APPROVED, RESTRICTED SCOPE: SYNTHETIC/PAPER-ONLY, IN-PRODUCT OPERATIONAL MONITORING AND ALERTS

The ten decision items of `GOV40_DAI30_OWNER_DECISION_PACKET.md` are resolved by the owner as follows. These are **binding final selections** (not defaults, not recommendations):

1. **Cadence — O1-b (event-triggered + bounded scheduled checks).** Event-triggered processing for events already produced by governed local contracts. Scheduled freshness/coverage checks every 30 minutes. No uncontrolled web crawling, external source discovery, or real-data scans. Schedule configuration must remain explicit and observable.
2. **Budgets — O2-c.** Global maximum **30 monitoring-job executions per hour**; per alert kind **maximum 6 executions per hour**; per in-product delivery channel **maximum 10 deliveries per hour**; per-minute burst ceiling **3 deliveries**. All limits enforced **before dispatch**. Never exceed existing contract ceilings.
3. **Delivery — O3-c.** In-product alert inbox **only**. No Telegram, Bale, WebSocket external fan-out, webhook, email, SMS, or other external egress. Durable, idempotent in-product outbox and dead-letter handling. Additive storage changes and a reversible migration.
4. **Retry, deduplication, expiry.** Durable deduplication window **24 hours**. Idempotency key = alert kind + subject + binding ID + source event ID; a deterministic canonical fingerprint when a source event ID is unavailable. Suppress duplicates; **no digest**. Drop expired alerts before delivery. Maximum **3 delivery attempts**; retry delays **30 s then 120 s**; exhausted deliveries move to dead-letter state. The existing contracts' idempotency requirements are preserved.
5. **Kill switch — O5-b.** Global in-product dispatch switch **plus per-job kill switch**, both **default ENGAGED** (fail-closed). Missing, malformed, or inconsistent configuration must deny execution. Every override transition auditable. No per-kind override system in this cycle. The owner **pre-authorizes release of the approved Synthetic/Paper jobs after all acceptance checks pass**.
6. **Observability.** Record: run ID, last attempt, last success, failure state, consecutive failures, last error code, queue depth, delivery success/failure, budget refusals, retry exhaustion, dead-letter count, kill-switch transitions. Dispatcher self-failure visible through health/status and structured local logs. **No recursive self-alerting.**
7. **Privacy and retention.** No external egress. Evidence IDs stay internal references. Only the minimum necessary human-readable summary displayed in the product. Never log credentials, tokens, or sensitive user content. Operational alert and dispatch records retained **90 days** with documented expiry cleanup. Sealed governance evidence and historical decision records preserved.
8. **Operating mode.** Synthetic/Paper only. Every visible alert carries the exact label `SYNTHETIC / PAPER — NOT LIVE`. Mixed, stale, and unavailable data blocked from operational alert delivery. Live-data alerting is NOT authorized. AI-2 real-data execution remains disabled.
9. **Acceptance.** All acceptance tests use synthetic fixtures and deterministic clocks. Test: scheduling and event triggers, budgets, idempotency, deduplication, expiry, retries, dead-letter, kill switches, audit records, privacy, labeling, recovery. Preserve all existing P5/P6, AI-1, and runtime-gate tests — none weakened, skipped, deleted, or rewritten to obtain a pass. Full test battery + all required static checks. End-to-end tests against the in-product inbox.
10. **Rollback and activation.** Implementation additive; no destructive database migration; queued and historical records preserved during rollback. Once all acceptance tests pass, the approved Synthetic/Paper in-product capability is activated under the approved budgets; the master switch and every unapproved job stay fail-closed; no external delivery or live-data operation may be enabled.

## A3. `OA-AI2-LIVE-CREDENTIALS` — DENIED FOR CURRENT RELEASE — CLOSED AS NOT GRANTED

Owner decision: **`DENIED FOR CURRENT RELEASE — CLOSED AS NOT GRANTED`** (explicit closed decision, not PENDING). No live provider credential is requested, read, copied, printed, hashed, committed, or otherwise handled during this cycle. The action may be re-proposed only by a future dated owner act.

## A4. `OA-AI2-ENABLEMENT` — DENIED FOR CURRENT RELEASE — CLOSED

Owner decision: **`DENIED FOR CURRENT RELEASE — CLOSED`** (explicit closed decision, not PENDING). Preserved unchanged for the whole cycle and after activation: `AI2_ENABLED=0` (`config.py:109`), `verified=False` (`config.py:282`), `execution_mode=SYNTHETIC_OR_PAPER`. Real-data AI-2 execution is not authorized. **G2 PASSED does not override this decision.**

## A5. GitHub publication — AUTHORIZED (one normal fast-forward)

The owner authorizes **one normal fast-forward publication** of the complete local history and CONSOL-GOV-41 changes to `origin/main`:

- No force push. No history rewrite. No squash or replacement of the 73-commit local chain (plus this cycle's commits).
- The actual final local HEAD is used — never a guessed SHA.
- Publication uses an authorized GitHub credential or a connected GitHub write integration; credentials are never exposed in logs or reports.
- If the remote has moved, ancestry is re-evaluated; remote work is never discarded.

## A6. Windows CI — MANDATORY RELEASE ACCEPTANCE

The owner requires an **actual Windows workflow run against the final published commit**. The approved Windows validation workflow (`.github/workflows/windows.yml`, `runs-on: windows-latest`, push/PR-triggered) must be included in the final local branch and executed by the publication push. Its run ID, URL, per-job conclusions, and logs are captured as release evidence. Old CI runs are not evidence for the new HEAD.

## Acceptance conditions and honest-reporting rule

The cycle is complete only when all applicable conditions hold (local HEAD = `origin/main`; full history published by fast-forward; Windows CI real success on the final commit; Ubuntu CI + Docker build success on the final commit; D-AI-30 recorded and implemented within the ten decisions; both OA-AI2 actions closed as denied; gates intact; all regression and new acceptance tests pass; manifest verifies completely; no prohibited live integration, external egress, trading, autonomous production mutation, or secret exposure). **If any condition fails, the cycle is not reported complete: the exact failing condition and its raw evidence are recorded, never disguised as a future roadmap item.**
