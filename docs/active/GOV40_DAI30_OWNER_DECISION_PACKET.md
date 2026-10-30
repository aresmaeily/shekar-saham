# D-AI-30 Owner Decision Packet — Operational Alert Cadence, Budgets and Delivery

> **✅ RESOLVED 2026-10-30 (Asia/Tehran) — CONSOL-GOV-41 owner decision amendment.** The ten decision items below were resolved by an explicit owner decision: O1-b (event-triggered + 30-minute bounded scheduled checks), O2-c (global 30 jobs/h; per-kind 6/h; per-channel 10 deliveries/h; burst 3/min), O3-c (in-product inbox only + durable idempotent outbox/dead-letter + reversible additive migration), decision-4 (24 h dedup; kind+subject+binding+event-ID key or canonical fingerprint; max 3 attempts with 30 s/120 s retries; expiry drop; no digest), O5-b (global + per-job kill switches defaulting ENGAGED, fail-closed on missing/malformed/inconsistent config, audited transitions), decision-6 (full observability, no recursive self-alerting), decision-7 (no external egress; evidence IDs internal; 90-day retention), decision-8 (Synthetic/Paper only; exact label `SYNTHETIC / PAPER — NOT LIVE`; mixed/stale/unavailable blocked), decision-9 (synthetic fixtures + deterministic clocks acceptance battery), decision-10 (additive rollback preserving records; post-acceptance activation; unapproved jobs stay fail-closed). **Scope ruling: APPROVED FOR SYNTHETIC/PAPER-ONLY, IN-PRODUCT operational monitoring and alerts.** Authoritative record: `GOV41_OWNER_DECISION_AMENDMENT_2026-10-30.md`. The packet text below is preserved byte-unchanged as the decision input; its `PENDING OWNER DECISION` status line describes the packet at preparation time and is superseded by this resolution block.

**STATUS: `PENDING OWNER DECISION` — nothing in this packet is decided, approved, or implemented.**

**Date:** 2026-10-30 (Asia/Tehran) · **Prepared under:** CONSOL-GOV-40 Phase 3 · **Baseline HEAD:** `dec77f25072439c07bd255ec132936f482c3a892` · **Action identifier:** `OA-ALERT-OPERATIONS` (decision register ID D-AI-30 unchanged)

**Authoritative sources read for this packet (verbatim, not paraphrased from memory):**
- `docs/governance/amendment_sources_2026-10-02/05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md:130–134` — "D-AI-30 — Proactive Intelligence. DEFERRED UNTIL CORE STABILITY. Requires budget, observability, recovery and kill switch."
- `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md:147–153` (nine alert classes), `:156` (governed monitoring; source terms, robots/rate limits, privacy, budgets, kill switches), `:181–186` (initial cadence policy; "Cadence, thresholds and budgets require explicit configuration, observability, idempotency, retry ceilings and a kill switch. Do not run live-data scans or backtests merely to prove a document change."), `:193` (monitoring acceptance: schedule/trigger execution, coverage/freshness, event lineage, failure/recovery, rate/budget enforcement, kill switch)
- `06_PRODUCT_CAPABILITY_CHARTER…:76–84` (§9 Cadence and operations: "Cadence must not be hard-coded before operational requirements and budgets are approved"; every job needs idempotency, retry ceilings, timeout, concurrency/rate limits, run identity, audit trace, last-success status, failure alert, kill switch and explicit source/data boundaries)
- Contracts read in source: `backend/app/domain/monitoring.py`, `backend/app/domain/monitoring_governance.py`, `backend/app/domain/governed_alerts.py`, `backend/app/services/notifier.py`, `backend/app/services/ws_hub.py`

**Hard boundary respected while preparing this packet:** `notifier.py` and `ws_hub.py` were read but NOT modified; no scheduler, dispatcher, or delivery code path was created; `governed_alerts.py` remains dispatch-free (`__all__` = contracts + pure helpers only). This packet is a decision document only.

---

## Context: what exists today (contracts only, zero operationalization)

