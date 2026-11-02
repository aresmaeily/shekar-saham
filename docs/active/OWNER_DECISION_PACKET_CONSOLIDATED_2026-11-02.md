# CONSOLIDATED OWNER DECISION PACKET — 2026-11-02 (MASTER directive §8)

Single consolidated view of EVERY outstanding owner decision. Prepared by the
temporary engineering team; **no option below is selected, assumed, or
pre-recorded** — every decision remains OPEN until the owner records an
explicit answer. Recommendations are labelled `RECOMMENDATION-NOT-DECISION`
and carry zero authority until the owner's dated reply.

How to answer: reply with the decision ID and the chosen option letter (e.g.
`D1=B, INSTALL=ISSUED 2026-11-03, LIVE=KEEP-DENIED`). Partial answers are
valid; unblocked work proceeds independently of unanswered items (directive
§8: "Do not interrupt independent work while preparing this packet").

---

## D1–D7 — AI-3 research-memory persistence (authority: AI3_PERSISTENCE_DECISION_PACKET.md, ALL SEVEN PENDING)

Verbatim questions, real option sets, seven-dimension comparison tables and
per-option consequences live in `docs/active/AI3_PERSISTENCE_DECISION_PACKET.md`
(answer templates at the end of that packet). One-line summary:

| ID | Question | Options | Work blocked by silence |
|---|---|---|---|
| D1 | Persistence backend for research memory | SQLite-WAL + content-addressed blobs (incumbent candidate) / pure JSONL / Postgres-class / defer | AI-3 engine adapter implementation (the acceptance scaffold is ready: 44-test Tier-A suite parameterized over `STORE_FACTORIES`; a TEST-LAYER-ONLY JSONL reference adapter proves the plug-in point — NOT a decision) |
| D2 | Target Windows installation access, or explicit deferral | grant access / defer with date | P343 target-machine validation (see R-2) |
| D3 | Retention policy by data class | per-class retention table | long-horizon storage sizing; NO purge path will be built for episodic evidence regardless (append-only/no-purge is architectural) |
| D4 | Encryption + key management | DPAPI / vault / OS-keyring / none | at-rest encryption layer |
| D5 | Backup destination + cadence | local/offsite/cadence table | automated backup schedule for research memory (product DB backup exists: `Store.backup(keep=7)`) |
| D6 | Access-control model | single-user / role file / none | shared-machine deployment posture |
| D7 | Recovery objectives (RPO/RTO) | numeric targets | recovery drill acceptance thresholds |

Consequence of continued silence: AI-3 stays `IMPLEMENTED/TESTED` at contract
level with the engine adapter BLOCKED; no other work is blocked.

## R-1 — INSTALL instruction (Controlled Alpha launch)

- **Question:** issue the explicit, dated `INSTALL` instruction for the P343
  Controlled Alpha launch sequence (`P343_INSTALL_CHECKLIST.md`, 10-step
  `PROPOSED_SEQUENCE_PENDING_OWNER_INSTALL`)?
- **Posture:** NOT ISSUED. Nothing installs without it. Windows CI green
  (runs on `7c225cb…`: 3/3 required jobs) is NOT proof of target-machine
  installation — separate acceptance gates (P3.43 principle).
- **RECOMMENDATION-NOT-DECISION:** issue INSTALL only after R-2 below is
  granted, so per-step exit criteria can be observed on the target machine.
- **Work blocked:** every installation step on the owner machine.

## R-2 — Windows target-machine validation access

- **Question:** provide target-machine access (or run the scripted sequence
  yourself and return the evidence bundle) for install/E2E/Electron checks?
- **Consequence of silence:** W2/W3–W5 Electron-shell and installation
  evidence remains TARGET-MACHINE-ONLY; the launch-readiness record stays at
  repo-side-complete.

## R-3 — Live data provider posture

- **Question:** keep the DENIED live-provider posture for the current
  release (synthetic/paper evidence only), or issue a new dated act
  authorizing a governed live work item with secure credential delivery?
