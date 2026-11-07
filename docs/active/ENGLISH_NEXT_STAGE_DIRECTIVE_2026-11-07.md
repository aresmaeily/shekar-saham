# ENGLISH NEXT-STAGE DIRECTIVE — POST-MASTER-DIRECTIVE EXECUTION — 2026-11-07

Issued under: MASTER DIRECTIVE — COMPLETE WEBSITE, DESKTOP APPLICATION, AND PRODUCT ROADMAP GAPS (§14.12 deliverable). This document is the hand-off instruction for the NEXT execution stage. It binds any successor agent (or the owner's next session) to the same evidence-first discipline. It carries NO new authorization beyond the standing OWNER AUTHORIZATION & CONTINUOUS EXECUTION DIRECTIVE (OA-1..OA-8).

## §1 State at hand-off (facts, exact SHAs)

- Published chain: `27e36c9` (WAVE-S records + CI currency) → `b456570` (WAVE-T implementation: 12-journey SITE-2 fleet E2E + MR-I-02 embedded Python runtime + audit-ready validators) → `445e4fb` (independent-audit remediation: J02 honest-empty fix + wording precision) → this docs commit (WAVE-T completion record + Persian report §51–§54 + this directive + STATUS/CHANGELOG/INDEX currency).
- Exact-SHA CI at `b456570`: ALL 4 REQUIRED CHECKS SUCCESS (test-backend 128413854547 / build-docker 128414148771 / windows-validation 128413854724 / build-installer 128413854878 — the modified installer workflow green INCLUDING the embedded-runtime fetch + MD5 verification + local dependency bundle + import smoke).
- Battery: 3026 passed / 1 skipped / 0 failed (= 3006 + 12 journeys + 8 embedded-runtime pins, exact), reproduced in a clean-checkout reviewer clone ×2.
- Windows readiness validator: 47/47 (13 new EMBEDDED_RUNTIME_* + RUNBOOK_EMBEDDED_RUNTIME added).
- Canonical matrix: `MASTER_RADAR_WAVES_EXECUTION_RECORD_2026-11-07.md` §2 + the WAVE-T delta table (§6 of the WAVE-T completion record).

## §2 Next-stage work queue (all non-owner-gated items, in order)

1. **CI currency pass (OA-7)** — record the final conclusions of `445e4fb` (Windows validation run #63 id 42377136482 was in_progress at the WAVE-T record time; the installer run belongs to the same push) and of the docs commit that carries this directive. Record AS OBSERVED; never transfer CI success across SHAs; distinguish missing/failure/cancelled/flake; a docs-only delta is covered by the head runs per the recorded batched-push convention.
2. **Sandbox-state resilience** — this stage began with the sandbox restored to a pre-WAVE-Q snapshot while all published work survived on the remote. ANY future session must start with: `git fetch` → compare `HEAD` vs `origin/main` → if behind, byte-compare colliding untracked files against incoming tracked blobs → back up out-of-tree → `merge --ff-only` → read-back → re-run the battery. Never re-do published work from a stale local tree; the remote is the source of record.
3. **Runtime evidence cadence** — the only valid runtime-evidence form in this sandbox is per-invocation boot+probe (port-listening processes are recycled between tool calls — WAVE-Q §3 mechanism, re-confirmed WAVE-T §2). Keep using the integrated-script pattern for any new runtime claim.
4. **If the owner requests a UI/feature change** — the 12-journey file (`backend/tests/test_website_journeys_e2e.py`) is now the regression harness for the SITE-2 surface: every journey touched by a change must stay green, and the honest-state assertions (synthetic labels, closed AI-2 gate, empty-state tolerance) must NOT be weakened to make a change pass.
5. **If dependencies change** — `requirements.txt` pins must stay mutually compatible with the bundled runtime (cp312 wheels, `--only-binary=:all:`). Any new dependency must ship Windows cp312 wheels or the installer build fails (fail-closed by design). Re-check the import-smoke list in the workflow when core imports change.

## §3 Owner-gated action register (unchanged in substance; consolidated pointer)

- **OA-1 / R-1 / R-2 (target machine):** download the built installer from the CI artifact (30-day retention) or the recorded artifact name/size/SHA-256 from the public build log; verify SHA-256; install on the target machine; run the §2 runbook health check (`curl 127.0.0.1:<port>/api/health`); exercise upgrade/rollback per runbook §3–§4. The payload now ships its own interpreter + dependencies — nothing else must be installed first. Code signing remains unavailable (no certificate) — SmartScreen will warn; that is disclosed, not a defect to fix without a cert.
- **OA-2 / R-3 / R-7 (real market data):** provider admission, credentials, entitlements, and the real symbol universe remain owner decisions. Everything source-independent is done; nothing is invented until the owner admits a source.
- **OA-3 (AI-2 activation):** committed default `AI2_ENABLED=0` byte-unchanged; `verified=False`; SYNTHETIC_OR_PAPER; G2 NOT_PASSED. The 20-point acceptance + Two-Key procedure (per the standing directive) is unchanged and is the ONLY path to a controlled activation. WAVE-L's isolated-session evidence is NOT authorization to flip committed defaults.
- **OA-4 (scheduled operation):** `SCHEDULER_ENABLED=0` stands; enabling scheduled runs is an owner act.
- **OA-5:** the durable Prediction Registry is live at the committed default (SQLite WAL, append-only). No transfer of decision authority to any model, ever.
- **OA-6 (Vercel):** unchanged — optional non-gating pipeline; the root-cause report + owner packet live in the WAVE-S record §3 (`npx vercel inspect --logs` with an owner token, then disconnect-or-configure). The supported deployment model is the Docker/FastAPI monolith.
- **OA-7:** exact-SHA CI evidence discipline continues; nothing converted.
- **OA-8:** global completion stays **NOT CALCULATED** — no approved weighting exists.

## §4 Invariants that bind the next stage (§11 continuity)

Every gate and discipline in the standing directive remains in force verbatim: fail-closed gates; no egress; no broker/live path; no external notifications; no autonomous production mutation; no auto-promotion; named-human-approver-only; Two-Key; append-only ledgers with no purge surface; no owner-device access; no domain/credential/production-deployment changes; no test weakening (recorded counter-pin bumps only, never silently); forward-only history; honest 11-status-class matrix updates; the honesty envelope on every governed payload; and the rule that ALL claims are evidenced by runtime/clean-checkout/CI artifacts — never inferred from commit titles, green counts alone, labels, or mocks.

## §5 Definition of done for the next stage

The MASTER DIRECTIVE's §15 definition stands. At this hand-off, every non-owner-gated item on the WAVE-S §5 queue is CLOSED with recorded evidence (journeys E2E fleet = RUNTIME-VERIFIED; embedded runtime = INTEGRATION-VERIFIED with CI-green build proof; independent audit = 4/4 PASS 0 FAIL with remediations committed; Persian report + English directive = delivered). What remains is: the CI currency pass (§2 item 1), the owner's gated acts (§3), and whatever the owner directs next. Completion percentages are never computed (OA-8); each requirement stands at its own evidence level, stated separately, honestly.