- **Alert objects:** `governed_alerts.py` (commit `dec77f2`) — closed nine-kind `AlertKind` mirroring 02:148–149; frozen `GovernedAlertObject` with evidence ≥1 (never self-referential), UTC timestamp, confidence ∈ [0,1] + declared basis, data trust state, risk semantics, invalidation ≥1, explicit expiry (`expiry_utc` or `expiry_open_ended`), reason-for-now, run_id; per-kind dedicated trigger bindings to existing governed contracts BY ID with cross-kind contamination refusal; 06 §4 M&A non-conflation guard; 40 corpus-derived tests.
- **Job identity contracts:** `monitoring.py` — `MonitoringJobSpec` (trigger, retry, budget, freshness SLA, observability_ref, alerting_ref, kill switch defaulting **ENGAGED**, fail-closed `run_allowed()`); `TriggerSpec` (SCHEDULED needs owner-configured `schedule_expression`; EVENT_DRIVEN needs `event_types` — no cadence hard-coded); `RetryPolicy` (max_attempts ≤ `MAX_RETRY_ATTEMPTS=10`, `backoff_seconds_base` ≤ 3600, `idempotency_required=True`); `BudgetSpec` (max_runs_per_hour ≤ 60, max_timeout_seconds ≤ 3600, max_concurrency ≤ 8); `MonitoringJobState` (last_success_utc, consecutive_failures, failure_state ∈ HEALTHY/DEGRADED/FAILING/HALTED, `failure_alert_sent` mandatory when HALTED).
- **Governance predicate:** `monitoring_governance.py` — deterministic permission-to-run / freshness / failure-state evaluation; no execution.
- **Legacy product channels (pre-amendment, untouched, out of amendment scope):** `notifier.py` (Telegram + Bale via `send_text`, `_dedupe` dict cooldown, dry-run mode writing a notify log entry when enabled but channel-less, `process_alerts` gating, `format_alert` legacy buy/sell dict formatting); `ws_hub.py` `ConnectionManager` (in-process WebSocket `broadcast`, no persistence, no retry, dropped on disconnect); `engines/anomaly.py` `AnomalyDetector` (deterministic price/volume/orderbook observations).
- **What does NOT exist:** no scheduler process, no dispatcher, no queue, no per-kind budget enforcement, no alert-channel kill switch, no retention store, no delivery retry, no route. This absence is deliberate (06 §9; P3.60 no-unauthorized-feature; D-AI-30 owner-gated).

---

## Decision items (each requires an explicit owner selection; defaults below are NOT endorsements)

### Item 1 — Alert cadence and scheduling policy
Corpus candidate modes (02:183–186; 06 §9): (a) **event-triggered** ingestion/analysis for material disclosures and market anomalies where feeds support it; (b) **scheduled** market/source freshness-coverage and market/financial intelligence scans; (c) **weekly or owner-configured** matured filter/strategy and prediction-outcome reviews; (d) **monthly or owner-configured** cross-product capability/UX/reliability audits.
Options: **O1-a** minimal — event-driven only, no scheduled scans (lowest resource use; freshness reporting degrades to on-demand); **O1-b** event-driven + scheduled freshness/coverage scans (matches 02:184 two-class minimum); **O1-c** full four-mode schedule per 02:183–186. In every option, schedule expressions are owner-configured strings in `TriggerSpec` (the contract already forbids hard-coding).
**Affected modules (for any option):** new additive scheduler/executor service (does not exist); consumes `MonitoringJobSpec.trigger`; writes `MonitoringJobState`; kill switch must be RELEASED per job before any execution. **Consequence:** O1-a minimizes new code and budget exposure; O1-c maximizes coverage but requires explicit budget heads and observability from day one (02:186).

### Item 2 — Per-class alert budgets and rate limits
The nine alert kinds may have wildly different natural rates (market anomalies vs research-result maturity). A single global budget would either throttle low-volume kinds needlessly or let high-volume kinds flood.
Options: **O2-a** one global `BudgetSpec` (max_runs_per_hour ≤ 60 hard ceiling already in contract); **O2-b** per-kind budget table (nine entries; each within the contract hard ceilings); **O2-c** per-kind + per-channel egress caps (adds a channel-side limiter that does not exist today).
**Affected modules:** `BudgetSpec` instantiation per job; new dispatch layer reads the budget before emitting; `notifier.py` `_allow()` cooldown is channel-global today and would need a per-kind key schema IF O2-b/c chosen (a change to a legacy file — only after approval).

