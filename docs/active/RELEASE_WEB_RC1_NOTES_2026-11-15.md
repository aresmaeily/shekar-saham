# RELEASE NOTES — Web Release Candidate 1 (release/web-rc1)

- **Date:** 2026-11-15 (Asia/Tehran)
- **Branch:** `release/web-rc1` — forward-only from origin/main `7a41563968dc5ac5d57f5f3d7ac3a674e735ee58`
- **Commits this RC:** `287f349` (D-O2 implementation + P2 gap closures) → `b8f27ba` (CI enablement for the RC branch) → docs commit (this file; the final SHA is recorded in the Persian final report)
- **Release verdict:** see the Persian final report (`RELEASE_WEB_RC1_FINAL_REPORT_FA` in download/). Required checks: `test-backend`, `build-docker`, `windows-validation`, `build-installer` — all four run on every RC SHA and must be green on the exact final SHA.

## 1. What is new in RC1

### D-O2 Filter-Compose continuation (owner-approved, additive)
- New engine `backend/app/engines/filter_compose.py`: the recovered 8-filter catalog
  (provenance + rationale per filter), independent per-filter evaluation, per-filter
  error recording (never silent), conjunction match counting, `min_matches` 1..8
  (رانتی rule = ≥2), ranking `match_count desc → golden_number desc → entry_score
  desc → symbol asc`, blank-symbol exclusion, read-only enrichment, degenerate
  market-context disclosure, explicit `NOT_SUPPORTED` disclosures.
- Overlap-only comparison metrics `golden_set_comparison.py`:
  `OVERLAP_ONLY_NO_SUPERIORITY_CLAIM` / `NOT_MEASURED` labels only.
- API: `GET /api/filter/compose/presets`, `POST /api/filter/compose` (engine-side
  400 semantics, `data_trust` passthrough verbatim).
- Frontend: «تحلیل چندبعدی» panel in the existing filter tab (preset checkboxes with
  provenance chips, custom expressions, min-matches control, match-count table with
  matched-filter chips, honest mock trust header, error chips). sw v3-0-21.

### P2 gap closures (previously honestly recorded as remaining)
- `backend/app/domain/liquidity_pinning.py` — value observations pinned to their
  session (never factor-adjusted; anachronism refusals), volume comparability through
  the EXISTING corporate-actions arithmetic with explicit `price_date`/`query_date`
  and publish-time gates recorded in the factor chain, mixed-basis refusal.
- `backend/app/domain/fundamental_line_pit.py` — per-fundamental-LINE point-in-time
  resolution: cutoff-explicit, restatement chains (history kept, never deleted),
  `CONFLICTING_SOURCES` surfaced (never silently resolved), `NOT_AVAILABLE` honesty,
  `PUBLICATION_UNKNOWN` vs `NOT_YET_PUBLIC` precedence.

### Release engineering
- `.env.production.example` — production posture template, placeholders only, gates
  documented; the app refuses insecure placeholder values at startup (fail-closed).
- `windows-installer.yml` gains the `pull_request` trigger (parity) and all three
  workflows gain `release/**` in their push filters so every RC SHA gets all four
  required checks.
- Persian install guide + operator guide + these release notes in `docs/active/`.

## 2. Provenance honesty

- The 8 composed filters and their expressions come from the RECOVERED research
  documentation (verified bit-for-bit from `TABLOKHANI_WORKSTREAM_PACKAGE_2026-11-14.zip`).
  The lost implementation commits (`97da840`, `4ce812e`) remain UNRECOVERED; nothing
  was reconstructed from memory. Every deviation (0.6 inclusive threshold, 30d window,
  evaluated-universe market mean) is recorded in the filter rationale.
- No parity/superiority claim versus tablokhani.com is made anywhere.

## 3. Known limitations (disclosed, not hidden)

- Windows installer is UNSIGNED (no certificate exists; SmartScreen will warn).
  Desktop installation tests on a target machine are owner-gated and were NOT performed.
- Docker image build is executed by CI (`build-docker`) on the exact SHA; the
  development sandbox has no Docker daemon, so the local image build evidence is the
  public CI run + its logs, not a local run.
- Runtime data posture: with `DATA_SOURCE=mock` every payload is
  `mock/synthetic/live_verified=false`. No LIVE label can be minted by configuration.
- Pull request for the RC branch requires an authorized GitHub API token (none exists
  in the engineering environment; none was fabricated). GitHub's suggested PR URL is
  recorded in the publication evidence.
- Comparison to the Tablokhani reference requires owner-observed reference data under
  protocol P1–P6; not measured.
