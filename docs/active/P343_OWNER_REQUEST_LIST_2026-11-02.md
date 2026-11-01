# P3.43 / PROGRAM — CONSOLIDATED OWNER REQUEST LIST

Created: 2026-11-02 (MA-1 consolidated multi-agent cycle).
Single authoritative list of owner-only inputs. Every repository-side task
that does not need owner environment access has been completed or is tracked
in `docs/STATUS.md`; nothing below can be advanced by the engineering team.

---

## R-1. `INSTALL` instruction (hard gate — nothing installs without it)

The owner must issue an explicit, dated `INSTALL` instruction for the
Controlled Alpha Launch (P3.43). All records to date: installation NOT
STARTED; "Do not install until owner says INSTALL."

## R-2. Windows target-machine access (or owner-executed run)

One session (or owner-executed sequence) on the target Windows machine for:

1. `scripts/windows/validate_install.ps1` → `install.ps1` → `start.ps1` →
   `validate_alpha.ps1` (exact sequence in `docs/active/P343_INSTALL_CHECKLIST.md §2`).
2. Browser E2E on the target browser (canonical P3.43-2 — `e2e/` suite
   against the locally booted app).
3. Interactive Electron checks W2-icon + W3–W5 shell navigation (not
   automatable in CI; `windows.yml` header).
4. Row-by-row recording into `ALPHA_INSTALLATION_CHECKLIST.md` +
   `ALPHA_TARGET_VALIDATION_CHECKLIST.md`.

Red line restated: the green `windows-validation` CI job on `7c72f3d5…` is
NOT proof of installation on the target computer.

## R-3. Live-provider posture (currently DENIED — a future dated act, or explicit acceptance)

`OA-AI2-LIVE-CREDENTIALS` / `OA-AI2-ENABLEMENT` are **DENIED FOR THE CURRENT
RELEASE — CLOSED** (GOV-41 Phase 2). The owner either:

- (a) accepts the controlled alpha as synthetic/paper-labeled non-live
  (`live_verified=false` preserved — no action needed), or
- (b) issues a NEW dated owner act re-opening the decision and provides
  `BRSAPI_KEY` (currently missing) / accepts a TSETMC reachability validation
  on the target. No credential may ever be pasted into chat or repository
  files (binding boundary 5).

## R-4. AI-3 persistence decisions D1–D7 (all PENDING)

Answer in one reply using the per-decision reply templates in
`docs/active/AI3_PERSISTENCE_DECISION_PACKET.md` (seven decision questions,
each with option tables across the seven evaluation dimensions; no decision
is assumed and none has been recorded). Until answered, the persistence
adapter stays BLOCKED and only interface/fixture preparation is done
(delivered: `backend/app/domain/research_memory_store.py` + acceptance kit).

## R-5. Publication confirmation (informational)

The engineering team is authorized (Part V of the current directive) to
publish forward-only changes via the existing deploy-key path with remote
read-back + CI verification on the exact SHA. This list records that the
current cycle's commits were published under that authority; no separate
owner act is required unless the owner withdraws it.

---

## Explicitly NOT requested (already resolved)

- G2 acceptance — PASSED, owner-recorded 2026-10-29 (CONSOL-GOV-37).
- D-AI-30 synthetic alert operations — APPROVED under ten binding decisions
  (GOV-41).
- GitHub publication of the historical chain — DONE (GOV-48/49).
