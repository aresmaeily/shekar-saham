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
