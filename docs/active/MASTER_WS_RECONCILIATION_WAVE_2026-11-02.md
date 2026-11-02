# MASTER WS RECONCILIATION WAVE RECORD — 2026-11-02

Directive: "NEXT EXECUTION DIRECTIVE — FINAL EVIDENCE RECONCILIATION AND
REMAINING ROADMAP COMPLETION" (2026-11-02), work packages WS-1 … WS-9.
Companion records: `WS1_EXACT_SHA_EVIDENCE_2026-11-02.md`,
`AI_RUNTIME_CONNECTIVITY_MATRIX_2026-11-02.md`, superseding corrections in
`MASTER_FINAL_17ROLE_AUDIT_2026-11-02.md` §SC-1..3 and
`MASTER_WAVE2_EXECUTION_RECORD_2026-11-02.md` §6.

## WS-3 — Quantitative evidence reconciliation (reproduced, not selected)

Discrepancy: Wave-2 record said "400 seeded grids + procedure equivalence on
300 grids × 4 q-levels"; the 17-role audit said "700 seeded grids +
procedure equivalence".

Resolution procedure (directive: "Do not select a number without
reproducible evidence"):
1. Inspected the independent reference implementation
   (`d1_mtp_audit.py` — reference BH/Bonferroni written from the textbook
   definitions via a deliberately different code path: tuple-sort with index
   tie-break, running-min from +inf, clip-at-end).
2. Re-executed it at the final HEAD against
   `backend/app/domain/evaluation_statistics.py`: **D1 RESULT: ALL PASS —
   43/43 checks**, exact reproduction of the audit-time result.
3. Exact numbers established from the probe's own counters:
   - 400 grids (seed 20261102, m=1..48, 4 distributions) — BH + Bonferroni
     exact float equality vs reference + input-order invariance
     (3 comparisons per grid);
   - 200 grids (seed 777) — repr-level IEEE-double identity;
   - 300 grids × 4 q-levels {0.01, 0.05, 0.10, 0.25} = **1200 threshold
     comparisons** (seed 42) — adjusted-p acceptance == BH step-up rejection
     set (ties share fate);
   - 100 grids (seed 43) — rejection set closed under smaller p.
4. Reconciliation: **700 = 400 + 300** — the two headline populations summed.
   Both source statements describe the SAME passing evidence; "700 seeded
   grids" is not wrong as a total of the two headline checks but was
   presented alongside "procedure equivalence" as if it were an additional
   population, which double-describes the 300. The precise canonical form is
   the Wave-2 record's decomposition.
5. Corrections applied: dated superseding §SC-2 in the 17-role audit
   (table above replicated there); §6.2 currency note in the Wave-2 record.
   Historical text preserved verbatim everywhere; the discrepancy itself is
   documented, not erased.

## WS-4 — F-1 severity/disposition (two fields, kept separate)

| Field | Value | Evidence |
|---|---|---|
| Severity | **HIGH** (unchanged) | `W2_DATA_MARKET_INTEGRATION_AUDIT.md` findings register row F-1 |
| Class/disposition | **OWNER-GATED** | same row; escalation recorded in Wave-2 record §2.4 |
| Technical state | **UNRESOLVED in shipped product** (`DATA_SOURCE` default `"auto"`, `config.py:34`; startup + poll loop fetch public TSETMC at the network layer) | same row's loci (`main.py:108,116`, `providers.py:285-310`) |
| Verification-layer state | **Fail-closed, enforced, verified this wave**: `verified=False` (`config.py:284`), live→mixed downgrade, `is_verified_live` triple gate un-mintable | gate sweep at final HEAD |
| Remediation | **NONE repo-side** — the fix is a one-line default flip / explicit live gate, which changes shipped product behavior and needs owner ratification (R-3 note in the owner packet) | `OWNER_DECISION_PACKET_CONSOLIDATED_2026-11-02.md` §R-3 |
| Owner acceptance | **NOT ACCEPTED** — no owner answer recorded; packet remains open | packet response template |

The 17-role audit's "zero CRITICAL/HIGH open" aggregate prose is corrected
(§SC-3 there): one HIGH finding open AS AN OWNER DECISION; zero HIGH
findings requiring engineering action. Severity was NOT downgraded; the two
fields are now recorded separately everywhere.

## WS-6 — Authorized backlog dispositions (evidence-first)

### F-7 — in-flight refresh deduplication → RETAINED AS EXPLICIT DESIGN DECISION

Analysis performed before deciding (directive: "first determine whether a
safe implementation can preserve current semantics"):

- A single-flight gate (second concurrent `refresh(force=True)` joins the
  in-flight cycle) is implementable without lock inversion (gate acquired
  before any Phase-3 lock; joiners await completion), but it CANNOT preserve
  current semantics: `backend/tests/test_refresh_degraded_token_concurrency.py`
  — written for Q-1 and pinned by the no-test-weakening control — creates
  TWO concurrent forced cycles and asserts `len(provider.calls) == 2`
  (two independent provider fetches), and its interleaving orchestration
  (cycle B stalled mid-cycle while cycle A completes its Phase 3) REQUIRES
  two independent in-flight cycles to exist. Dedup would also change the
  second caller's response to the first cycle's fetch moment.
- Decision: retain the no-dedup design. Concurrency CORRECTNESS for
  simultaneous cycles is already guaranteed the other way — per-cycle
  degraded token (Q-1) + per-cycle source capture (F-2) make each cycle
  individually correct under interleaving; the cost is duplicated work,
  which is a bounded efficiency issue, not a correctness issue. The design
  decision is hereby explicit; the backlog label "semantics change" is
  resolved into this record.

### F-8 / F-9 — dead paths → RETAINED (removal excluded by directive; wiring = behavior change)

- F-8: `MarketDataProvider.load_cache()` (`providers.py:520-530`) has zero
  callers (grep: single definition). Wiring it would change startup data
  behavior (consume possibly-stale cache at boot) — product behavior change
  = owner class. Removing it is excluded by the directive ("do not remove
  behavior based solely on apparent lack of callers"). The cache file itself
  is still WRITTEN every successful cycle and is gitignored/rebuildable.
- F-9: `history_path` (`config.py:141`) is declared but referenced nowhere
  else. Removing a config field can break environment contracts
  (`ALPHA_ENV_CONTRACT.md` class); wiring it creates a new persistence
  path (owner class). Retained as a recorded inert declaration.
- Both are now explicit design decisions with this record as the citation.

### Remaining security/reliability hardening — C-3 completed (last unpinned action)

- Found and fixed this wave: `actions/upload-artifact@v4` (windows.yml) was
  the LAST tag-pinned third-party action (W2-SEC C-3 scope). Now pinned by
  the authoritative commit SHA `ea165f8d65b6e75b540449e92b4886f43607fa02`
  (v4.6.2), resolved via `git ls-remote` of the action repository and
  cross-checked against the release page; a contract test pins all actions
  in both workflows against tag-style references
  (`test_windows_workflow_gates.py`).
- Everything else AUTHORIZED in W2-SEC was already closed in `1b9d461`
  (C-1/C-3/C-4/C-5/C-6/C-12 + electron lockfile C-11) or Wave-3 (C-10
  holdout validator). Remaining findings are OWNER-GATED by the audit's own
  classification and stay with the owner packet: C-2 (0.0.0.0 launcher
  default), C-7 (retention deletes — would create NEW purge paths), C-8
  (WS query-param auth), C-9 (decrypt heuristic).

### Windows PowerShell syntax validation (W2-INST F3 authorized follow-up) — DONE

- Added a fail-closed **"PowerShell script syntax gate (W2-INST F3)"** step
  to `windows.yml` (position 2, before any install/boot step): parses all
  four shipped scripts (`scripts/windows/{install,start,validate_install,
  validate_alpha}.ps1`) with the real PowerShell language parser
  (`[System.Management.Automation.Language.Parser]::ParseFile`) on a real
  pwsh host and exits 1 on any parse error or missing script. Until this
  step, NO automation anywhere parsed the shipped scripts (W2-INST S2
  honestly recorded NOT-RUN-HERE; the sandbox has no pwsh).
- Pinned by `backend/tests/test_windows_workflow_gates.py` (5 tests): gate
  presence + fail-closed shape; exact script inventory (a newly shipped
  script MUST be added to the gate); ordering before boot and upload;
  `upload-artifact` SHA pin; zero unpinned `@vN` actions in either
  workflow. YAML validated by safe_load. The real parse executes on the
  windows-latest runner; CI verification of this commit therefore validates
  the gate end-to-end.

### P5/P6 integration and end-to-end gaps

- P5: COMPLETE within the D-AI-30 approved restricted scope (W2-ROAD);
  delivery-channel expansion and E6 wiring remain owner-gated (R-9) — no
  change made, none authorized.
- P6: internal lifecycle contracts now pinned (WS-5 wave: 14 collected
  tests, `test_p6_opportunity_lifecycle.py`); external legs (filings/
  disclosures ingestion, live feeds) remain owner-gated (D-AI-33/38 + live
  posture R-3).
- E2E: 7/7 repo-side (last full evidence W2-INST + windows-validation W6 on
  every push); target-machine Electron items stay with R-1/R-2.

### Capability-matrix / comparative-claim rulings

- R-4 (C1–C8 phrases) remains PENDING — no phrasing change is authorized
  without the owner ruling; the capability matrix's honest
  `NOT_COMPARED_WITH_EVIDENCE` reporting stands. No change made.

## Battery and integration verification of this wave

- Full battery at the implementation commit: **1535 passed / 1 skipped /
  2 warnings** = 1471 + 64 exact (16 AI-2 composition + 12 AI-3 scaffold
  44→56 + 10 AI-1/alert-ops + 14 P6 lifecycle + 7 AI-4 evaluator + 5
  Windows workflow gates).
- pyflakes clean over all touched/added files; workflow YAML safe_load OK.
- Gates unchanged: AI2_ENABLED=0 (`config.py:111`), verified=False
  (`config.py:284`), SYNTHETIC_OR_PAPER (`g2_gate.py:287`), AI-5 kill
  switch ENGAGED (`proactive_research.py:102`), zero `ai2` under
  `backend/app/api/`. No runtime caller added to any disconnected edge; no
  purge path added; no test modified/weakened/skipped/deleted — every
  battery addition is a new test or an append-only scaffold extension.