- **Posture:** DENIED for the current release (`OA-AI2-LIVE-CREDENTIALS` /
  `OA-AI2-ENABLEMENT` closed as not granted; `AI2_ENABLED=0` default;
  `verified=False`). The market-display layer's pre-existing public TSETMC
  fetch (`DATA_SOURCE=auto` default) is a separate, pre-existing product
  behavior — the W2 data audit flagged the posture nuance (F-1, HIGH,
  owner-visibility): verification stays fail-closed (`verified=False`), and
  no AI research path can consume live data.
- **RECOMMENDATION-NOT-DECISION:** keep DENIED for this release; if the
  display-layer posture should change (e.g. force `DATA_SOURCE=mock` on
  install), that is a separate product decision — record it explicitly.
- **Work blocked:** any verified-live evidence, AI-2 real-data runs.

## R-4 — Comparative-phrasing rulings (C1–C8)

- **Question:** rule on the comparative phrases ("بهینه‌تر از/بهتر از
  tablokhani.com" etc.) inventoried with exact loci in
  `TABLOKHANI_CAPABILITY_MATRIX.md` §4 (README.md:3,
  `frontend/js/modules/render/watchlist_excellent.js:2,53`, adjacent
  archived/UI loci) under the 03:111 evidence rule?
- **Options:** (a) reword to evidence-backed neutral phrasing (repo-side edit
  after ruling); (b) keep with an owner-accepted disclaimer record; (c) keep
  unchanged (owner accepts the unsupported claim).
- **Consequence of silence:** phrases remain owner-gated findings; the
  capability matrix honestly reports 31/32 rows
  `NOT_COMPARED_WITH_EVIDENCE`.

## R-5 — AI-4 numeric budgets (sandbox/evaluator ceilings)

Proposal-only today (`AI4_SANDBOX_LIMITS_PROPOSAL.md`). Owner sets numeric
ceilings or accepts the proposal → budgets leave proposal class.

## R-6 — AI-5 proactive-research scheduler runtime

Distinct from the APPROVED D-AI-30 alert-ops cadence (already implemented and
kill-switched). Question: authorize the proactive-research scheduler runtime
(cadence/budget) per `AI4_AI7_P343_DEPENDENCY_MATRIX.md` §AI-5? Kill switch
default ENGAGED (`domain/proactive_research.py:102`).

## R-7 — AI-6 source classes + Two-Key parameters

Question: admit external-intelligence source classes and set Two-Key
parameters (`GOV40_AI2_PREREQUISITE_CHECKLIST.md` discipline). D-AI-29 stays
gate-deferred until formally changed.

## R-8 — AI-7 autonomy expansion (D-AI-31)

Evidence-gated; deferred posture remains in force until a dated owner act.

## R-9 — Governed-alert delivery channel + E6 wiring

Two related rulings: (a) authorize any delivery channel beyond the
type-closed `IN_PRODUCT_INBOX` (notifier/ws_hub edge — currently absent by
construction with an AST proof test); (b) wire confluence/screener board
events into governed admission (E6 — deliberately disconnected per the
D-AI-30 implementation record). Both are future-work items, not defects.

## R-10 — Publication authority

Standing grant vs per-cycle authorization for pushes through the authorized
deploy-key path (practice working to date: forward-only, remote read-back +
exact-SHA CI verification each cycle).

## R-11 — Final acceptance

After this cycle's consolidated records: the 17-role final audit
(`MASTER_FINAL_17ROLE_AUDIT_2026-11-02.md`) is ready for the owner's single
Role-1 acceptance act. Outstanding owner items above are precisely what
separates "implementation-complete up to owner gates" from "100% accepted"
(directive §11: no percentage manipulation; no defensible global percentage
exists without approved weights — phase-by-phase status is reported).

---

### Response template (copy, fill, return)

```
D1=  D2=  D3=  D4=  D5=  D6=  D7=
R-1 INSTALL=  (dated)
R-2 access=
R-3 live=
R-4 C1-C8=
R-5..R-8 =
R-9 channel/E6=
R-10 publication=
R-11 acceptance=
```
