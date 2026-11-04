# AUDIT-MR4 — Independent Read-Only Audit of MASTER-RADAR WAVE-B (2026-11-04)

Auditor posture: independent, read-only, pre-publication, conducted in a **fresh clone** of the
WAVE-B working tree (`masterwaveb_scratch/audit/clone`), at implementation commit
`733ba96550f71aea04ff6595613cbf0b0e4bab90` (working tree byte-identical to that commit).
Evidence commands were re-executed from scratch; nothing was trusted from the implementer's
records without reproduction.

## Verdict: 7/7 checks PASS — 0 FAILs — 4 observations (all LOW/INFO, accepted with rationale)

| # | Check | Method (independent re-execution) | Result |
|---|---|---|---|
| 1 | Battery reproduction | full `pytest tests/ -q` ×2 in the fresh clone | 2739 passed / 2 skipped / 0 failed **both runs**; count math exact: 2624 baseline + 60 (DSL) + 29 (API) + 26 (static/integration) = 2739 |
| 2 | Hostile robustness | 43 probes against a REAL `uvicorn` server (`DATA_SOURCE=mock`, port 8123): oversized/nested/unicode/quote-smuggled DSL sources, prototype-pollution & oversize imports, NaN/Inf/list/bool/negative/float/2.5-period params, bad timeframes, compute-after-uninstall | **zero 5xx** — 33×422 (typed DSL/param errors), 2×409, 1×404, 7×200 |
| 3 | No-look-ahead (live) | prefix comparison on the running server: compute(N=200,end=900) vs N∈{50,100,150} slices for `sma(close,10)` | byte-agreement within 1e-9 on the shared range for every k |
| 4 | Runtime refactor equivalence | A/B: HEAD `runtime.py` (loaded from `git show HEAD:…`) vs working-tree runtime; 5 RSL-1 programs (incl. MTF + sym() + risk + crossover + ref-INPUT) × 6 deterministic contexts, plain AND MTF paths, decisions AND error pairs | **2415 decisions + 18 matching error-path pairs — 0 mismatches** |
| 5 | Test integrity | `git diff` over the five modified test files | counter-pin bumps ONLY (v3-0-8→v3-0-9); no assertion weakened, no test deleted/skipped; `test_security_hardening` and all other pre-existing files untouched |
| 6 | Security / secrets / gates | secret-scan regex battery over every changed/new file (keys, private-key blocks, token shapes); `git diff --stat` over `config.py`/`market_service.py`/`runtime_settings.py`; manual read of the new modules for egress primitives | secret scan: **NONE**; gates diff: **0 bytes** (`AI2_ENABLED=0` config.py:111, `verified=False` posture, SYNTHETIC_OR_PAPER); new API module contains no `httpx/requests/urllib/socket/subprocess/BackgroundTasks/asyncio.create_task` |
| 7 | Frontend static gates | repo validator `scripts/validate_frontend_static.py` (ok + 29/29 tabs + duplicate-id census), `node --check` on the three touched JS files, manual boundary review of the two new modules | validator `ok:true`; tabs 29/29; dup census clean; **api.js-only HTTP**, no `eval(/new Function(/import(/document.write`, no client-side fallback engine, `esc()` on every interpolated server field, no timers (single best-effort `setTimeout` = object-URL revocation in the export path) |

## Fixtures recomputed by the auditor (hand arithmetic, not re-running the module)

- `sma(close,3)` over the pinned 12-bar fixture: bar 2 = (10+10.5+11)/3 = 10.5; bar 11 =
  (13.6+14.2+15)/3 = 14.2̄6 — matches engine output exactly.
- `rsi(close,5)` boundary at index 5: gains (0.5+0.5+0+0.6+0.6)=2.2 → avg 0.44; losses 0.2 →
  avg 0.04; RS=11 → RSI = 100 − 100/12 = 91.6̄6 — matches.
- Warm-up boundaries: `sma/ema/stdev` first valid at `p−1`, `rsi/atr` seeded at `p`,
  `ref(x,k)` at `k` — the engine's `structural_warmup` and the runtime zero/partial-window
  regions agree in all 11 parametrized cases (auditor re-ran the coherence suite and spot-
  checked `sma(close,3)*2 − ref(close,1)` → warm-up 2 with the documented zero-DERIVED (not
  zero) region, honestly pinned as `zero_fill=False`).

## Observations (all accepted; none block publication)

- **O1 (INFO):** the legacy demo modules `frontend/js/modules/custom_indicator.js` +
  `render/custom_indicator_ui.js` (regex "interpreter" with a dishonest silent SMA-20
  fallback) remain in-tree but are **unmounted dead code** (no importer; verified by grep).
  The governed UIDL-1 panel is the only mounted user-indicator path. Disposition: accepted;
  physical removal assigned to a future hygiene wave to keep the WAVE-B commit boundary clean.
- **O2 (INFO):** the UIDL store is in-memory (server restart clears it); export/import is the
  documented persistence contract — identical to the audited `indicator_manager`. Accepted.
- **O3 (LOW):** popup detach v1 syncs symbol/timeframe only; crosshair/visible-range are NOT
  synced across detached windows and no OS window-placement is claimed — stated in the module
  header, in the detached-window note, and in the execution record. Accepted (honest scope).
- **O4 (INFO):** for `highest/lowest` the warm-up region carries the runtime's documented
  PARTIAL-window values (not zeros); the engine labels warm-up as "first fully-determined
  bar" and the tests pin the distinction explicitly. Accepted.

## Boundary notes

- Governance artifacts untracked in the working tree (`.claude/`, `CLAUDE.md`) were excluded
  from the commit boundary (same disposition as WAVE-3).
- Rate-limit hygiene: WAVE-B test identity `mr-waveb-uidl:12349` — census against the
  recorded identities 12345–12348 shows no collision.
- The `get_settings` lru_cache residue class (AUDIT-MR3 Obs.3) resurfaced via
  `test_security_hardening` poisoning later modules; the durable per-test autouse hygiene in
  `test_user_indicator_api.py` fixes it for this module without touching the poisoner
  (recorded as an integration finding, fixed pre-publication).
