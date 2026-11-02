# TABLOKHANI CAPABILITY MATRIX — EVIDENCE-BASED, NO SUPERIORITY CLAIMS

- **Task:** T5 (CONSOL-NEXT Wave 1), WP-1 — authorized docs task per MA-1 record
  (`docs/active/MA1_CONSOLIDATED_EXECUTION_RECORD_2026-11-02.md` §7, lines 168–170:
  "the matrix doc is the next authorized docs task and requires no owner decision").
- **Baseline SHA:** `84f9b1b75dd2c90d9c6c98d2c808f2d93df44ec6` (branch `main`, tracked tree clean at authoring time).
- **Date:** 2026-11-02.
- **Author:** T5 TabloKhani Evidence Specialist (read-only pass; this file is the ONLY repo file created).

## 1. Purpose

Map RADAR BOURSE's implemented capabilities against the TabloKhani reference
methodology **using only verifiable in-repo evidence**, so that the owner and future
cycles can see exactly what is claimed, what is implemented, and — critically — what is
NOT compared. This matrix makes **no superiority claim of any kind** (see §2).

Primary in-repo sources describing the TabloKhani reference methodology:

- `docs/archive/phase-reports/summary-of-tablokhani-videos.md` — summary of 6 reference
  videos (rant stocks, industry leader, big-player moves, hot money, hot-money signals,
  market game) + an annotated screenshot of `tablokhani.com/stock-watchlist` (lines 113–150).
- `docs/archive/phase-reports/CHANGELOG_V13_IDEAS_TABLOKHANI.md` — which TabloKhani-derived
  ideas were actually implemented (items 1–6) and where.