### Item 3 — Delivery channels and delivery guarantees
Existing transport: Telegram/Bale (`notifier.py` `_post_telegram`/`_post_bale`, returns bool success), WebSocket push (`ws_hub.py` `broadcast`, in-process only), dry-run log. No email/SMS/webhook exists.
Options: **O3-a** reuse Telegram+Bale+ws only (no new channel code); **O3-b** add a governed webhook channel (new adapter, new secret-handling surface); **O3-c** advisory-only in-product surface (no external egress at all — strongest privacy, weakest timeliness).
Guarantee classes: **at-most-once** (current ws_hub semantics; cheap, lossy) vs **retry-until-ack with dead-letter** (needs a persistent outbox — new storage) vs **best-effort with delivery log** (notify_log exists but is not queryable as an outbox). The corpus requires failure alerting and last-success status (06 §9) — the outbox question is therefore a real owner choice, not an implementation detail.
**Affected modules:** `notifier.py` (channel adapters, egress), `ws_hub.py` (push fan-out), `store`/notify-log (only if persistent guarantee chosen), new dispatcher.

### Item 4 — Retry, deduplication, expiry, suppression semantics
Contract anchors already fixed: `RetryPolicy` (bounded ≤10 attempts, idempotency required), `GovernedAlertObject.expiry_utc/expiry_open_ended` (explicit expiry decision mandatory per alert), `notifier._dedupe` (in-memory, 2000-entry cap, lost on restart — NOT durable dedup).
Owner must decide: (a) dedup **window and key** (per alert_kind+subject? per binding id?; in-memory vs persisted); (b) suppression policy (silence duplicates vs downgrade-to-digest); (c) expired-alert behavior (drop at dispatch? deliver with expiry flag?); (d) whether retry applies to delivery (channel-level) or only to job execution (monitoring-level).
**Affected modules:** new dispatcher (primary), `notifier._allow` (if durable dedup chosen — legacy-file change), `governed_alerts.is_expired/active_at` helpers (pure, already deterministic).

### Item 5 — Kill-switch behavior and human override
Existing: per-job kill switch default ENGAGED (`MonitoringJobSpec.run_allowed()`), HALTED→failure-alert guard. NOT existing: an alert-channel master switch, per-kind mute, or a human-override audit surface.
Options: **O5-a** job-level only (sufficient to stop any scheduler work at the source); **O5-b** job-level + channel master switch (one flag stops all external egress; recommended shape per 06 §9's kill-switch requirement, but the choice and its placement are owner's); **O5-c** + per-kind mute table. Whichever is chosen, the switch must fail-closed (absent/malformed config = blocked) matching the existing ENGAGED-default posture, and every override transition must be recorded (audit trace, 06 §9).
**Affected modules:** `monitoring_governance.py` predicate extension (additive), new dispatcher gate, `notifier.py` (only if O5-b/c), settings/config read path.

### Item 6 — Failure reporting and observability
Corpus requirement (02:193; 06 §9): schedule/trigger execution, coverage/freshness, event lineage, failure/recovery, rate/budget enforcement, kill switch — all observable. Existing: `MonitoringJobState` fields + `observability_ref`/`alerting_ref` strings; no metrics emitter, no structured log schema for alert dispatch.
Owner decides: (a) minimum observable set at launch (suggested boundary to react to: last_success/last_attempt/failure_state per job + per-channel delivery success/failure counters + budget-enforcement refusals); (b) where records live (notify_log vs a governed dispatch log); (c) who is alerted when the alerting system itself fails (the `failure_alert_sent` HALTED guard exists — its channel target is an owner choice).
**Affected modules:** new dispatcher observability hooks; `notifier.py` notify-log shape (if extended — legacy-file change).

### Item 7 — Privacy and data-retention boundaries
Corpus anchors: 02:156 (monitoring must respect privacy), 06 §3 (privacy-safe telemetry boundaries; record publication vs retrieval time separately). Alert payloads carry `evidence_ids`, `subject`, `risk_semantics` — potentially company-sensitive.
Owner decides: (a) whether full alert payload or a redacted digest leaves the system (external channels); (b) retention period for dispatch logs and alert records (existing notify-log has no TTL); (c) whether evidence IDs may egress at all (they are internal referents) or only human-readable summaries; (d) data-trust gating: whether `data_trust_state` below a threshold blocks external delivery.
**Affected modules:** new dispatcher (redaction step), `notifier.py` payload construction (`format_alert` is legacy buy/sell — a governed formatter is new code), storage layer (TTL).

