# MASTER-RADAR WAVE-AG — AI-2, SCHEDULER & SECURITY BOUNDARY AUDIT + OWNER-GATED REGISTER — 2026-11-07

Directive source: MASTER CONTINUOUS CLOSURE DIRECTIVE §7 + §9. Code SHA: `b1d1c3c0dc08c038b90b7570ca2f6a668bbaaaad`.
Evidence basis: WAVE-AC auditors B/C/D live verification + this session's browser evidence + full
battery 3026/1s/0f after remediation.

## §1 Security-invariant verification (every default preserved, zero drift)

| Invariant | Required default | Verified state at `b1d1c3c` | Evidence |
|---|---|---|---|
| AI2_ENABLED | 0 | **0** (committed default, byte-unchanged) | `config.py:118`; browser posture `ai2_enabled: false` |
| SCHEDULER_ENABLED | 0 | **0**; boot log «scheduler gate closed (SCHEDULER_ENABLED=0) — not started» | `config.py:158`; runtime log |
| verified | False | **False**, structurally unmintable | `config.py:201-212/285,294-297`; auditor-B: no caller (incl. tests) can mint verified LIVE |
| Execution mode | SYNTHETIC_OR_PAPER | **SYNTHETIC_OR_PAPER** rendered in UI posture + generate responses | `ai2_generation.py:378`; browser J09 |
| Broker connectivity | none | none | auditor-B/C egress greps |
| Live trading | none | none | no order/broker path |
| Production mutation | none | none | no production-write path outside owner-gated seams |
| Autonomous promotion | none | promotion requires NAMED human approver, server-enforced | `ai2_governance.py:353-362` |
| Self-escalation | none | model has zero authority over approve/promote | OA-3 anchors rendered in UI |
| External notification egress | none | zero smtp/webhook/push matches in AI-2/scheduler modules; notifier seams disjoint & owner-gated | auditor-C grep + auditor-D S02 classification |
| G2 | NOT_PASSED prose / PASSED json — see §3 | fail-closed under EITHER verdict; gate_report hard-codes real_data_ai2_allowed False | auditor-C F-C11-1 + §3 wording |
| Two-Key | intact | intact | auditor-D presence verification |
| Kill switch (scheduler) | ENGAGED | ENGAGED; idempotency + disabled-refusal tests green | `internal_scheduler.py:266-335`; 316 AI-2/G2/scheduler tests passed |
| AI-2 ledger | append-only | tuple-backed, adversarial update/delete grep zero matches; browser J09: refusal leaves total=0 | `ai2_governance.py:299-419` |
| Injection resistance | layered | injection scanner 19 passed; obfuscation/quarantine suite green | auditor-D P03 |
| Candidate integrity | checksummed/tamper-verifying | registry approve/promote tamper fail-closed | `ai2_governance.py:782-820` |
| DSL sandbox | no eval/exec | typed-AST + RSL-1 whitelist; 26 hostile sources rejected; zero 500s | auditor-D S03; 76 sandbox tests |

## §2 Scheduler audit (fail-closed correctness)

- Default `SCHEDULER_ENABLED=0`; startup refuses to start the loop (boot log captured).
- Kill switch ENGAGED gates every tick even if a loop were started (defense in depth).
- Idempotency + recovery + persistence paths are test-covered (316-test AI-2/G2/scheduler subset).
- Alert-ops loop: the 60s in-product alert_ops loop starts with kill switches still gating every
  tick (boot log) — in-product delivery only, zero external send (D-AI-30 posture, browser J10).
- No scheduled external operations exist; activation = owner decision (OA-4 packet below).

## §3 Canonical G2/AI-2 wording (adopted; supersedes stale prose)

1. `docs/active/G2_GATE_STATE.json` records the owner decision verdict **PASSED** (2026-10-29,
   CONSOL-GOV-37, SHA-256-bound). Standing directive prose says **NOT_PASSED**. This record treats
   BOTH as recorded sources and notes: the runtime is fail-closed under EITHER verdict
   (`g2_gate.py` fail-closed; `ai2_service.gate_report()` hard-codes
   `NOT_PASSED`/`real_data_ai2_allowed: False`), and the AI-2 disabled posture does not depend on
   the discrepancy (`AI2_ENABLED=0`, `verified=False`, `SYNTHETIC_OR_PAPER` enforced
   independently). Owner clarification packet = §4 row R-G2 (zero-risk wording decision).
2. The AI-2 API surface EXISTS (`backend/app/api/ai2_generation_api.py`, mounted `/api/v10/ai2`)
   and is fully gated; with the committed default every generate returns
   `gated_not_executed`/`ai2_disabled` and the append-only ledger stays unchanged (browser J09
   with the refusal + `total=0`). Older "zero ai2 under app/api" claims are superseded
   (pre-WAVE-K wording). Nothing about the gate changed in this wave.

