# MASTER-RADAR WAVE-D EXECUTION RECORD — PDF Report Export (MR-D5-01 residual)

Date: 2026-11-05 · Baseline SHA: `7a8552837ab64c22b94b98479c9d8de4fb510881` (origin/main after WAVE-C; re-fetched) ·
Requirement: MR-D5-01 residual — "PDF export of backtest/optimization/walk-forward reports (CSV/JSON already delivered)" · Directive §11 WAVE-D.

---

## 1. What was implemented

| Item | File(s) | Status |
|---|---|---|
| Deterministic PDF writer (zero new dependencies) | `backend/app/services/report_pdf.py` (NEW) | IMPLEMENTED |
| `/strategylab/backtest/export` gains `format=pdf` | `backend/app/api/strategy_lab.py` | IMPLEMENTED |
| `POST /strategylab/optimize/export` (json/csv/pdf) | `backend/app/api/strategy_lab.py` (NEW endpoint) | IMPLEMENTED |
| `POST /strategylab/walkforward/export` (json/csv/pdf) | `backend/app/api/strategy_lab.py` (NEW endpoint) | IMPLEMENTED |
| `POST /optimize` and `POST /walkforward` refactored to delegate to shared `_optimize_payload` / `_walkforward_payload` (verbatim move — export re-uses the SAME deterministic run path and digest) | `backend/app/api/strategy_lab.py` | IMPLEMENTED |
| Frontend: `apiBlob()` binary-attachment client (single-HTTP-module rule kept) | `frontend/js/core/api.js` | IMPLEMENTED |
| Frontend: PDF export button (Backtest Center) + optimizer PDF/CSV/JSON export buttons wired to `/optimize/export`; binary Blob download helper | `frontend/js/modules/render/backtest_center.js`, `frontend/index.html` | IMPLEMENTED |
| Service-worker cache bump v3-0-10 → **v3-0-11** (+2 changed files already in precache) | `frontend/sw.js` | IMPLEMENTED |
| Counter-pin updates (pins only, recorded) | 6 test files (frontend static / wave2 / wave3 / waveb / p3_80 / wda-consistency) | RECORDED |

## 2. PDF writer design contract (pinned in the module docstring)

1. **Byte-determinism**: identical sections → byte-identical PDF. Fixed Info dates (`D:20000101000000Z`), no file `/ID`, no wall clock, uncompressed streams. Verified by dedicated tests.
2. **Zero dependencies**: hand-rolled PDF 1.4 assembly (catalog/pages/info/page/content/font objects, exact xref offsets). No new requirements.txt entry; CI dependency set unchanged.
3. **Base-14 fonts only** → English-label projection (the CSV export's existing documented convention). Persian renders in the product UI; every PDF states this limitation explicitly.
4. **Honesty block on every report**: data-trust label, "SYNTHETIC SEEDED SERIES, NOT LIVE MARKET DATA", "the JSON export remains the full-fidelity report", engine notes/limitations echoed verbatim, never invented values, `None` → empty cell.
5. **Fail-closed sizing**: deterministic truncation by glyph count; `None`/bool/float-repr conventions identical to the CSV export.
6. **Trades cap**: 200 rows per PDF with an explicit omitted-rows text block (JSON export carries the full list).

## 3. Verification evidence

### 3.1 Static / unit / API tests — `backend/tests/test_report_pdf.py` (+27 tests)

- Byte-determinism (writer ×1 and API ×3 surfaces), fixed Info dates, xref-offset consistency (parse-and-verify every offset), %PDF-1.4/%%EOF structure.
- Greppable honest content: digest, `SYNTHETIC_OR_PAPER`, "NOT LIVE MARKET DATA", page numbering, metric keys, trade values.
- Hostile containment: PDF operator characters `( ) \` in payload values and titles — structure intact, byte-identity held, escaped form verified; non-WinAnsi glyphs → deterministic `?` fallback.
- Pagination consistency: `/Count` == Kids length == footer "Page i of N" on every page; 250-trade report → 5 pages; explicit cap note.
- API: all three export endpoints (pdf/csv/json), byte-identity across identical bodies, digest equality between `/optimize` and `/optimize/export` (same deterministic run path), hostile `format` → 422 (all three), csv/json regression unchanged, new routes scoped under the governed `/api/v10/strategylab/` prefix (openapi enumeration, version-stable form).
- Env-conditional third-party validation: poppler `pdftotext` roundtrip (present in this sandbox → PASSED; skips honestly in environments without poppler).

### 3.2 Full battery

`cd backend && python3 -m pytest tests -q -p no:cacheprovider` → **2768 passed / 1 skipped / 0 failed in 27.88s** = 2741 (WAVE-C baseline in this environment) + 27 (this wave) EXACT. The single skip is the recorded env-conditional G2 substantive-rejection self-skip. CI expectation: poppler test skips there (env-conditional, recorded).

### 3.3 Static / lint

- pyflakes CLEAN on `report_pdf.py`, `strategy_lab.py`, `test_report_pdf.py` (two dead-name findings found and fixed pre-publication).
- `node --check` GREEN on `api.js`, `backtest_center.js`, `sw.js`.
- Static frontend validator (tabs 29/29, panels, imports) — battery-green.

### 3.4 Runtime verification (real server + real browser, this session)

- Backend restarted with the WAVE-D code; service-worker cache verified `radar-bourse-static-v3-0-11` after a controlled unregister+clear (honest note: the first export attempt against the pre-restart server returned 422 `pattern '^(csv|json)$'` — the OLD module in the OLD process; root cause = stale process, not code; re-verified after restart).
- Golden path (browser): Backtest Center → run backtest (`result_digest ded96d75…` rendered from the server response) → click «خروجی PDF» → `POST /api/v10/strategylab/backtest/export` → **200** (binary attachment path via `apiBlob`).
- Optimizer golden path (browser): fill space `{grid:{fast:[3,5,8]}}` + seed 7 → run → click «خروجی PDF بهینه‌ساز» → `POST /api/v10/strategylab/optimize/export` → **200**.
- Zero console errors during the whole flow.
- PDF structural validation against a real third-party parser (poppler `pdftotext`): title, metrics, trust label and digest extracted successfully.

## 4. Honesty scope

- The PDF is a fixed-layout ENGLISH-label projection; Persian text renders in the UI, not in the PDF (base-14 fonts — stated on every PDF page and in the docs). The JSON export remains the full-fidelity report on all three surfaces.
- The PDF writer adds NO third-party dependency; requirements.txt unchanged; no CI dependency delta.
- Walk-forward export is API-first (the walk-forward surface has no dedicated tab; the export endpoint serves API consumers) — recorded honestly; optimizer export is wired in the Backtest Center UI.
- Gates unchanged: AI2_ENABLED=0 · verified=False · SYNTHETIC_OR_PAPER · no scheduler/egress/live path · R-1..R-11 intact · INSTALL NOT ISSUED. Global completion **NOT CALCULATED**.

## 5. Remaining after WAVE-D (from the WAVE-A gap list)

WAVE-E (declared session calendars with honest `DECLARED` trust class) · WAVE-F (five product loops audit) · WAVE-G (repo-side Windows packaging readiness) · WAVE-H (17-role audit + owner acceptance package).
