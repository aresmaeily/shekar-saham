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

---

## ADDENDUM — 2026-11-02 final reconciliation wave (WS-9; nothing below is a decision)

Status after the WS reconciliation wave (exact remote HEAD verified
`47183c0913518be1297f50c77bca0fdb3dddd9d1`; WS-5/WS-6 authorized
implementations committed; records: `MASTER_WS_RECONCILIATION_WAVE_2026-11-02.md`,
`AI_RUNTIME_CONNECTIVITY_MATRIX_2026-11-02.md`, `WS1_EXACT_SHA_EVIDENCE_2026-11-02.md`,
`AI3_IMPLEMENTATION_READINESS_RECORD_2026-11-02.md`,
`TARGET_MACHINE_EVIDENCE_CHECKLIST_2026-11-02.md`).

### Exact current blockers (unchanged in kind; sharpened in evidence)

| ID | Blocker (distinct) | Consequence of continued silence | Independently executable meanwhile? |
|---|---|---|---|
| D1 | AI-3 persistence backend | adapter stays blocked; nothing else blocked | YES — readiness record + 56-test scaffold complete |
| D2 | Windows target access (AI-3 axis) | target-machine validation for AI runtime | YES — repo-side only work proceeds |
| D3 | Retention policy by data class | storage sizing only; NO purge path will be built for episodic evidence regardless | YES |
| D4 | Encryption + key management | at-rest encryption layer | YES — options designed (readiness record §2) |
| D5 | Backup destination + cadence | automated research-memory backup schedule | YES — product-DB backup exists |
| D6 | Access-control model | shared-machine posture | YES |
| D7 | RPO/RTO numbers | recovery drill thresholds | YES |
| R-1 | INSTALL instruction (hard gate, NOT ISSUED) | no installation on the owner machine | YES — Phase-0 prereqs and checklist prep only |
| R-2 | Target-machine validation access | W2/W3–W5 + P3.43-2 evidence stays TARGET-MACHINE-ONLY | YES — checklist Phase-8 bundle spec ready |
| R-3 | Live provider posture (includes F-1 HIGH display-layer nuance) | verified-live evidence impossible; F-1 stays HIGH/OWNER-GATED/technically-unresolved | YES — everything synthetic/paper proceeds |
| R-4 | C1–C8 comparative phrasing rulings | phrases stay owner-gated findings; matrix honestly reports 31/32 NOT_COMPARED_WITH_EVIDENCE | YES |
| R-5 | AI-4 sandbox numeric budgets | budgets stay proposal-class | YES — evaluator coverage extended (WS-5) |
| R-6 | AI-5 proactive-research scheduler runtime | scheduler stays absent; kill switch ENGAGED | YES |
| R-7 | AI-6 source classes + Two-Key params | ingestion stays absent | YES |
| R-8 | AI-7 autonomy expansion (D-AI-31) | evidence-gated; deferred posture in force | YES — evidence cannot exist yet |
| R-9 | Governed-alert delivery channel + E6 wiring | notifier/ws_hub edges stay absent by construction | YES |
| R-10 | Publication authority (standing vs per-cycle) | per-cycle authorization remains the working practice | YES — forward-only + exact-SHA CI each cycle |
| R-11 | Final acceptance (owner Role-1 act) | "implementation-complete up to owner gates" ≠ "100% accepted"; percentage honestly NOT_CALCULATED | YES — all evidence packages ready for the act |

### Independently executable now (no owner input required)

All repo-side synthetic/paper work: battery-verified implementation, records
currency, Windows workflow gates, AI-3 readiness (not implementation), E2E
maintenance, docs. The queue of authorized repo-side items from the W2 audits
is EMPTY after this wave (WS-5/WS-6 executed; dispositions recorded for
F-7/F-8/F-9; C-3 completed with the upload-artifact SHA pin; W2-INST F3
PowerShell gate added). Next progress on the blocked classes requires dated
owner answers to the IDs above — partial answers are valid and unblock only
their own row.

### Vercel (new housekeeping item, owner-side, non-blocking)

The owner-connected Vercel GitHub App fails its Production deployment on
every push (recurring since before this program; NOT a repository-policy
check — the repo's three required Actions jobs are green on the exact HEAD).
Owner may configure the Vercel project or disconnect the integration; no
repository-side action exists or is needed. Evidence:
`WS1_EXACT_SHA_EVIDENCE_2026-11-02.md` §4.

## ADDENDUM-2 — 2026-11-02 (owner chat delegation executed; supersedes PENDING statuses below)

On 2026-11-02 the owner issued a chat directive enumerating the gate set and
**explicitly delegating the selection** ("به دقت بهترین تصمیم رو با دلیل بگو
به نحوی که همین الان انجام بشه…"). The full decision set with per-row
reasoning is recorded in **`OWNER_DECISIONS_RECORDED_2026-11-02.md`** — each
decision subject to owner veto by a dated reply. Answer key:
`D1=A(SQLite-WAL+blobs), D2=DEFER-2026-11-02, D3=PERMANENT-TABLE, D4=KEYRING+AESGCM,
D5=LOCAL-DAILY-KEEP14, D6=SINGLE-USER, D7=RPO24h-RTO15m, R-1=OWNER-ISSUED-INSTALL,
R-2=OWNER-EXECUTES-BUNDLE, R-3=KEEP-DENIED, R-4=REWORD, R-5=ACCEPT-PROPOSAL,
R-6=DORMANT-MANUAL-ONLY, R-7=NO-EXTERNAL-CLASS+TWO-KEY-REQUIRED,
R-8=NO-EXPANSION, R-9=INBOX-ONLY-E6-DISCONNECTED, R-10=STANDING-GRANT-FORWARD-ONLY,
R-11=READY-FOR-ACT`.

Executed consequences in the same cycle: D1–D7 → production adapter
`backend/app/data/research_memory_sqlite.py` (factory #3 in the acceptance
scaffold; not auto-wired — engine activation remains a separate gate);
R-4 → the three live loci reworded (`README.md:3`,
`frontend/js/modules/render/watchlist_excellent.js:2,53`; archived docs
untouched); R-5 → accepted verbatim for the future runtime integration; WS-10
chart-pro wave delivered per `WS10_CHART_PRO_DIRECTIVE_2026-11-02.md`.
Rows above marked PENDING reflect the pre-delegation state and are preserved
verbatim for history; this addendum is the dated superseding record.