## §4 Owner-gated action register (unchanged gates; packets per directive §9)

For each: exact owner decision / current evidence / remaining action / risks / safe options /
recommended option / exact verification procedure. **No unrelated work is blocked by these.**

| Gate | Exact owner decision | Current evidence | Remaining action | Risks | Safe options | Recommended | Exact verification procedure |
|---|---|---|---|---|---|---|---|
| **R-1/R-2 Windows target install** | whether/when to install on the owner's actual machine + run the post-install drill | installer BUILT in CI (all 12 steps green, artifact 114.4 MB, identity recorded); Persian guide in-repo; first-launch needs NO system Python/pip/venv/network | download artifact (authenticated), hash-verify, install, run the 8-row post-install table, upgrade/rollback drill | unsigned binary (hash is the only integrity anchor); running unknown executables always carries risk | (a) verify hash + install; (b) verify hash + unzip-only inspection; (c) defer | (a) with the exact procedure below | follow `OWNER_WINDOWS_INSTALL_GUIDE_FA_2026-11-07.md` §1-§3 rows 1-8; record every result against the table |
| **R-3/R-7 live data providers** | choose providers, entitlements, credentials; Two-Key custody | fetch-then-label mechanism implemented; trust envelope cannot mint verified LIVE; synthetic default unchanged | provider selection + credential custody + dated R-3 amendment | cost, data-licensing, leakage of credentials | keep synthetic default; add ONE provider at a time behind Two-Key | keep default until the desktop install is accepted | after any credential: run dataquality coverage + verify trust envelope still refuses verified-LIVE until explicit entitlement recorded |
| **OA-3 AI-2 production activation** | whether AI-2 ever runs against real providers | full governance chain tested (94+ tests); browser-verified honest refusal; ledger append-only | activation decision only | model-generated strategy quality; over-trust | keep disabled; enable in paper-only sandbox first | keep disabled | if enabled: verify posture flips honestly, refusal path still works on disable, ledger records every run |
| **OA-4 scheduled ops / notifications** | whether any scheduler/external notification goes live | scheduler fail-closed, kill switch engaged, zero egress | activation decision only | unsupervised automation; external egress | keep off | keep off | if enabled: start with 1 job, verify idempotency + kill switch stops within one tick |
| **OA-6 Vercel housekeeping** | keep/disconnect/configure the optional pipeline | combined status `failure` (Vercel context) at b1d1c3c — recorded SEPARATELY from required checks; Docker/FastAPI is the required deployment model | decide + perform on Vercel side | none to the product (pipeline is non-gating) | disconnect; configure proper env; leave as-is | leave as-is until a public deployment is wanted | n/a (owner-side console action) |
| **R-G2 wording clarification (NEW, zero-risk)** | which G2 prose is authoritative (directive NOT_PASSED vs G2_GATE_STATE.json PASSED) | §3 above; runtime identical under either | one-line owner clarification | none (wording only; no gate depends on it) | confirm json; confirm directive prose; leave dual-recorded | leave dual-recorded with this canonical note | none required |
| **OA-8 global progress weighting** | supply an approved weighting model or keep NOT CALCULATED | all statuses are evidence-leveled per requirement; no global % claimed anywhere | approval of a weighting model (if wanted) | a wrong weighting creates false certainty | keep NOT CALCULATED | keep NOT CALCULATED | n/a |
| **Signing decision (NEW, optional)** | whether to code-sign future installers | artifact UNSIGNED by recorded policy | sign or keep unsigned | unsigned = SmartScreen warning; signed = certificate cost | keep unsigned + hash discipline | keep unsigned until public distribution | verify signature absence is disclosed in provenance (it is) |

## §5 Clean-checkout reproduction & security reproduction (directive §11 item 13)

- WAVE-T clean-checkout reviewer-clone battery ×2 at the published SHA carries forward (recorded).
- This wave: tracked tree at `b1d1c3c` verified clean; full battery re-executed post-remediation
  **3026 passed / 1 skipped / 0 failed (45.19s)**; readiness 47/47; YAML valid; node --check green;
  pyflakes clean; `git diff --check` clean; secret-pattern diff scan 27e36c9..b1d1c3c → 8 hits all
  code-identifiers, zero real credentials; entropy sweep clean; no `.env` committed.
- Test integrity: zero tests weakened/skipped/deleted in this wave (diff reviewed; the only test
  delta in the WAVE-T chain was the honest J02 shape-fix recorded at 445e4fb).
