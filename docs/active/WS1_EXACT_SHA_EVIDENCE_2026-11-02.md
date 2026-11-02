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
