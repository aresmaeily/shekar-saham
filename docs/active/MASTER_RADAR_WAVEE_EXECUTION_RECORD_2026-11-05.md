# MASTER-RADAR WAVE-E EXECUTION RECORD — DECLARED Session/Calendar Model (MR-B1-01 residual)

Date: 2026-11-05 · Baseline SHA: `32363ddaffa0f46456cdeb541cde35dd07950fdb` (origin/main after WAVE-D records; re-fetched) ·
Requirement: MR-B1-01 residual — "declared-calendar model with honest DECLARED trust class; sourced holiday tables stay owner-gated (R-3/R-7)" · Directive §11 WAVE-E.

---

## 1. Reconciliation with the existing P1 machinery (zero overwrite)

- `backend/app/domain/market_calendar.py` (WS-1/P1): the versioned holiday-TABLE contract (`MarketHolidayTable` / `is_trading_day` / fail-closed `TRADING_DAY_UNCLASSIFIED`) — **untouched** (`git status` clean on the file; its 14-test suite `tests/test_market_calendar.py` unchanged and green).
- `backend/app/domain/market_session.py` (P3.25): Iran session inference — untouched.
- The residual gap was that the P1 contract defines HOW a declared table is represented but NO actual declared calendars existed. WAVE-E adds exactly that declaration layer as a NEW module.

## 2. What was implemented

