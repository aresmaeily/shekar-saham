# WS-10 — CHART-PRO WINDOWS APPLICATION DIRECTIVE (Faraz-Chart / TradingView class) — 2026-11-02

Persian executive summary (خلاصه فارسی): این سند دستور اجرایی موج WS-10 است — افزودن
«چارت حرفه‌ای» در اپلیکیشن ویندوز (Electron) در کلاس فرازچارت/TradingView، بر پایه
بررسی عمیق محصولات مرجع و وضعیت موجود مخزن، همراه با تصمیمات تفویض‌شده مالک
(`OWNER_DECISIONS_RECORDED_2026-11-02.md`). همه داده‌ها برچسب صادقانه
`SYNTHETIC_OR_PAPER` می‌گیرند؛ هیچ Provider زنده‌ای فعال نمی‌شود (R-3=KEEP-DENIED).

## 1. Authorization reference (roadmap-lock compliance)

`PRODUCT_ROADMAP_LOCK.md` forbids feature drift before Alpha gates close **or an
explicit recorded authorization exists**. This directive IS that recorded
authorization: the owner's chat directive of 2026-11-02 explicitly (a) named the
missing item — "اپلیکیشن ویندوز نظیر فراز چارت و تریدینگ ویو" — (b) ordered a deep
review of the related material, and (c) delegated the owner-gate decisions to the
executable-now best option set, instructing that **all remaining work be issued to
the programmer and completed in this stage**. Working baseline: remote `main`
verified `f05be4ce16912757f2d56cdc7690b247ee255baa` at wave open (forward-only from
there; no amend/rebase/reset/force).

## 2. Deep review — reference products vs. current repository state

### 2.1 Reviewed reference material
- **Faraz Chart (فراز، faraz.io / faraz.io/features)** — Iranian TSE-class charting
  platform: simultaneous multi-chart layouts, live charts for domestic + global
  markets, specialized indicators, price alerts, watchlists, bar replay, bar/candle
  chart types, analysis save/load/copy (reviewed 2026-11-02).
- **TradingView** — candlestick/line/area chart types, 100+ indicator library,
  drawing tools (trendlines, Fibonacci, horizontal levels), price alerts on
  indicators/price, watchlists, screener, multi-chart layouts, saveable templates.
- **Repository state at `f05be4c`** (verified): TradingView **Lightweight Charts
  v4.2.0 vendored** (`frontend/vendor/lightweight-charts.standalone.production.js`),
  `ExcellentChart` (`frontend/js/modules/render/tradingview_excellent.js`) with
  MA/EMA/RSI/volume + markers + risk price-lines, forex tab with
  `ReplayController` + `IndicatorPane`, volume-profile canvas overlay,
  support/resistance swings, custom indicator module, `/api/v08/chart` and
  `/api/v09/forex` endpoints, symbol page chart, Electron shell (main.js menu →
  hash routes), full Persian RTL UI. **Missing vs. the reference class:** drawing
  tools, Fibonacci, per-symbol analysis persistence, chart price alerts, watchlist
  panel beside the chart, MACD/Bollinger on the chart, deterministic seeded demo
  candles (both existing synthetic generators are time-bucket-seeded or unseeded),
  and a dedicated pro-chart surface on the Windows (Electron) app.

### 2.2 Gap → work-package matrix (WS-10 = CH-1..CH-8)

| ID | Work package | Faraz/TV reference capability | Acceptance criterion |
|---|---|---|---|
| CH-1 | Deterministic seeded candle generator (`backend/app/data/seeded_candles.py`) | reproducible demo/history data | same `(symbol, timeframe, end_bar_index)` → byte-identical OHLCV, twice, any process; bar N never mutates later |
| CH-2 | `/api/v10/chartpro/*` API (candles + indicators + universe) | chart data API | pytest suite; `data_trust` returned from `market_service.data_trust_context()` and asserted never "live"; limit clamp 50..1000 |
| CH-3 | chartpro tab on the dashboard + Electron menu item | professional chart surface | tab↔panel pins, static validator green, menu hash target exists, RTL Persian labels |
| CH-4 | Indicators UI: MA20/MA50/EMA20/RSI14/MACD/Bollinger | specialized indicators | toggles render/hide series; MACD via second pane (`indicator_pane.js` precedent) |
| CH-5 | Drawing tools: trendline, horizontal line, Fibonacci retracement | TV-class drawing tools | overlay canvas; per-symbol localStorage persistence; delete/clear; survives reload |
| CH-6 | Chart price alerts (local) | price alerts | `createPriceLine`; cross → in-product toast/inbox only (R-9: no external channel) |
| CH-7 | Watchlist panel beside chart | watchlist | universe from CH-2, click-to-load symbol, last price + change |
| CH-8 | Analysis save/load/export (JSON) | Faraz "save/load analysis" | named layouts in localStorage; export = download JSON; import restores drawings+indicators+alerts |

Non-goals for this wave (explicit): live data of any class (R-3), external alert
delivery (R-9), new npm dependencies (vendored lightweight-charts only), replay
extension (already shipped for forex), any change to the pinned two-cycle refresh
contract (F-7 record), any edit to archived docs.

## 3. Implementation constraints (binding for every CH package)

1. File ownership is bounded and non-overlapping (see execution record); frontend
   module must use `core/api.js`'s `api()` — raw `fetch` outside that module is
   forbidden by its contract.
2. Honest trust vocabulary: every v10 response carries `trust_level` +
   `data_trust` from the market service; UI shows a visible source badge
   (`SYNTHETIC_OR_PAPER` semantics); nothing may render synthetic data as live.
3. Existing pins stay intact: `test_gov24_desktop_shell.py` (Electron shell),
   `test_frontend_static_script.py` (static validator), version sync, menu hash
   targets, unique IDs, no `v0.x` literals, no legacy links.
4. Gates per change: `node --check` on new/changed JS; `python
   scripts/validate_frontend_static.py`; `PYTHONPATH=. pytest -q tests`;
   `python -m pyflakes app`; YAML untouched; PowerShell scripts untouched.
5. Forward-only commits through the authorized deploy-key path (R-10 standing
   grant recorded this date), remote read-back + exact-SHA CI verification.

## 4. Execution record

Executed 2026-11-02 in the same cycle: see `docs/CHANGELOG.md` top entry and
`OWNER_DECISIONS_RECORDED_2026-11-02.md` for the decision set that conditions this
wave. Battery arithmetic and commit SHAs are recorded in `docs/STATUS.md`.
