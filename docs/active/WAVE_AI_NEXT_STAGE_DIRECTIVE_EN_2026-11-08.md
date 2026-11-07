# NEXT DEVELOPER DIRECTIVE — WAVE-AI FOLLOW-UP (EN, 2026-11-08)

Repository: `aresmaeily/shekar-saham` · Canonical branch: `main`
Baseline for the next stage: the final HEAD of the WAVE-AI-ACCEPTANCE stage
(see `docs/active/WAVE_AI_ACCEPTANCE_EXECUTION_RECORD_2026-11-08.md` §10).

## Standing rules (non-negotiable, unchanged)

- Startup: fetch `origin/main`, resolve the exact 40-hex HEAD, verify
  ancestry, preserve untracked owner artifacts (byte-compare before any
  recovery; ff-only; never force-push/reset/rebase). If the branch advanced,
  use the actual current HEAD — never overwrite newer work.
- Gates unchanged and byte-pinned: `AI2_ENABLED=0`, `SCHEDULER_ENABLED=0`,
  `verified=False`, `SYNTHETIC_OR_PAPER`, G2 fail-closed, R-3/R-7
  KEEP-DENIED, Two-Key Rule, no broker/live trading, no autonomous
  promotion, no production mutation, no external notification egress, no
  credential exposure, no owner-gate bypass, no scheduler.
- Test discipline: 12-class coverage per implementation; never weaken
  assertions, never delete historical failures, never add unexplained
  skips; counter-pin bumps recorded only. Final commits must carry
  exact-SHA CI evidence for ALL FOUR required checks (`test-backend`,
  `build-docker`, `windows-validation`, `build-installer`) at the exact
  published HEAD — CI success never transfers across commits.
- Status vocabulary: IMPLEMENTED / TESTED / INTEGRATION-VERIFIED /
  RUNTIME-VERIFIED / OPERATIONALLY-VERIFIED / OWNER-GATED / PARTIAL /
  NOT-VERIFIED. Implementation is never operational readiness. Global
  completion % stays NOT CALCULATED (OA-8) until the owner approves a
  weighting model.

## Work packages (dependency order, continuous execution)

1. **AI-MA real reasoning seam (owner-gated prep only).** The runtime is
   ready for an LLM-backed executor behind the SAME SpecialistExecutor
   protocol: provider-adapter design doc + contract tests + fail-closed
   `ToolNotPermitted` seams + budget/timeout integration tests + honest
   SYNTHETIC_OR_PAPER labeling on any synthetic transport. Do NOT activate
   any provider; deliver the owner decision packet (provider, budgets,
   egress posture, kill switch, Two-Key coupling) and stop at the gate.
2. **AI-3 audit trail durable storage (prep for D1–D7 recorded decisions).**
   Mirror the prediction-store precedent: SQLite/WAL append-only adapter
   with pinned-digest migrations + per-row digests + verified backup +
   restore-refuses-unverified + tamper refusal; keep it DORMANT (no runtime
   caller; import-graph pin) until the owner wires it. The in-memory trail
   shipped in WAVE-AI is the deterministic reference.
3. **Golden Set v2 corpus growth.** Add cases per kind (interpretation
   conflicts beyond the HOLD condition, more resolver edge cases,
   extraction units/currencies, regime windows with gaps, calibration
   maturity edges); keep the digest-pinning discipline; extend the FP/FN
   accounting report; still NO superiority claim — a TabloKhani
   comparative study requires the owner-approved benchmark protocol first.
4. **AI-MA UI iteration from real usage.** Add per-step artifact content
   viewers (server-provided payloads only), a run-history panel (client
   session only, no persistence), and keyboard/palette integration via the
   existing command-palette registry. Keep api()-only, esc() everywhere,
   user-action-only, trust labels from server fields.
5. **Product-loop surface consolidation.** Surface the AI-3 audit trail
   read-only inside the product loops tab (audit rows are server-computed;
   render verbatim with trust labels), and expose the Golden Set v2 report
   (baseline/candidate columns, FP/FN totals, no-superiority banner) behind
   a versioned read-only endpoint when the owner requests it.
6. **Windows/installer:** no new work without owner R-1/R-2 results. If the
   owner reports an install outcome, record it verbatim (no conversion of
   failures), re-verify the four checks at the then-current HEAD, and
   update the runbook's honest sign-off matrix.

## Final deliverables for the next stage

Update the execution record with: exact baseline/final SHAs; commit-by-commit
summary; file-level evidence; test commands and counts; browser screenshots;
exact-SHA CI run/job IDs; 17-role matrix currency; owner-gated register;
residual gaps; invariant verification. Persian final report + English next
directive. Verify every claim against the real files before publication.