| Item | File(s) | Status |
|---|---|---|
| Declared calendar layer: 3 versioned calendars (Iran equities Sat..Wed 08:30–12:30 Asia/Tehran; Forex 24/5 UTC; US indices Mon..Fri 09:30–16:00 America/New_York) with fixed-date holiday rules, `DECLARED` trust marker, honesty envelope (owner-gate note, disclosed scope gaps, no-wall-clock note) | `backend/app/domain/declared_calendars.py` (NEW) | IMPLEMENTED |
| P1 bridge: `as_holiday_table(cal, year)` materializes declared fixed-date rules into a validated `MarketHolidayTable` (deterministic, fixed declaration instant, duplicate-date contract honored) so the existing `is_trading_day` machinery consumes them | same module | IMPLEMENTED |
| API: `GET /dataquality/calendars`, `/calendars/{id}`, `/calendars/{id}/session-state?as_of_utc=…` (REQUIRED caller instant — the server never reads a wall clock for calendar decisions; malformed → 422 with an encoding hint; unknown id → 404) | `backend/app/api/data_quality_api.py` (additive) | IMPLEMENTED |
| Frontend: declared-calendars panel in the Data Quality Center (3 calendars rendered from server fields only) + explicit-instant session-state checker (fail-closed refusal without both inputs) | `frontend/js/modules/render/data_quality_center.js`, `frontend/index.html` | IMPLEMENTED |
| Pre-publication integration fix (pre-existing WAVE-2 defect): `setEmptyRow`/`rowListOf` were CALLED by the committed data-quality module but never DEFINED — the no-market/empty-rows/error paths of the coverage+audit renderers could never run, and everything after them in `dqLoadAll` (including the new calendar panel) was blocked. Minimal intended-semantics helpers added once, defined before first use. | same module | FIXED + RECORDED |
| Service worker: v3-0-12 → v3-0-13; **install fetches now use `cache: "reload"`** (robustness fix: the browser HTTP cache's heuristic freshness — StaticFiles sends `max-age=3600` — could serve a stale module into the SW cache during install) + recorded counter-pin bumps (pins only, 6 files) | `frontend/sw.js` + pin tests | FIXED + RECORDED |

## 3. Honesty contract (pinned in the module docstring)

1. `trust_class: "DECLARED"` is a CALENDAR-level marker (the series-level `TrustClass` enum keeps its exhaustive 7 values — pinned by test).
2. DECLARED means: repository declaration, version-stamped (`2026-11-05.v1`), deterministic — NOT a sourced authoritative table; it never claims sourced status.
3. Sourced holiday tables stay owner-gated (R-3/R-7 Two-Key Rule) — disclosed in every payload.
4. Declared scope = fixed-date holiday rules + weekday session windows ONLY; weekend-adjacency moves, substitution days, ad-hoc closures, intraday halts, auction phases NOT modeled — disclosed in every payload. The Iran Nowruz window is an APPROXIMATE range declared to end Mar 31 so the Apr 1 rule stays unambiguous (the P1 duplicate-date contract refuses overlapping declarations — found and fixed during the wave).
5. No network, no file IO, no wall clock anywhere in the module; the API requires the caller's `as_of_utc`.

## 4. Verification evidence

### 4.1 Tests (+40, `backend/tests/test_declared_calendars.py`)

- Determinism (pure function, byte-identical payloads modulo the canonical wall-clock `checked_at` envelope — same convention as the strategylab exports), honesty envelope on every payload, fail-closed refusals (unknown calendar / naive instant / malformed instant / missing `as_of_utc`), per-calendar session logic incl. DST (US EDT), holiday-over-weekend precedence (disclosed, not moved), Forex Sunday-evening open vs Sunday-afternoon CLOSED semantics, Nowruz range ending Mar 31 + unambiguous Apr 1 rule, `TrustClass` enum untouched, routes scoped under the governed prefix, P1 bridge (deterministic materialization, range expansion, `is_trading_day` HOLIDAY/TRADING_DAY verdicts, UNCLASSIFIED fail-closed preserved, P1 surface intact).

### 4.2 Full battery

**2808 passed / 1 skipped / 0 failed** = 2768 (WAVE-D) + 40 (this wave) EXACT; the P1 14-test suite unchanged and green inside the battery; pyflakes clean; `node --check` green.

### 4.3 Runtime browser verification (real server + real browser, fresh session)

- Calendar table renders 3 declared calendars (id / market / timezone / declared windows / fixed-date rules / version / DECLARED class) from server fields only.
- Session-state checker golden paths: IR_EQ Saturday 10:00 Tehran → **OPEN** («declared window 08:30–12:30 REGULAR»); IR_EQ Monday 12:00 UTC (15:30 Tehran) → **CLOSED** (past the declared close); hostile `as_of` → fail-closed refusal message (nothing fabricated); zero fresh console errors after the fix.
- The audit table render (pre-existing broken branch) now works (USEQ:AAPL SYNTHETIC row) thanks to the missing-helper fix.
- Service-worker/cache verification: cache `radar-bourse-static-v3-0-13` present; the SW-cache-first + version-bump + cache:reload design confirmed live.

## 5. Session-level incident recorded honestly (reconciliation note)

During this wave the working-tree copy of `app/domain/market_calendar.py` was inadvertently overwritten by the new WAVE-E module (name collision — the P1 module's existence was not re-checked before writing). The overwrite was caught during battery reconciliation (test-count arithmetic mismatch), the committed P1 module and its 14-test suite were restored verbatim from git (forward-only; nothing rewritten), and the WAVE-E layer was re-homed as `declared_calendars.py` with an explicit bridge instead of a replacement. No gate, no committed file content, and no test was changed by the incident; the final tree is clean on both P1 files.

## 6. Gates and status

Gates unchanged: AI2_ENABLED=0 · verified=False · SYNTHETIC_OR_PAPER · no scheduler/egress/live path · R-1..R-11 intact · INSTALL NOT ISSUED. MR-B1-01 residual → **INTEGRATION-VERIFIED** (declared layer; sourced tables remain owner-gated). Global completion **NOT CALCULATED**.

## 7. Remaining after WAVE-E (WAVE-A gap list)

WAVE-F (five product loops audit vs §5) · WAVE-G (repo-side Windows packaging readiness) · WAVE-H (17-role audit + owner acceptance package) · plus WAVE-D/WAVE-C CI exact-SHA evidence currency (GitHub API rate-limit window; to be appended per WS1 §13/§14 when queryable).