### Item 8 — Synthetic vs real-provider operating modes
Current fail-closed posture: `AI2_ENABLED=0`, `verified=False` (config.py:109/282), `execution_mode` SYNTHETIC_OR_PAPER; provider probes fail-closed `live_verified=false`; runtime G2 gate binds real-data AI-2 to the convened review commit (`gate_state_stale` otherwise). Alerts on **synthetic/paper data** vs **verified live data** are materially different claims (06 §3: no unsupported claims; 02:186: do not run live-data scans merely to prove a document change).
Owner decides: (a) whether operational alerting (once D-AI-30 approved) may run on synthetic/paper data at all, and with which visible "SYNTHETIC" labeling on every outbound message; (b) whether live-data alerting waits for `OA-AI2-LIVE-CREDENTIALS` (separate decision — do not conflate); (c) whether mode mixing is forbidden (synthetic alerts suppressed when real mode activates, or tagged separately). Recommended-structure boundary: alert source mode must be carried in `GovernedAlertObject.run_id`/`data_trust_state` and restated at delivery time — but the policy itself is the owner's.
**Affected modules:** dispatcher mode gate; `notifier.py` message templates; `execution_mode()` in `g2_gate.py` (read-only dependency).

### Item 9 — Acceptance criteria and required tests (whichever options are chosen)
Per 02:193 and 06 §9, acceptance of the operational alerting capability must evidence, at minimum: (1) schedule/trigger execution proof (deterministic tests over `TriggerSpec` binding + a synthetic clock harness); (2) per-kind budget enforcement refusal tests; (3) delivery success/failure recording incl. retry-ceiling exhaustion and dead-letter (if chosen); (4) kill-switch refusal tests both directions (ENGAGED denies, RELEASED allows, malformed denies); (5) dedup/expiry/suppression behavior tests incl. restart-durability when chosen; (6) synthetic-mode labeling test (every outbound synthetic alert carries the declared mode); (7) M&A non-conflation carried through delivery (alert-layer guard already tested — dispatch must not bypass it); (8) regression: existing 40 P5/P6 alert-contract tests + 58 AI-1 monitoring/opportunity tests + runtime-gate tests stay green; (9) privacy/redaction tests matching Item 7 choices; (10) no-live-data rule (02:186) — all acceptance runs on synthetic fixtures.
**Affected modules:** new test modules only; existing suites must remain untouched (no assertion-weakening precedent allowed).

### Item 10 — Risks, dependencies, rollback
**Dependencies (strict order):** D-AI-30 recorded (this packet) → additive dispatcher/scheduler implementation (new module, no legacy rewrite) → notifier/ws_hub integration (shared integration surfaces — sequential, never parallel with other runtime work) → synthetic-mode acceptance run → owner acceptance of the run evidence → (separately) `OA-AI2-LIVE-CREDENTIALS` for live mode. **No step authorizes AI-2 real-data execution** (`OA-AI2-ENABLEMENT` remains its own decision with its own gate binding).
**Risks:** alert flooding (mitigated by Item 2 budgets); duplicate spam on restart (in-memory dedup loss — Item 4); privacy egress via Telegram/Bale (Item 7 redaction); synthetic-vs-real confusion in outbound messages (Item 8 labeling); channel API lockout/rate limits (Telegram/Bale server-side — retry ceilings exist in contract); kill-switch blind spot if channel-level switch omitted (Item 5 O5-b); increased resource use by scheduled scans (Item 1 budget heads).
**Rollback behavior:** per design, every component is gated: engaging the job kill switch stops all scheduling; the channel master switch (if O5-b) stops egress; rollback of the dispatcher module is a code revert with zero data migration (no persistent outbox unless chosen in Item 3 — if chosen, outbox rows are append-only and can be drained/archived, never edited). No rollback path touches sealed evidence or governance records.

---

## Explicit non-actions by this packet

1. No option above is selected, endorsed, or implemented; `PENDING OWNER DECISION` remains the operative state of `OA-ALERT-OPERATIONS` / D-AI-30.
2. `notifier.py`, `ws_hub.py`, `monitoring.py`, `monitoring_governance.py`, `governed_alerts.py` are byte-unchanged by this cycle (verified by the cycle's tracked-diff check).
3. No scheduler, dispatcher, outbox, or delivery code exists after this cycle; nothing can send, publish, schedule, or deliver an alert.
4. D-AI-30 approval, `OA-AI2-LIVE-CREDENTIALS`, and `OA-AI2-ENABLEMENT` remain **three separate owner decisions** (never a bundle).