- Governance boundary: `docs/governance/amendment_sources_2026-10-02/03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md:111`
  ("TabloKhani is an initial market-board interpretation benchmark only … Claims that the
  product exceeds reference sites require versioned benchmark evidence, not model assertion
  or marketing language."), and
  `docs/governance/amendment_sources_2026-10-02/02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md:188–189`,
  `05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md:167,170` (decision D-AI-34),
  `06_PRODUCT_CAPABILITY_CHARTER_CONTINUOUS_INTELLIGENCE_2026-10-02.md:49`,
  `00_OWNER_ROADMAP_DECISION_CURRENT_2026-10-02.md:107`,
  `02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE_CURRENT_2026-10-02.md:110`.

Terminology note: in-repo Persian "تابلوخوانی" is used BOTH as the generic methodology
term ("board reading") and as the reference-site name (tablokhani.com). This matrix treats
the two archive documents above as the authoritative description of the REFERENCE; generic
uses of the word are listed in §4 (non-claim inventory), not as claims.

## 2. Evidence rules (absolute)

1. **Every matrix cell cites in-repo evidence**: `file:line` and/or test ids
   (`test_file.py::test_name`). Citations were re-verified at baseline
   `84f9b1b` (grep transcripts in `/home/z/my-project/consolnext_scratch/T5/`).
2. Anything **without verifiable in-repo evidence is explicitly marked**
   `UNKNOWN(reason)`, `NO_EVIDENCE`, or `NOT_DESCRIBED_IN_SOURCES` — never guessed.
3. **No superiority claims anywhere.** A comparative verdict (e.g. "better than",
   "at parity with", "exceeds") **REQUIRES a measured, repeatable comparison between
   RADAR BOURSE and the TabloKhani reference**. After a full-repo evidence sweep
   (`grep -rni "tablokhani|tablo khani|تابلوخوانی|تابلو خانی"` → 53 transcript lines,
   scratch `grep_tablokhani_full.txt`), **NO such measured comparison exists anywhere
   in the repo**. Therefore every comparative verdict below defaults honestly to
   `NOT_COMPARED_WITH_EVIDENCE`. Per the owner-governance evidence rule (03:111),
   such a claim may only be made after a versioned Golden Set + repeatable benchmark
   show measurable improvement — the Golden Set exists (row 14) but contains **only
   RADAR-BOURSE-internal regression cases** (`backend/tests/fixtures/golden_set/golden_set_v1.json`),
   **zero TabloKhani reference measurements**, so it cannot ground any comparison.
4. Verdict vocabulary (exactly one per row):
   - `AT_PARITY_EVIDENCE_BASED` — a measured, repeatable in-repo comparison exists and shows parity. **Never used in this matrix.**
   - `NOT_COMPARED_WITH_EVIDENCE` — both the RADAR implementation evidence and a TabloKhani reference basis are documented, but the repo contains NO measured head-to-head comparison. (Honest default.)
   - `NO_EVIDENCE` — no implementation evidence in-repo (or no usable reference basis), so no comparison is even constructible.
   - `UNKNOWN(reason)` — evidence exists but is ambiguous or stale; reason stated.
5. Test citations were executed at baseline where noted (§6); file:line citations were
   grep-verified. If a cited V13-era frontend path is stale, the row says so and cites
   the current tree instead (this was checked: `frontend/js/app.js` no longer exists;
   `ls frontend/js/` shows `main.js, core/, components/, modules/, tabs/`).

## 3. Capability matrix

Legend: **RADAR** = RADAR BOURSE implementation evidence; **REF** = what the in-repo
TabloKhani source materials ACTUALLY document; verdict per §2.4.

| # | Capability | RADAR implementation evidence (file:line + test ids) | TabloKhani reference basis (in-repo sources) | Comparison verdict |
|---|---|---|---|---|
| 1 | Market data ingestion (TSETMC) | `backend/app/data/providers.py:1` (docstring "TSETMC / BrsApi با fallback به mock"), `:128` `tsetmc_mw_to_snapshot`, `:232` `MarketDataProvider`, `:250` `fetch`, `:392–395` `_from_tsetmc` → `cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch`, `:445/:467` parsers, `:208` CircuitBreaker, `:507/:520` cache; `backend/app/core/config.py:33–39` (`DATA_SOURCE=mock\|tsetmc\|brsapi\|auto`, `TSETMC_BASE`). Tests: `test_p3_90_7_tsetmc_cdn_schema.py::test_cdn_schema_without_l18_is_accepted` (:51), `::test_legacy_l18_schema_still_works` (:71), `::test_parse_tsetmc_json_accepts_cdn_marketwatch` (:82); `test_p3_91_cdn_snapshot_filter.py::test_cdn_snapshots_are_filterable_without_verified_live` (:28); `test_data_domain.py::test_data_trust_context_never_marks_mock_live` (:25) | Archive docs describe TSETMC only implicitly (watchlist screenshot refresh + board columns, `summary-of-tablokhani-videos.md:119–129`). Data-ingestion mechanism of the reference site: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 2 | Symbol universe / screening | `backend/app/engines/screener.py:24` `analyze_market`, `:336` `_to_card`, `:359` `_is_noise_symbol`; board refresh wiring `backend/app/services/market_service.py:416` (`rank_tablocastic(..., limit=100)` in `refresh()`), `:484` (`_last_tablocastic`); frontend board `frontend/js/modules/render/watchlist_excellent.js:42` `renderWatchlistExcellent`. Tests: **no dedicated screener unit test**; exercised indirectly via `test_refresh_false_fresh.py` ×3 (service refresh path) and `test_market_intelligence_service.py:30` (Row contract) | Reference universe = full board table with industry filter, column picker (11 columns), per-column numeric filters, search (`summary-of-tablokhani-videos.md:122–131`). Ranking/scoring logic of reference: **NOT_DESCRIBED_IN_SOURCES** (beyond the video-derived filters) | NOT_COMPARED_WITH_EVIDENCE |
| 3 | Technical indicators | `backend/app/engines/indicators.py:39` `macd`, `:60` `bollinger`, `:80` `stochastic`, `:119` `atr`, `:144` `adx`, `:197` `cci`, `:216` `obv`, `:234` `williams`, `:252` `vwap`; `backend/app/engines/metrics.py:20` `compute_metrics`. Tests: `test_indicators.py::test_macd_shape` (:29), `::test_bollinger_order` (:41), `::test_stochastic_range` (:49), `::test_williams_range` (:57), `::test_atr_positive` (:65), `::test_adx_range` (:73), `::test_obv_cumulative` (:81), `::test_cci_finite` (:89), `::test_vwap_between_low_high` (:97); `test_metrics.py::test_compute_metrics_finite` (:4) | Archive videos teach board-field logic (buy power, per-capita, volume ratio — `summary-of-tablokhani-videos.md:17,22–27,76–79`), not MACD/ATR/ADX-class chart indicators. Chart-indicator set of reference: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 4 | Volume profile | `frontend/js/modules/volume_profile.js:1–11` (header: bins, POC, VAH/VAL, visible/full range), `frontend/js/modules/forex.js:138–149` `renderVolumeProfileInfo`, `:181–182` toggle; `backend/app/data/forex_provider.py:2` ("Volume Profile ready"); README.md:23 (Phase 6 list). Tests: **none dedicated** — `test_forex.py` covers brokers/symbols only (`::test_gold_has_three_brokers` :15 … `::test_symbols_list_contains_all_new_symbols` :61) | **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 5 | Chart / visualization | Backend: `backend/app/engines/chart_builder.py:11` `build_ohlcv_from_ticks`, `:56` daily OHLCV, `:85/:96` MA/EMA, `:112` RSI, `:148` `generate_markers_from_signals`. Frontend: `frontend/js/modules/render/tradingview_excellent.js` (TradingView embed), `frontend/js/modules/utils/chart_theme.js:3` ("چارت‌های lightweight-charts … مثل تابلوخوانی"), `frontend/js/modules/support_resistance.js:1–8` (swing S/R lines). Tests: no chart unit tests; page-level e2e only (`e2e/test_smoke.py::test_symbol_page_serves` :62, `::test_main_dashboard_has_no_uncaught_errors` :68) | Reference visualization described only as the watchlist screenshot table (`summary-of-tablokhani-videos.md:113–150`) + "more charts links" note (`frontend/js/symbol.js:453`). Charting capability of reference: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 6 | Filter DSL / strategy framework | `backend/app/engines/filter_dsl.py:143–441`: `FilterError` :143, `normalize_expr` :179, `parse_filter` :263, `validate_filter` :278, indicator refs `_indicator_value` :290, sandboxed eval `_SafeEval` :319, `eval_filter` :408, `run_filter` :418, `fields_help` :430, `functions_help` :434, `expression_tree` :438; tablocastic fields in row context `:75`; strategy registry `test_strategy_framework.py::test_strategy_registry_contract` :52. Tests (17): `test_filter_dsl.py::test_valid_filter` :14 … `::test_functions_help_lists_indicator_references` :108 (incl. security refusals :69–83); `test_strategy_framework.py::test_filter_strategy_validate_contract` :13, `::test_filter_strategy_rejects_unsafe_filter` :46. Docs: `docs/architecture/FILTER_DSL_STRATEGY_FRAMEWORK.md:30`; `docs/active/P3.26_FILTER_DSL_STRATEGY_FRAMEWORK_REPORT.md:55` | Archive videos present FIXED pseudocode filters (e.g. `summary-of-tablokhani-videos.md:22–27, 39–44, 89–91`), not a user-facing expression DSL. Whether the reference exposes a DSL: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 7 | Backtest engine | `backend/app/engines/backtest.py:329` `run_filter_strategy_backtest`, `:494` `run_backtest`, `:70` `ExecutionConfig`, `:134` `resolve_same_bar_tp_sl` (no-lookahead fill rules), `:277` `_metrics_from_trades`. Tests (14): `test_backtest_framework.py::test_backtest_entry_executes_next_bar_no_lookahead` :26, `::test_backtest_commission_and_slippage_reduce_pnl` :40, `::test_close_only_tp_uses_close_not_intrabar_guess` :113, `::test_ohlc_sl_only_fills_at_sl_level` :201, `::test_data_trust_is_preserved_in_backtest_report` :106; Golden Set BACKTEST case `test_golden_set.py::test_backtest_golden_case_exact_recompute_and_double_run_determinism` :125 | **NOT_DESCRIBED_IN_SOURCES** (no reference backtest capability appears in either archive doc) | NOT_COMPARED_WITH_EVIDENCE |
| 8 | Walk-forward optimization | `backend/app/engines/backtest.py:529` `run_walk_forward`, `:81` `WalkForwardConfig`. Tests: `test_backtest_framework.py::test_walk_forward_uses_out_of_sample_windows` :74, and **`::test_walk_forward_is_not_an_optimizer`** :222 (the engine deliberately implements out-of-sample WINDOWED EVALUATION, not parameter optimization); Golden Set WFO case `test_golden_set.py::test_walk_forward_golden_case_exact_recompute_per_window` :151 (per-window exact equality) | **NOT_DESCRIBED_IN_SOURCES**. Also definitional caution: RADAR implements WFO-style evaluation whose own test forbids "optimizer" semantics; calling it "optimization" would overstate. Verdict could also read `UNKNOWN(definitional)`; NOT_COMPARED_WITH_EVIDENCE is the conservative reading | NOT_COMPARED_WITH_EVIDENCE |
| 9 | Forward test | `backend/app/engines/backtest.py:581` `run_forward_test` (explicit `start_ts` boundary). Tests: `test_backtest_framework.py::test_forward_test_uses_later_boundary` :88; Golden Set FORWARD_TEST case `test_golden_set.py::test_forward_test_golden_case_exact_recompute` :197 (asserts `forward_boundary.start_ts == 28.0`, mode `forward_test`) | **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 10 | Multi-testing controls | `backend/app/domain/evaluation_statistics.py:85` `bonferroni_adjust`, `:98` `benjamin_hochberg_adjust` (exact arithmetic), `:136` `EvaluationFamily`, `:178` `adjusted_acceptance` (refuses unadjusted for family>1, NONE-method honesty flag), `:320` `confusion_counts`, `:348` `precision_recall_fp_rate`. Tests: `test_evaluation_statistics.py::test_bonferroni_hand_computed` :32, `::test_benjamin_hochberg_hand_computed` :63, `::test_adjusted_acceptance_refuses_unadjusted_for_family_over_one` :149, `::test_precision_recall_fp_rate_never_fakes_zero_for_undefined` :244 | **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 11 | Holdout isolation | `backend/app/engines/holdout.py:95` `split_holdout` (timestamp-boundary split, frac∈(0,0.5) enforced), `:166` `HoldoutAttestation` (isolated:True only via passing path), `:186` `assert_no_selection_on_holdout`, `:42` `HoldoutViolation`. Tests (17): `test_holdout.py::test_split_holdout_boundary_is_timestamp_frontier` :44, `::test_attestation_happy_path_isolated_true` :126, `::test_attestation_refuses_selection_touching_the_boundary` :143, `::test_attestation_record_is_frozen` :221 | **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 12 | Regime slices | `backend/app/engines/regime_slices.py:190` `slice_by_regime` (closed label set, overlap refusal, deterministic aggregate), `:64` `RegimeSliceViolation`, `:105` `RegimeSlicesReport`. Tests: `test_regime_slices.py::test_slice_two_windows_basic_membership` :27, `::test_overlapping_windows_refused` :82, `::test_nondeterministic_aggregate_refused` :146, `::test_records_are_frozen` :190 | **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 13 | Survivorship guard | `backend/app/domain/survivorship_guard.py:136` `survivorship_check` (closed verdicts OK / SURVIVORSHIP_BIAS_RISK / ANACHRONISTIC_MEMBER / INCOMPLETE_UNIVERSE), `:65–105` models. Tests: `test_survivorship_guard.py::test_ok_when_complete_and_delisted_member_is_included` :46, `::test_survivorship_bias_risk_when_delisted_member_excluded` :57, `::test_verdict_precedence_bias_over_anachronistic_over_incomplete` :117, `::test_conflicting_member_record_refuses_fail_closed` :153 | **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 14 | Versioned Golden Set | `backend/app/domain/golden_set.py:53` (kinds BACKTEST/WALK_FORWARD/FORWARD_TEST), `:156` `version_id` pattern `GS-YYYY-MM-DD`, `:66` `canonical_json`, `:80` `digest_of` (SHA-256), `:210` `verify_case` (EXACT `==`, no tolerance), `:232` `parse_golden_set_version` (fail-closed `CASE_BARS_DIGEST_MISMATCH` / `VERSION_DIGEST_MISMATCH`). Fixture: `backend/tests/fixtures/golden_set/golden_set_v1.json` (v`GS-2026-11-02`, 3 pinned cases, hand-written 40-bar paths). Tests (16, all executed green at baseline — §6): `test_golden_set.py::test_fixture_file_digest_matches_pinned_reference` :68 (pinned file digest, :45–48), `::test_version_cases_digest_matches_pinned_and_embedded` :73, `::test_parse_refuses_tampered_bars` :281, `::test_cases_digest_excludes_created_at_utc` :331 | The module docstring itself (golden_set.py:3–10) cites roadmap line 189 and explicitly states it "makes NO capability claim of any kind and asserts NO superiority over any external system". Reference-side golden/benchmark data: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 15 | AI assistant layer | `backend/app/services/ai_service.py:214` `AIContextBuilder`, `:263` `FallbackAIProvider` (deterministic fallback: `assistant` :268, `analyst` :315, `optimizer` :364, `research` :406, `strategy` :452, `risk` :478), `:537` `AIService`; REST: `backend/app/api/routes.py:556` `/ai/assistant`, `:563` `/ai/analyze`, `:570` `/ai/optimize`, `:577` `/ai/intelligence/{symbol}`, `:586` `/ai/research`, `:593` `/ai/strategy`, `:600` `/ai/risk`; tablocastic context feed `ai_service.py:323`. Tests: `test_ai_service.py::test_ai_api_smoke_assistant` :74, `::test_ai_api_invalid_filter_is_controlled` :94 | Reference has no documented AI layer: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 16 | AI research loop (synthetic/paper) | `backend/app/services/ai2_research_loop.py:284` `AI2ResearchLoopRunner` (budget verdicts, duplicate pre-classification, injected clocks, episodic artifact append; shadow runs mapped to non-COMPLETED so governed acceptance can never accept them — `::test_outcome_status_map_pins_shadow_to_non_completed` test_ai2_research_loop.py:182, `::test_append_record_idempotent_helper` :526); `backend/app/services/multi_agent_runtime.py:113–220` (bounded-parallel waves, step timeouts); `backend/app/domain/multi_agent_failure_model.py` (9-kind taxonomy). Runtime switch **OFF by default**: `backend/app/core/config.py:111` `ai2_enabled = _env_bool("AI2_ENABLED", "0")`; synthetic transports only (MA-1 record §5, lines 127–129) | Reference has no documented AI research loop: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 17 | Persistence | `backend/app/data/store.py:25` `class Store` (SQLite/WAL), `:48` `_run_migrations` (`PRAGMA user_version`, additive), `:233` `save_market_snapshot`, `:362` `save_alerts`, `:421–450` portfolio CRUD, `:452` `save_big_moves`, `:529` `filter_save`, `:556` `save_notify_log`; governed alert ops store `backend/app/data/alert_ops_store.py`. Tests: `test_data_domain.py::test_data_trust_state_classification` :10, `::test_iran_instrument_from_snapshot_preserves_farsi_and_ids` :34 | Reference persistence (portfolio save button etc. per screenshot, `summary-of-tablokhani-videos.md:117,143`) mechanism: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 18 | Alerting / notifications | `backend/app/services/notifier.py:20` `Notifier` (Telegram + Bale tokens :52–53, decrypted-token handling :27), `backend/app/domain/alert_operations.py` (D-AI-30 governed ops: budgets, kill-switch, dedup — `test_dai30_alert_operations.py::test_budgets_owner_pinned_exact_values` :143, `::test_service_rejects_blocked_trust_before_queueing` :265, `::test_kill_switch_gate_fail_closed_on_missing` :284), `backend/app/domain/governed_alerts.py` (9-kind closed vocabulary — `test_p5p6_governed_alerts.py::test_each_of_the_nine_corpus_kinds_representable` :92), engine trigger `backend/app/engines/confluence.py:203` `pick_notify_alerts`; delivery channels listed `docs/STATUS.md`/README.md:21 (WebSocket/Telegram/Bale) | Reference alerting described only as periodic page refresh (`summary-of-tablokhani-videos.md:129`); push/telegram alerting of reference: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 19 | Windows / Electron packaging | `electron/main.js:1–40` (BrowserWindow 1400×900, `contextIsolation: true`, origin allow-list `isAllowedNavigation`), `electron/package.json`, `electron/icon.ico`, `scripts/windows/`; CI windows-validation job per MA-1 record §8 :159 (W1 boot … W6 browser E2E 7/7, W7 log posture — verified on SHA `1832b75`, not re-run in this sandbox). Tests: `test_gov24_desktop_shell.py::test_package_json_version_is_settings_version` :22, `::test_windows_icon_is_a_valid_ico_and_referenced` :37, `::test_shell_security_preferences_unchanged` :60. Honest limitation: MA-1 §6 :144–145 — Windows **target-machine** validation remains owner-gated (CI green ≠ target install) | Reference desktop packaging: **NOT_DESCRIBED_IN_SOURCES** (screenshot shows a web page, `summary-of-tablokhani-videos.md:113–150`) | NOT_COMPARED_WITH_EVIDENCE |
| 20 | Backup / restore | `backend/app/data/store.py:62` `backup(keep=7)` (WAL checkpoint → copy → prune); `docs/active/BACKUP_RESTORE_RUNBOOK.md:1–30` (documents verified code paths only; alert-ops rollback :27–30) | **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 21 | Hot money (پول داغ / پول داغ پلاس) | `backend/app/engines/screener.py:187` `build_hot_money`, `:154` `_flow_score`; schema field `backend/app/models/schemas.py:272` `flow_score`; thresholds `backend/app/core/config.py:47` (`hot_money_threshold: float = 200_000_000`) and `:54` (`smart_per_capita_min: float = 25_000_000`), consumed at `tablocastic.py:78,106`; README.md:67–68 (>200M / 100–200M). Frontend heatmap: `frontend/js/tabs/data.js:87–96` (heat tiles), `frontend/js/components/heat-tiles.js:1–3`. Tests: **no dedicated screener unit test** (fields exercised via `test_market_intelligence_service.py:30`, contract tests) | Videos doc :68–79: per-capita ≥200M = hot, 100–200M = plus; `CHANGELOG_V13_IDEAS_TABLOKHANI.md:5–8` (flow_score idea 1.3 implemented). RADAR thresholds match the taught thresholds (README.md:67–68); **whether the runtime behaviour matches the reference site itself is unmeasured** | NOT_COMPARED_WITH_EVIDENCE |
| 22 | Big-player game (بازی بازار) | `backend/app/engines/screener.py:242` `build_market_game` (incl. `hunt_champion`); `backend/app/models/schemas.py:287` `hunt_champion`; frontend champions `frontend/js/tabs/data.js:194,212`; `CHANGELOG_V13_IDEAS_TABLOKHANI.md:14–18` (idea 2.1). Tests: none dedicated (as row 21) | Videos doc :97–109 (big/mid/retail bias, dominant = "ورود بزرگان"); frontend attribution `frontend/index.html:895` ("مشابه «بازی بزرگان» تابلوخوانی") | NOT_COMPARED_WITH_EVIDENCE |
| 23 | Big moves / 10-minute deltas (تحرکات بزرگان) | `backend/app/engines/big_moves.py:117` `compute_big_moves`, `:23` `flow_coverage_sec`, `:32` `ensure_flow_history`, `:100` `bootstrap_history_if_empty`; store `backend/app/data/store.py:452` `save_big_moves`; frontend matrix view `frontend/js/tabs/data.js:117–125` (`bigView === "matrix"`) + `heat-tiles.js:1–3`. Tests: none dedicated; service wiring exercised via `test_refresh_false_fresh.py` | Videos doc :49–64: Δ net/power/volume/percent scoring; explicitly notes RADAR shows `actual_window_sec`/`coverage_sec` "که تابلوخوانی نداره" (:64) — an **unverified intent claim** (see §4 claim C6), and CHANGELOG_V13:19–21 implemented the heatmap | NOT_COMPARED_WITH_EVIDENCE |
| 24 | Rant / leader / growth-potential filters (رانتی، لیدر، مستعد رشد) | Industry flow `backend/app/engines/screener.py:293` `build_industry_flow`; entry-score gating in `tablocastic.py:166` (`m.entry_score`) and hot-money conditions (`tablocastic.py:93,152–159`); per-video pseudocode thresholds are partially encoded in config-gated metrics (`backend/app/engines/metrics.py:20` `compute_metrics`: buy_power, volume_ratio, per-capita). Tests: `test_metrics.py::test_compute_metrics_finite` :4, `::test_flow_coverage` :12 | Videos doc :14–27 (rant filter pseudocode), :32–45 (leader formula `tval*0.1 + buy_power*10 + …`), :83–91 (growth-potential `entry_score>=65 and hot_net>10 …`). **The literal leader-scoring formula of video 2 is NOT found verbatim in the current tree** — only the industry-flow analogue (`build_industry_flow`) — so this row is partial | UNKNOWN(partial implementation: reference formulas from `summary-of-tablokhani-videos.md:39–44` have no verbatim in-repo implementation; only related constructs exist; and no reference-site comparison exists) |
| 25 | Tablocastic proprietary indices (D+, M+, M/D, عدد طلایی, queue power, cross-minutes) | `backend/app/engines/tablocastic.py:1–10` (docstring: "شاخص‌های اختصاصی تابلوخوانی", operational definitions), `:63` `compute_tablocastic`, `:210` `rank_tablocastic`; API `backend/app/api/routes.py:252–258` (`GET /api/tablocastic`), preview `routes.py:152`; wired in `market_service.py:192,416,638,648,701–702,935`; consumed by `filter_dsl.py:75`, `confluence.py:40`, `market_map.py:78`, `api/chart.py:134`, `api/excellent.py:56–60`, AI context `ai_service.py:323`, `domain/ai_intelligence.py:129`; explainer notes `engines/ai_explainer.py:37–41`. Tests: **no dedicated engine unit test** (honest gap); indirect: `test_ai_intelligence_core.py:20` (tablocastic context contract), `test_ai_service.py:35`, `test_g2_runtime_gate.py:345`, `test_p3_75_data_trust_hardening.py:44`, `test_p3_77_local_hardening.py:187,277`, `test_p3_81_ai_contracts.py:39`, `test_refresh_false_fresh.py:71,104,132` (service field), `test_excellent.py::test_ai_explainer` :37–51 (golden_number/d_plus explanation path). **Direct-run evidence at baseline:** `compute_tablocastic` + `rank_tablocastic` executed on a mock snapshot → grade/golden_number/d_plus/m_plus returned (scratch `tablocastic_direct_run.txt`) | The video teach generic board concepts (buy power, per-capita, queue pressure — `summary-of-tablokhani-videos.md:17,22–27`); the SPECIFIC D+/M+/عدد طلایی/cross-minutes definitions are RADAR's own synthesis "نزدیک به مفاهیم رایج تابلوخوانی" (tablocastic.py:3), not a documented reference-site feature: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 26 | Market watchlist board (دیده‌بان بورس) | `frontend/js/modules/render/watchlist_excellent.js:1–57` (summary cards from real overview, industry filter, search, refresh), `:90` CSV export wiring, `:133–147` `exportWatchlistToCSV` (UTF-8 BOM). Tests: none dedicated; page-level `e2e/test_smoke.py::test_main_dashboard_has_no_uncaught_errors` :68 | Screenshot feature list `summary-of-tablokhani-videos.md:113–150`: 4 header buttons, summary bar (total/positive/negative/avg/volume/value :119), industry filter + 11-column picker :122, per-column dropdown filters :125, per-second refresh :129, CSV/Excel save :138, portfolio save :143. RADAR implements a subset (summary, industry filter, search, CSV, refresh — watchlist_excellent.js:1–5) and **does NOT document the 11-column picker or per-column range filters** | NOT_COMPARED_WITH_EVIDENCE |
| 27 | Market map / industries / confluence | `backend/app/engines/market_map.py:58` `build_market_map` (uses tablocastic :78); `backend/app/engines/screener.py:293` `build_industry_flow`; `backend/app/engines/confluence.py:21` `build_confluence_board`, `:203` `pick_notify_alerts`; REST: `backend/app/api/routes.py` (`/api/market-map`, `/api/confluence` in heavy-path list `core/rate_limiter.py:41`). Tests: none dedicated for map/confluence math (contract-level coverage only) | Videos doc :32–45 (industry leader concept); `docs/active/PROJECT_CONTINUITY_HANDOFF.md:177` (confluence = "Combined technical/fundamental/flow board"); specific reference-site equivalents: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 28 | Fundamental filter | `backend/app/engines/fundamental.py` (engine present; consumed in `market_service.py` `_build_filter_row` and `confluence.py`), README.md:73 ("فیلتر بنیادی — P/E، EPS، ارزش بازار"); dossier layer `backend/app/domain/fundamental_dossier.py`. Tests: `test_amendment_p0_dossier_audit_prediction.py` (dossier contracts) | Videos doc mentions fundamentals only tangentially; reference fundamentals capability: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |
| 29 | Support / resistance auto-detection | `frontend/js/modules/support_resistance.js:1–8` (`findSupportResistance`, swing high/low + clustering), toggle in `frontend/js/modules/render/tradingview_excellent.js`; `CHANGELOG_V13_IDEAS_TABLOKHANI.md:28–31` (idea 4.1 — Forex chart S/R). Tests: none dedicated | The V13 doc derives this from TabloKhani-site image analysis (its title line 1–3); the reference site's own S/R feature: **NOT_DESCRIBED_IN_SOURCES** (the screenshot section :113–150 does not show it) | NOT_COMPARED_WITH_EVIDENCE |
| 30 | Market thermometer (دماسنج بازار) | `backend/app/engines/screener.py:114` `build_thermometer` (score −100..+100); `backend/app/models/schemas.py:314` `thermometer`; frontend `frontend/js/components/thermometer.js:2`, wired `frontend/js/main.js:10,64,248`; `CHANGELOG_V13_IDEAS_TABLOKHANI.md:23–27` (idea 5.1). Tests: none dedicated | **NOT_DESCRIBED_IN_SOURCES** (V13 marks it as an idea from TabloKhani image analysis; the archive screenshot list :115–131 shows no thermometer) | NOT_COMPARED_WITH_EVIDENCE |
| 31 | Forex / gold / broker charts | `backend/app/data/forex_provider.py:2` (brokers + volume profile), `frontend/js/modules/forex.js:5–16` (POC/VAH/VAL + MA/EMA/RSI + custom indicator). Tests: `test_forex.py::test_gold_has_three_brokers` :15, `::test_gc1_comex` :22, `::test_dxy_tvc` :29, `::test_capital_com_indices_and_oil` :36, `::test_broker_list_complete` :55 | **NOT_DESCRIBED_IN_SOURCES** (reference is an Iran-market board reader; forex layer is RADAR Phase-6 scope per README.md:23) | NOT_COMPARED_WITH_EVIDENCE |
| 32 | Heatmap tiles (hot money + big moves) | `frontend/js/components/heat-tiles.js:1–3` ("کاشی‌های هیت‌مپ (پول داغ / تحرکات بزرگان)"); hot-money tiles `frontend/js/tabs/data.js:87–96`; big-moves matrix `frontend/js/tabs/data.js:117–125`. Tests: none dedicated. **Path note:** `CHANGELOG_V13_IDEAS_TABLOKHANI.md:12,21` cites `frontend/js/app.js::renderHot/renderBig`, but `frontend/js/app.js` **no longer exists** (frontend restructured to `js/main.js`/`js/tabs/`/`js/modules/`); current-tree evidence above is what survives | `CHANGELOG_V13_IDEAS_TABLOKHANI.md:10–12` (idea 1.1) and :19–21 (idea 3.1) — implemented FROM TabloKhani-site image analysis; reference-site heatmap feature itself: **NOT_DESCRIBED_IN_SOURCES** | NOT_COMPARED_WITH_EVIDENCE |

## 4. Claim inventory (comparative phrasing — exact file:line, status)

Rule applied: `docs/governance/amendment_sources_2026-10-02/03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md:111`
("the 03:111 evidence rule") — superiority claims require versioned benchmark evidence.
MA-1 already flagged the README/frontend phrasing for the OWNER
(`docs/active/MA1_CONSOLIDATED_EXECUTION_RECORD_2026-11-02.md:26` audit finding A3 and
§6 lines 150–151: "flagged for owner, not changed"). **T5 has not edited any of these.**
Removal/rewording awaits the owner's ruling.

| ID | Location (exact) | Text (verbatim) | Nature | Status |
|---|---|---|---|---|
| C1 | `README.md:3` | `پلتفرم تحت‌وب تابلوخوانی و رصد حرفه‌ای سهام بورس ایران — الهام‌گرفته و بهینه‌تر از [tablokhani.com](https://tablokhani.com)` ("…inspired by and MORE OPTIMIZED/BETTER THAN tablokhani.com") | **Superiority claim, owner-facing README** | Owner-flagged (MA-1 :26, :150–151); NO supporting benchmark in-repo; awaiting owner ruling per 03:111 |
| C2 | `frontend/js/modules/render/watchlist_excellent.js:2` | `* watchlist_excellent.js - بهتر از tablokhani.com/stock-watchlist` ("better than tablokhani.com/stock-watchlist") | **Superiority claim, code comment** | Owner-flagged (same MA-1 record); NO benchmark; awaiting owner ruling |
| C3 | `frontend/js/modules/render/watchlist_excellent.js:53` | `<h2>👁 دیده‌بان بورس — بهتر از تابلوخوانی</h2>` ("Stock Watchlist — BETTER THAN TabloKhani") | **Superiority claim, USER-VISIBLE UI text** | Owner-flagged (same MA-1 record); NO benchmark; awaiting owner ruling |
| C4 | `docs/archive/phase-reports/INSPECTION_REPORT_V09_ULTIMATE_RUTHLESS.md:1` | `گزارش بازرسی بی‌رحم و بی‌طرف - نسخه Ultimate v0.9 - بهتر از نوآوران، فراز، تابلوخوانی` ("…better than Navaran, Faraz, TabloKhani") | Superiority claim (also vs. two other sites), historical phase report | Archived historical record (MA-1 §5: historical records untouched); not covered by the MA-1 README/frontend flag but same 03:111 tension; listed for the owner |
| C5 | `docs/archive/phase-reports/CHART_EXCELLENT_V08.md:73` | `این نسخه برای استفاده شخصی از هر دو سایت بهتره چون تمام امکانات اونا + امکانات اختصاصی تابلوخوانی و AI رو یکجا داره.` ("this version is better than both sites for personal use…") | Superiority claim, historical phase report | Archived historical record; same status as C4 |
| C6 | `docs/archive/phase-reports/summary-of-tablokhani-videos.md:28` | `**بهبود ما نسبت به تابلوخوانی:** تابلوخوانی فقط فیلتر میده، ما دلیل هر سهم رو هم میگیم + ریسک…` | Comparative INTENT claim (planning note, not measured result) | Primary reference source; preserved verbatim as evidence; NO measured benchmark backs it; also :45, :64, :93, :133–134 carry the same "بهبود ما نسبت به تابلوخوانی" pattern (per-reason explanations :28, leader follower signals :45, coverage window :64, next-day prediction :93, board gap list :133–134) |
| C7 | `docs/archive/phase-reports/summary-of-tablokhani-videos.md:138` | `دکمه ذخیره جدول به CSV/Excel - تابلوخوانی داره، ما هم اضافه کنیم (قبلاً نداریم)` ("TabloKhani HAS it, we don't yet — add it") | **Anti-superiority evidence**: an in-repo admission the reference had a capability RADAR lacked at that time | Historical planning note; feature since implemented (`watchlist_excellent.js:133–147`) but this shows the record's own claims were not uniformly superiority-directed |
| C8 | `README.md:65` | `## ابزارهای اصلی (مشابه تابلوخوانی)` ("main tools SIMILAR TO TabloKhani") | Similarity/attribution, not superiority | Not flagged; benign reference framing; listed for completeness |

Non-comparative reference mentions (NOT claims; inventory only, no action proposed):
`frontend/index.html:6` (page title "تابلوخوانی هوشمند"), `frontend/index.html:895`
("مشابه «بازی بزرگان» تابلوخوانی" — attribution), `frontend/index.html:917` (API doc),
`frontend/js/modules/utils/chart_theme.js:3`, `frontend/js/modules/theme.js:7`,
`frontend/js/symbol.js:415`, `frontend/js/symbol.js:453`, `frontend/css/app.css:512`,
`backend/app/main.py:145`, `backend/app/services/ai_service.py:335`,
`backend/app/engines/confluence.py:1`, `backend/app/engines/ai_explainer.py:54`,
`backend/app/engines/tablocastic.py:1–3` (generic "board reading" usage),
`docs/active/USER_GUIDE_FA.md:22`, `:161`, `:176` (attribution "مطابق/مشابه تابلوخوانی"),
`docs/STATUS.md:75`, `docs/archive/phase-reports/P3.23_REPOSITORY_CONSOLIDATION.md:30,60`,
`docs/active/PROJECT_CONTINUITY_HANDOFF.md:742`, `docs/active/PROJECT_LINK_MANIFEST.md:48`,
`docs/active/CONSOLGOV13_FULL_REMEDIATION_REVALIDATION_2026-10-22.md:238`,
`docs/active/MA1_CONSOLIDATED_EXECUTION_RECORD_2026-11-02.md:26,150,168`,
governance corpus (00:107, 02-EXEC:188–189, 02-MA:110, 03:111, 05:167,170, 06:49),
`electron/main.js:1` ("like faraz.io Windows app" — comparative to a DIFFERENT reference,
style/attribution only). Full transcript: scratch `grep_tablokhani_full.txt`.

## 5. TabloKhani-informed features (what the product ACTUALLY implemented from the materials)

Evidence chain = the two archive docs → current tree:

1. **Tablocastic engine** (proprietary board indices): `backend/app/engines/tablocastic.py:1–218`;
   exposed at `GET /api/tablocastic` (`backend/app/api/routes.py:252–258`), computed per
   refresh (`backend/app/services/market_service.py:416`), surfaced in DSL row context
   (`filter_dsl.py:75`), confluence (`confluence.py:40`), market map (`market_map.py:78`),
   symbol chart (`api/chart.py:134`), analyze (`api/excellent.py:56–60`), AI context
   (`ai_service.py:323`). Direct execution verified at baseline (scratch
   `tablocastic_direct_run.txt`). No dedicated unit test (honest gap, row 25).
2. **Hot money + flow score** (V13 idea 1.3): `backend/app/engines/screener.py:154` `_flow_score`,
   `:187` `build_hot_money`; `backend/app/models/schemas.py:272` `flow_score`;
   thresholds aligned with the taught per-capita tiers (README.md:67–68 vs videos doc :70–72).
3. **Hot-money heatmap** (V13 idea 1.1): current paths `frontend/js/tabs/data.js:87–96`,
   `frontend/js/components/heat-tiles.js:1–3` (V13's original path `frontend/js/app.js`
   is stale — frontend was restructured).
4. **Hunt champions** (V13 idea 2.1): `backend/app/engines/screener.py:242`
   `build_market_game`; `backend/app/models/schemas.py:287` `hunt_champion`;
   `frontend/js/tabs/data.js:194,212`.
5. **Big-moves heatmap/matrix** (V13 idea 3.1): `frontend/js/tabs/data.js:117–125`
   (`bigView === "matrix"`), `frontend/js/components/heat-tiles.js:1–3`; engine
   `backend/app/engines/big_moves.py:117` `compute_big_moves` with
   `flow_coverage_sec` :23 (the videos doc :55–64 taught the Δ-scoring + coverage idea).
6. **Market thermometer** (V13 idea 5.1): `backend/app/engines/screener.py:114`
   `build_thermometer`; `backend/app/models/schemas.py:314`; `frontend/js/components/thermometer.js:2`.
7. **Auto support/resistance on charts** (V13 idea 4.1): `frontend/js/modules/support_resistance.js:1–8`
   `findSupportResistance` (swing points + clustering), toggle in
   `frontend/js/modules/render/tradingview_excellent.js`.
8. **Watchlist board with CSV export** (from the watchlist-screenshot gap list, videos doc
   :133–143 item 3): `frontend/js/modules/render/watchlist_excellent.js:133–147`
   `exportWatchlistToCSV` (UTF-8 BOM), wired `:90`; summary cards from real overview `:61–69`.
9. **Attribution kept honest**: `frontend/index.html:895` describes the big-game scoring as
   "مشابه «بازی بزرگان» تابلوخوانی" (attribution, not superiority); `README.md:65` frames the
   toolset as "مشابه تابلوخوانی".

What the materials taught that has **no verbatim implementation** (gap, honestly recorded):
the literal industry-leader scoring formula of video 2 (`summary-of-tablokhani-videos.md:39–44`,
`tval*0.1 + buy_power*10 + volume_ratio*5 + plp*2` with leader/follower roles) has no
matching verbatim code; the closest construct is `screener.py:293` `build_industry_flow`
(row 24 verdict `UNKNOWN(partial implementation)`).

## 6. Verification appendix (what was executed/checked at baseline `84f9b1b`)

- Golden Set suite (read-only run): `cd backend && PYTHONPATH=. ../.venv/bin/python -m pytest tests/test_golden_set.py -q` → **16 passed** (scratch `pytest_test_golden_set.txt`).
- Tablocastic-adjacent suites: `pytest tests/test_excellent.py tests/test_refresh_false_fresh.py tests/test_metrics.py tests/test_indicators.py -q` → **27 passed** (scratch `pytest_tablocastic_adjacent.txt`).
- Direct engine execution: `compute_tablocastic` + `rank_tablocastic` on a mock `SymbolSnapshot` → OK (scratch `tablocastic_direct_run.txt`).
- Repo-wide grep (incl. Persian spellings تابلوخوانی / تابلو خوانی / تابلوخانی / تابلو خانی): 53 transcript lines (scratch `grep_tablokhani_full.txt`).
- All file:line citations above were grep/Read-verified against the working tree at `84f9b1b`; raw grep transcripts in scratch: `grep_tsetmc.txt`, `grep_backtest.txt`, `grep_volume_profile.txt`, `grep_ai_loop.txt`, `grep_ai_service.txt`, `grep_map_charts.txt`, `watchlist_head.txt`, `test_ids_quant.txt`, `test_ids_ai_data.txt`, `grep_e2e.txt`.
- Test-file line numbers for test ids were read directly from `backend/tests/test_*.py` at the cited lines.

## 7. Evidence gaps found (for the orchestrator)

1. **No measured TabloKhani comparison exists anywhere in-repo** — no reference dataset,
   no reference response capture, no side-by-side benchmark. Every comparative verdict in
   §3 is therefore `NOT_COMPARED_WITH_EVIDENCE`; the only non-default verdict is row 24
   (`UNKNOWN` — partial implementation, definitional).
2. **Golden Set contains zero TabloKhani cases** — it pins RADAR's own engines
   (BACKTEST/WALK_FORWARD/FORWARD_TEST on synthetic 40-bar paths). It is necessary
   infrastructure for a future 03:111-compliant claim but is NOT a comparison.
3. **Dedicated unit tests absent** for: `tablocastic.py`, `screener.py`
   (hot money/game/industry flow/thermometer), `big_moves.py`, `market_map.py`,
   `confluence.py` engine math, volume profile, support/resistance, watchlist rendering.
   Coverage is indirect (service/contract tests) or none.
4. **V13 changelog frontend paths are stale** (`frontend/js/app.js` gone; features survive
   under `js/tabs/`, `js/components/`, `js/modules/`); the archive doc must not be cited
   as evidence of CURRENT file locations.
5. **Owner-gated**: C1–C3 (and archive items C4–C6) remain in place pending the owner's
   03:111 ruling; this matrix deliberately records them without editing (no existing file
   was modified by T5).
