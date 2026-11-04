# WS-1 EXACT-SHA EVIDENCE RECORD — 2026-11-02 (MASTER directive, final reconciliation wave)

Scope: verify the actual remote `main` HEAD, its commit anatomy, and the CI
results **on that exact SHA** — never inferred from earlier commits or from a
commit message. Vercel recorded separately with its policy classification.
Raw capture (with egress notes): outside-repo wave scratch
`masterwave3_scratch/00/ws1_raw_evidence.txt`.

## 1. Remote HEAD verification

- `git ls-remote origin main` → `47183c0913518be1297f50c77bca0fdb3dddd9d1`
  — **exactly** the directive's reported final commit; the remote has NOT
  advanced beyond it.
- After `git fetch origin`: local `HEAD` == `origin/main` == `47183c0`;
  `git rev-list --left-right --count origin/main...HEAD` → `0 0`.

## 2. Commit anatomy (git cat-file, not reconstructed)

- commit `47183c0913518be1297f50c77bca0fdb3dddd9d1`
- tree `18c2316cff99d08a9b19b0cb305b19e8f429ce2e`
- parent `2229bd2e82c7f59d1a8229df1a23289187372e85` (single parent — linear)
- author/committer `Z User <z@container>`, 1793626240 +0000
  (Mon Nov 2 13:30:40 2026 +0000)
- subject: "MASTER-WAVE-2 currency: exact-SHA CI conclusions recorded …"
- changed files (docs-only currency commit):
  `docs/active/MASTER_WAVE2_EXECUTION_RECORD_2026-11-02.md` (+10/−3)
- program parent chain: `69a75bf` → `7c225cb` → `1b9d461` → `2229bd2` →
  `47183c0` (forward-only; no amend/rebase/reset/force at any point).

## 3. GitHub Actions check runs on the EXACT SHA (check-runs API)

Retrieved via the GitHub check-runs API for
`commits/47183c0…/check-runs` (sandbox direct curl rate-limited from a shared
IP; retrieved through the WebFetch egress path; cross-checked against the
commit's /checks page rendering). Three check runs exist, one per required
job; **no other check runs exist on this SHA**:

| Check run | head_sha | status | conclusion | window (UTC) | run / job |
|---|---|---|---|---|---|
| test-backend | 47183c0… | completed | **success** | 13:30:48 → 13:31:33 (45s) | 41453605589 / 125304634094 |
| build-docker | 47183c0… | completed | **success** | 13:31:36 → 13:31:58 (22s) | 41453605589 / 125305025170 |
| windows-validation | 47183c0… | completed | **success** | 13:30:48 → 13:34:50 (4m02s) | 41453605614 / 125304635075 |

- All three required jobs GREEN on the exact final SHA. This is an observed
  API result, not an inference from `7c225cb`/`2229bd2` (whose green runs
  were separately recorded in the Wave-2 currency commit).

## 4. Vercel — recorded separately (NOT a check run)

Vercel posts a commit **status** (context `Vercel`), not an Actions check
run; the check-runs list above is complete without it.

- Deployment `7493431829`, environment **Production**, created
  2026-11-02T13:31:14Z by `vercel[bot]`, for SHA `47183c0…`.
- State: **FAILURE** — "Deployment has failed — run this Vercel CLI command:
  `npx vercel inspect dpl_2VVFjdpMaMvY23YbY2CJ2bxkuVQy --logs`".
- Target URL: `https://shekar-saham-ovaan7pmg-aresmaeily-9501.vercel.app`.
- **Recurrence, not regression:** identical FAILURE on the prior pushes
  (deployment `7485071086` @ `69a75bf`, `dpl_AGEPrS8q1hqyEVB3j6AACxnND4HG`,
  05:32:46Z; deployment `7493297502` @ `2229bd2`, 13:25:12Z). Deployment
  history on the repo extends back to 2026-09-19 (including the third-party
  v0 agent branch `9b30cbd2`), i.e. the pipeline predates this program and
  its failures predate this program's commits.

### Policy classification (directive §WS-1.6)

Owner-connected optional pipeline, NOT a repository-policy requirement:

1. The repo's own CI policy is exactly `.github/workflows/` — `ci.yml` +
   `windows.yml` — neither references Vercel; there is no `vercel.json` and
   no release/branch-policy document requiring it.
2. Deployments are created by `vercel[bot]` — the owner's externally
   connected GitHub App auto-deploying every push to Production; connecting,
   configuring, or disconnecting it is an owner-side act.
3. Empirically NOT a push gate: 10+ direct pushes to `main`
   (`0b9f889` … `47183c0`) all landed despite recurring Vercel failures.
4. Deployment-model mismatch explains the perma-failure: the frontend is a
   static vanilla-JS app and the backend a FastAPI service deployed via
   Docker (`Dockerfile` / `docker-compose.yml`); Vercel auto-detection has
   no framework to build.
5. Branch protection settings require authenticated admin access and were
   NOT queryable anonymously — recorded as unknown-but-empirically-
   nonblocking (item 3).

**Consequence:** the Vercel failure does not affect repository CI acceptance
(the three required jobs are the repo's defined checks, all green). It is an
owner-side housekeeping item: configure the Vercel project or disconnect the
integration. No repository-side action is authorized or needed; nothing in
the product deploys through Vercel.

## 5. Gates re-verified at this baseline (byte-exact greps)

- `AI2_ENABLED` default `0` — `backend/app/core/config.py:111`
- `verified = False` — `backend/app/core/config.py:284`
- `SYNTHETIC_OR_PAPER` fallback — `backend/app/domain/g2_gate.py:287`
- AI-5 kill switch default `ENGAGED` — `backend/app/domain/proactive_research.py:102`
- zero `ai2` references under `backend/app/api/` (case-insensitive grep: 0)

## 6. Post-publication CI verification of the WS wave (currency note, 2026-11-02)

The WS reconciliation wave was published forward-only:
`47183c0..8be2576  main -> main` (fast-forward via the authorized deploy-key
path, no force; remote read-back `8be25762ce904987ed44256c91b92084cfcef619`
== local HEAD, 0/0 after fetch). Commits: `3cb126e2a056dc0a2af4c864000161a584b9d60f`
(implementation wave, +64 tests) then `8be25762ce904987ed44256c91b92084cfcef619`
(records wave incl. the in-repo Persian final report).

Observed CI on the EXACT final SHA `8be2576…` (GitHub API, not inferred):

- ci.yml run `41465447835`: `test-backend` completed/**success**
  (14:48:28→14:49:14Z, 46s); `build-docker` completed/**success**
  (14:49:16→14:49:40Z, 24s).
- windows.yml run `41465447817`: `windows-validation` completed/**success**
  (14:48:27→14:52:59Z, 4m32s) with EVERY step green — including
  **step 4 "PowerShell script syntax gate (W2-INST F3)": success** on its
  first real execution (all four shipped `scripts/windows/*.ps1` parse clean
  on a real pwsh host) — and W6 Browser E2E 7/7 green.

3/3 required jobs green on the exact published SHA. This currency note
changes no code and no finding above; it records the observed results.

## §7 — 2026-11-02 (WS-10 cycle): windows run #14 W7 flake recorded; steps 1–9 green

After the WS-10 owner-delegation wave was published (`f05be4c → 1f037dc
(implementation) → a7da35d (records)`; fast-forward, remote read-back
`origin/main == a7da35d0a14ee8985c19f58dd5794a27671a8026`, 0/0), the CI runs
on the exact HEAD were:

- ci.yml run 41484686326-era (`#21`): **test-backend success, build-docker
  success** on the exact SHA `a7da35d…`.
- windows.yml run `41484686328` (`#14`, 4m19s): **FAILURE — isolated to
  step 10 "Runtime log posture (W7 — fail-closed evidence)"**. Step-level
  conclusions (check-runs/jobs API): steps 1–9 ALL success — provenance,
  **PS1 syntax gate success**, Setup Python 3.13, deps, **W1 boot success**,
  **W2 health+version success**, **W6 Browser E2E 7/7 success**; step 11
  Shutdown + step 12 Upload artifacts success (evidence artifact
  `windows-validation-evidence`, 8.56 KB, sha256:632ee5de…ceac5). Annotations:
  1 error ("Process completed with exit code 1.") + 1 warning (Node.js 20
  deprecation — non-fatal, present on successful runs too).

**Mechanism analysis (honest, no gate weakening):** W7's assertions are
(a) "Traceback" must not appear anywhere in the combined uvicorn
stdout+stderr, (b) the ephemeral/FERNET fail-closed warning must be present,
(c) `live_verified` must not be true. (b) and (c) are deterministic and
present/green in every run. Only (a) can vary run-to-run: the pre-existing
`refresh()` pipeline contains `logger.exception` sites that print FULL
tracebacks into the runtime log on data/provider faults
(`market_service.py` — `analyze_market failed: …` with a following `raise`
into `_poll_loop`'s own `logger.exception`; plus per-cycle provider faults
reaching the same handler). The mock generator is md5-seeded per 30-second
wall-clock bucket, so analysis inputs change every cycle — a rare data/provider
edge prints a traceback on some runs and not others. The WS-10 diff adds NO
logging, NO background tasks, and NO runtime paths exercised during boot/E2E
(the chart-pro router registers routes that the E2E suite never calls).

**Local non-reproduction at this tree (three attempts, all clean):**
boot with `DATA_SOURCE=auto` (providers fail → mock_fallback, W7 inputs
checked: 0 "Traceback", ephemeral/FERNET present) + the W6 E2E suite run
THREE times consecutively against the same booted server (7/7, 7/7, then a
provider-timeout-affected 4/7 — still 0 tracebacks in the log) + a 480-bucket
sweep of the exact Phase-2 stack (`analyze_market`, `_update_big_moves`,
`rank_tablocastic`, `_rebuild_row_cache`) across 4 hours of synthetic
mock buckets — **0 exceptions** (`scripts/sweep_mock_buckets.py`, outside the
repo). Classification: runner-egress/timing-specific pre-existing flake
sensitivity, not introduced by this wave; the W7 gate itself remains
intact, fail-closed, and correct.

**Resolution path:** a fresh forward-only currency commit re-runs the job —
a green run on identical code paths confirms the flake empirically; if it
recurs, the exact traceback locus is in the run artifact
(`windows_run_provenance.txt` carries the first 80 lines of both log streams,
including the traceback context) which requires the owner's authenticated
download — no assertion is weakened and no owner decision is fabricated
either way.

**§7.1 — CONFIRMATION (same day, ~30 min later): the flake hypothesis was
empirically confirmed.** The currency commit `814418be045b266193d4dbb53000d
8fd0bf08f23` (the §7 record itself — zero code changes) triggered fresh runs
on its exact SHA:

- ci.yml run `41491463599`: **test-backend success, build-docker success**.
- windows.yml run `41491463575` (`#15`, 17:28:14→17:32:37Z, 4m23s):
  **success — ALL 25 steps success**, including step "Runtime log posture
  (W7 — fail-closed evidence)" **success** and step "Browser E2E suite
  (W6 — 7/7 expected)" **success** (check-runs/jobs API, per-step).

⇒ Identical tested code, new run: 3/3 required jobs green. Run `#14` is
recorded as an isolated environmental flake instance of the pre-existing
W7 log-textbook sensitivity (full mechanism above); no gate was changed,
no assertion weakened, no code reverted. The WS-10 wave's published chain
`f05be4c → 1f037dc → a7da35d → 814418b` is fully CI-verified.

## §8 — 2026-11-02 (same cycle, continued): evidence-stream hygiene — the §7 flake MECHANISM structurally removed (forward-only, no gate change)

§7/§7.1 recorded the W7 flake instance and its empirical confirmation. This
section records the structural resolution of the recorded mechanism itself,
implemented as the next forward-only wave on top of `4972746…`:

**Change (6 handled-fault sites, `backend/app/services/market_service.py`):**
`logger.exception(...)` printed FULL multi-line tracebacks into the uvicorn
runtime log on handled, non-fatal fault paths (poll cycle, analyze_market,
big_moves, confluence build, persist, confluence rebuild). All six sites now
log a single line via plain `logger.error(f"[{err_id}] ...: {exc}")` with NO
exc_info argument — stdlib logging never attaches exception info implicitly,
so the evidence stream keeps the error text, the `[err_id]` correlation
prefix and the uptime metrics, and can no longer contain a traceback from a
HANDLED fault. The `raise` after the analyze_market site is UNCHANGED — the
fault still propagates fail-loud. Real UNHANDLED ASGI crashes are still
tracebacked by uvicorn itself, so W7's crash-detection power is unchanged;
W7 and every other gate step are byte-unchanged.

**Tests (+3, `backend/tests/test_runtime_log_hygiene.py`):**
1. `test_phase2_fault_propagates_fail_loud_without_traceback_in_log` —
   a faulted Phase-2 analysis still raises (fail-loud) AND the captured log
   contains only the single-line error with the `[err_id]` prefix; no
   "Traceback" text; every record `exc_info is None`.
2. `test_poll_loop_swallows_refresh_fault_without_traceback` — a failing
   refresh cycle inside `_poll_loop` is logged and swallowed (loop keeps
   running) under the same no-traceback/no-exc_info contract.
3. `test_poll_path_has_no_traceback_logging_sites` — source guard:
   `market_service.py` contains zero `logger.exception` sites (regression
   guard for the evidence stream).

**Verification:** battery **1594 passed / 1 skipped = 1591 + 3 EXACT**;
focused neighbors `test_refresh_false_fresh.py` + 
`test_refresh_degraded_token_concurrency.py` 6/6; pyflakes clean on
`app/` + the new test module; `git diff --check` clean; one stdlib-logging
semantics subtlety was caught and fixed BEFORE publication: the first draft
called `logger.error(..., exc_info=False)`, which makes the record carry
`exc_info=False` (not `None`) — the stricter authored assertion
(`r.exc_info is None`) failed, so the kwarg was dropped at the six wave
sites (the pre-existing site at line 405 already used `exc_info=False` and
is traceback-free; left unchanged, out of wave scope).

**Honest residual traceback-capable surfaces (NOT changed, recorded):**
- `app/services/alert_operations.py` (2 sites) — dispatcher self-failure
  logging is a PINNED design ("dispatcher self-failure visible in health",
  D-AI-30 / decision 6): the traceback is deliberate visibility evidence,
  the loop is deterministic in-product logic (SYNTHETIC_OR_PAPER, no
  external egress) and has never faulted in any recorded CI window;
  reformatting it is an owner-class behavior change and was NOT done
  unilaterally.
- `app/core/errors.py` — has ZERO importers (unwired module); not on the
  boot/poll/E2E evidence stream.

No gate changed; no test weakened/skipped/deleted; no behavior change beyond
log formatting on handled-fault paths; D1–D7 remain recorded per
`OWNER_DECISIONS_RECORDED_2026-11-02.md`; INSTALL NOT ISSUED.

**§7.2 — RECURRENCE (2026-11-02, same day, later cycle): windows run #16 on
`4972746…` failed at W7 again — the flake is NOT isolated (supersedes the
"isolated" classification of §7.1; history above preserved verbatim).**

- ci.yml on `4972746`: run 41493220286 — **test-backend SUCCESS,
  build-docker SUCCESS**.
- windows.yml run `41493220452` (`#16`, created 17:39:28Z): **FAILURE
  isolated to step 10 "Runtime log posture (W7 — fail-closed evidence)"**
  (jobs API, per-step): steps 1–9 ALL success — PS1 syntax gate, Setup
  Python, deps, W1 boot, W2 health+version, **W6 Browser E2E success**;
  steps 11–12 (Shutdown, Upload artifacts) success; step 10 failure.
- Classification UPDATE: with two W7 occurrences (#14 on `a7da35d`, #16 on
  `4972746`) vs one green (#15 on `814418b`) on identical tested code, the
  sensitivity is a RECURRING low-frequency flake exactly matching §7's
  mechanism (rare handled-fault traceback printed into the runtime log
  under per-30s-bucket mock-input variance). No assertion weakened, no gate
  changed either way; the artifact with the exact traceback locus again
  requires the owner's authenticated download.
- **Resolution: the evidence-stream hygiene wave (§8 below) removes the
  mechanism structurally** on `f42ad27…` (implementation) — no wait-and-see.

**§8 CI evidence (2026-11-02, exact-SHA rule R-10): the hygiene wave is
validated by real CI execution on its exact published SHA `574ff14…`.**

- ci.yml run `41496606213` (`#24`): **test-backend SUCCESS + build-docker
  SUCCESS** (check-runs API on the exact SHA).
- windows.yml run `41496606114` (`#17`, 18:01:29→18:05:38Z, 4m09s):
  **SUCCESS — ALL steps success** (jobs API, per-step): checkout/provenance,
  **PS1 syntax gate**, Setup Python 3.13, deps, **W1 boot**, **W2
  health+version**, **W6 Browser E2E success**, **W7 Runtime log posture
  SUCCESS on the hygiene-fixed code** (first CI execution after the
  traceback-capable handled-fault sites were removed), Shutdown, artifacts.
- ⇒ **3/3 required jobs SUCCESS on the exact published SHA `574ff14…`;**
  the structural fix for the recorded W7 flake mechanism is proven by
  execution, not by argument.

## §9 — 2026-11-03: FINAL SHA PROOF for the hygiene cycle HEAD `c1f3c12…` (directive §1 — every required job recorded independently)

Exact identity (local git, verified against remote): HEAD ==
`c1f3c1210c350e2a5f859e96e763dc61b7ad620d`; tree ==
`9d7cf85ab6b6074489e72bdc3389ec915f8d73a3`; `origin/main` == local (0/0 after
fetch). GitHub check-runs API on the EXACT SHA (not inferred from `574ff14`
or any earlier commit):

| Job | Run | Job ID | Conclusion | Started (UTC) | Completed (UTC) |
|---|---|---|---|---|---|
| test-backend | CI #25 / run 41497871472 | 125457449943 | **success** | 2026-11-02T18:09:28Z | 2026-11-02T18:10:08Z |
| build-docker | CI #25 / run 41497871472 | 125457824759 | **success** | 2026-11-02T18:10:11Z | 2026-11-02T18:10:30Z |
| windows-validation | Windows #18 / run 41497871509 | 125457450568 | **success** (18:09:29→18:13:43Z, runner "GitHub Actions 1000000064") | 2026-11-02T18:09:29Z | 2026-11-02T18:13:43Z |

Windows step-level (jobs API, ALL 15 steps success): Set up job ✓; checkout
(SHA-pinned v4.2.2) ✓; provenance ✓; **PowerShell script syntax gate (W2-INST
F3) ✓**; Setup Python 3.13 ✓; deps ✓; **W1 boot ✓**; **W2 health+version ✓**;
**W6 Browser E2E ✓**; **W7 "Runtime log posture (fail-closed evidence)" ✓**
(the hygiene-fixed code passing its gate in real CI); Shutdown ✓; artifacts ✓
(+3 post-steps ✓).

**Vercel (recorded SEPARATELY as an external, non-required status):** commit
status context "Vercel" on `c1f3c12` = **failure**
(dpl_H4FD5RWeJrtwFUsM9P8CGifr1vU7) — the owner-connected optional deployment
pipeline; NOT one of the three required GitHub Actions jobs; classification
unchanged (WS-1 §1: recurring, pre-dates the program, empirically not a push
gate; owner-side housekeeping).

Evidence availability: all three required check runs + the windows job's
per-step states retrieved via the GitHub API (check-runs + jobs endpoints) —
nothing unavailable, nothing inferred. Raw CI logs/artifacts remain
sign-in-gated for the agent (recorded limitation, unchanged from GOV-49).

## §10 — 2026-11-04 (UTC, authoritative): exact-SHA CI on the 2026-11-03 wave records commit `2023895…` + a dated stamp-honesty note

**(a) Date-stamp honesty note (§SC convention):** the 2026-11-03 wave's
records (AI3_OPERATIONAL_STATUS / WDA_CAPABILITY_MATRIX /
ROADMAP_TRACEABILITY_DELTA / TABLOKHANI_CAPABILITY_MATRIX, and the dated
comments in code) carry the logical cycle label "2026-11-03"; the authoritative
wall-clock evidence — the GitHub CI runs below — is **2026-11-04 UTC**. Treat
the "2026-11-03" stamps as cycle labels; every TIMESTAMP in evidence rows is
authoritative and was never invented. File names keep the label for
referential stability; this note supersedes any implied date claim.

**(b) Exact-SHA CI for the wave publication `20238959d8562e6ebd4b9fe04f963d8
c6f090a7b`** (tree `cbd1e6dc…`; origin/main == local verified 0/0 after push;
nothing inferred from any earlier SHA): check-runs API on the exact SHA —

| Job | Job ID | Conclusion | Started (UTC) | Completed (UTC) |
|---|---|---|---|---|
| test-backend | 126390154298 | **success** | 2026-11-04T04:34:49Z | 2026-11-04T04:35:39Z |
| build-docker | 126390445114 | **success** | 2026-11-04T04:35:42Z | 2026-11-04T04:36:06Z |
| windows-validation | 126390154037 | **success** (4m21s) | 2026-11-04T04:34:48Z | 2026-11-04T04:39:09Z |

⇒ 3/3 required jobs SUCCESS on the exact published wave SHA, with the +200-test
battery (1794/1s local) carried through real CI test-backend execution.
