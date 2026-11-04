# TABLOKHANI CAPABILITY MATRIX — 2026-11-03 (direct-test refresh)

- **Task:** WDA-D (roadmap-closure, directive §5) — the "TabloKhani capability matrix
  document" explicitly deferred as "the next authorized docs task", delivered here
  together with direct capability tests.
- **Predecessor:** `docs/active/TABLOKHANI_CAPABILITY_MATRIX.md` (2026-11-02, 32
  capabilities, evidence-based, no superiority claims). That document remains the
  full capability/claim inventory (C1–C8); THIS document refreshes it with
  **direct, hand-derived capability tests** delivered in the same wave and a
  stricter implementation status per row.
- **Baseline:** additive-only wave on top of the 2026-11-02 tree; battery before
  this wave: 1594 passed / 1 skipped. New tests: 18 (`test_corporate_actions.py`)
  + 18 (`test_universe_membership.py`) + 12 (`test_tablokhani_capability.py`).
- **Comparison boundary (unchanged, restated):** no parity or superiority claim
  versus tablokhani.com (یا هر سایت مرجع دیگر از جمله فراز) is made or implied
  anywhere in this matrix. A comparative verdict requires a measured, repeatable
  comparison against the vendor's **public interface**; the repo contains no
  vendor public-interface evidence and zero measured head-to-head comparisons
  (2026-11-02 matrix §2.3: 31/32 rows honestly `NOT_COMPARED_WITH_EVIDENCE`).
  Comparison-with-vendor is therefore **out of scope** for this document.

## 1. Status vocabulary (honest statuses only)

Exactly one status per row:

| Status | Meaning |
|---|---|
| `EXISTS` | The capability is implemented AND directly exercised by a named test against the actual public function/service, with hand-derived expectations. |
| `PARTIAL` | The implementation exists (cited file:line) but direct-test coverage is absent or incomplete; behavior is NOT pinned by tests in this wave. |
| `MISSING` | The capability does not exist in the repo (implementation absent), even if adjacent infrastructure exists. |
| `NOT-VERIFIED` | The capability cannot be honestly assessed from in-repo evidence alone (e.g., anything requiring the vendor's public interface or a measured benchmark). Never upgraded to EXISTS without evidence. |

## 2. Capability matrix

| # | Capability | Repo evidence (function + test) | Status | Notes |
|---|---|---|---|---|
| 1 | Ranked board list (رتبه‌بندی تابلو) — ordering by (quality_score, golden_number, d_plus) desc | `app/engines/tablocastic.py::rank_tablocastic` + `backend/tests/test_tablokhani_capability.py::test_rank_tablocastic_orders_strong_neutral_dead` | EXISTS | Full order pinned on strong/neutral/dead synthetic boards; each sort-key component separately pinned strict. Expectations hand-derived from committed formulas, independent of internals. |
| 2 | Rank limit / truncation to top-ranked | `rank_tablocastic(limit=…)` + `::test_rank_tablocastic_limit_truncates_to_top_ranked` | EXISTS | limit=2/1/beyond-input all pinned against the derived order. |
| 3 | Ranking determinism (double-run identical) | `rank_tablocastic` + `::test_rank_tablocastic_double_run_identical`; per-symbol determinism also `test_tablocastic_screener_bigmoves_units.py::test_tablocastic_deterministic_two_runs_byte_identical` | EXISTS | Dict-level equality over every field incl. notes. |
| 4 | Stable ranked-row output schema | `TablocasticResult.to_dict` + `::test_rank_rows_carry_stable_output_schema` | EXISTS | Exact 21-key row contract pinned for API/UI consumers. |
| 5 | Blank-symbol rows never ranked | `rank_tablocastic` (`if s.l18` filter) + `::test_rank_tablocastic_skips_blank_symbol_rows` | EXISTS | Honesty pin: a row without a symbol is dropped, not fabricated. |
| 6 | Per-symbol board indices: D+, M+, M/D, عدد طلایی, قدرت صف, فشار عرضه/تقاضا | `app/engines/tablocastic.py::compute_tablocastic` + `test_tablocastic_screener_bigmoves_units.py::test_tablocastic_score_components_within_documented_bounds`, `::test_tablocastic_orderbook_pressure_direction`, `::test_tablocastic_in_buy_queue_positive_queue_power_and_note`, `::test_tablocastic_volume_spike_flips_momentum_bonus_sign` + component-dominance pins in `::test_rank_tablocastic_orders_strong_neutral_dead` | EXISTS | Bounds, pressure direction/mirroring, queue notes and spike-sign flip pinned by the hardening wave; hand-derived arithmetic in test comments (e.g., 5,499,300/601,300 → 9.15). |
| 7 | زمان کراس (cross-minutes) + الگوی ساعت | `compute_tablocastic` + `::test_cross_minutes_hand_derived_distinct_case` (30.0 min, "up") and `test_tablocastic_screener_bigmoves_units.py::test_tablocastic_cross_minutes_clamped_to_240_and_direction` (45.0 min, clamp), `::test_tablocastic_hour_pattern_requires_pcp_minus_plp_gap` | EXISTS | Two distinct hand-derived cross cases (45.0 and 30.0); hour-pattern gap boundary pinned. |
| 8 | Grade banding A+/A/B/C/D | `compute_tablocastic` grade thresholds + `::test_grade_banding_extremes_hand_derived` | EXISTS | Extreme bands pinned by hand math (strong ≈90 → "A+"; dead ≈14 → "D"); interior band boundaries (75/60/45) not individually enumerated — noted as remaining gap, band vocabulary closed. |
| 9 | Insufficient-data honest flags (zero order book, no estimable cross) | `compute_tablocastic` + `::test_zero_flow_board_honest_flags` | EXISTS | Zero-flow board → demand/supply pressure 0.0, m_over_d honest `_div` default 0.0, `cross_minutes=None`, `cross_direction="none"` — withheld, never invented. |
| 10 | Hot-money tiering (پول داغ / پول داغ پلاس) | `app/engines/screener.py::build_hot_money` + `::test_hot_money_exact_tier_boundaries` and `test_tablocastic_screener_bigmoves_units.py::test_build_hot_money_tiering_thresholds`, `::test_build_hot_money_sell_side_symmetric_tiering`, `::test_build_hot_money_sorted_by_score_desc`, `::test_build_hot_money_empty_snaps_empty_rows` | EXISTS | Exact ≥-boundary semantics pinned (200M → hot, 100M → plus, 99M → absent); wave-2 pins interior points (400M/150M/50M), ordering, sell-side symmetry, emptiness. |
| 11 | Service-level min-quality filter | `app/services/market_service.py::MarketService.get_tablocastic` + `::test_service_get_tablocastic_min_quality_filter` | EXISTS | ≥min_quality filtering with order preservation and post-filter limit pinned (rows 90/40/65 @ min 60 → [الف, پ]). |
| 12 | Honest empty state (no board / no cached ranking) | `::test_service_get_tablocastic_empty_state_honest_empty`, `::test_rank_tablocastic_empty_input_honest_empty` | EXISTS | Empty board → `[]` from both the service and the ranker; no fabricated rows. |
| 13 | تحرکات بزرگان (big-moves 10-minute delta scoring) | `app/engines/big_moves.py::compute_big_moves` + `test_tablocastic_screener_bigmoves_units.py::test_compute_big_moves_delta_direction_and_min_score`, `::test_compute_big_moves_deterministic_under_fixed_clock`, `::test_compute_big_moves_empty_history_no_moves`, `::test_compute_big_moves_min_score_filters_weak_deltas` | EXISTS | Delta direction, min-score filter, fixed-clock determinism, empty-history honesty pinned by the hardening wave. |
| 14 | API surface `GET /api/tablocastic` + preview | `app/api/routes.py:252` (`tablocastic`), `routes.py:152` (`tablocastic_preview`) | PARTIAL | Endpoint implemented and wired to `MarketService.get_tablocastic`; the service-layer filter is now directly tested (row 11) but NO test hits the HTTP route itself. |
| 15 | بازی بازار (big/mid/retail bias, hunt champion) | `app/engines/screener.py::build_market_game` (`hunt_champion` at `:265`) | PARTIAL | Implementation cited by the 2026-11-02 matrix (row 22); still NO dedicated direct test. |
| 16 | Industry flow / رانتی-لیدر proxy | `app/engines/screener.py::build_industry_flow` | PARTIAL | Implemented and used by `analyze_market` + `/api/market-map`; no dedicated direct test. |
| 17 | دماسنج بازار (market thermometer) | `app/engines/screener.py::build_thermometer` | PARTIAL | Score −100..+100 implemented; no dedicated direct test. |
| 18 | Market map (industries/heat) | `app/engines/market_map.py::build_market_map` (consumes tablocastic at `:78`) | PARTIAL | Implemented; no dedicated direct test. |
| 19 | Volume profile (POC/VAH/VAL) | `frontend/js/modules/volume_profile.js` (frontend-only) | PARTIAL | Frontend implementation only; no backend engine, no dedicated test (2026-11-02 matrix row 4). |
| 20 | Watchlist CSV export | `frontend/js/modules/render/watchlist_excellent.js::exportWatchlistToCSV` | PARTIAL | Implemented (UTF-8 BOM); no dedicated test. |
| 21 | Support/resistance auto-detection | `frontend/js/modules/support_resistance.js::findSupportResistance` | PARTIAL | Frontend implementation; no dedicated test. |
| 22 | TabloKhani-reference benchmark (versioned Golden Set of REFERENCE behaviors) | `app/domain/golden_set.py` infrastructure EXISTS but `backend/tests/fixtures/golden_set/golden_set_v1.json` contains only RADAR-internal regression cases — zero TabloKhani reference measurements | MISSING | The capability "benchmark against the reference methodology" does not exist; building it requires lawful, obtainable reference-behavior data (owner-gated sourcing). |
| 23 | Comparative standing vs tablokhani.com / فراز (parity or superiority) | — | NOT-VERIFIED | Out of scope without public-interface evidence: no vendor public-interface contract, no measured head-to-head benchmark exists in-repo. Per the evidence rule (03:111), no parity/superiority claim is made. |
| 24 | Vendor public-interface evidence (tablokhani.com contract usable for comparison) | — | NOT-VERIFIED | Nothing in-repo documents the vendor's public interface; recording one requires an owner-authorized lawful sourcing pass. |

## 3. No-duplication register

15 dedicated tablocastic/screener/big-moves unit tests already existed from the
MASTER-WAVE-2 hardening wave and are cited above where they are the evidence:

`backend/tests/test_tablocastic_screener_bigmoves_units.py` —
`test_tablocastic_deterministic_two_runs_byte_identical`,
`test_tablocastic_score_components_within_documented_bounds`,
`test_tablocastic_orderbook_pressure_direction`,
`test_tablocastic_in_buy_queue_positive_queue_power_and_note`,
`test_tablocastic_volume_spike_flips_momentum_bonus_sign`,
`test_tablocastic_hour_pattern_requires_pcp_minus_plp_gap`,
`test_tablocastic_cross_minutes_clamped_to_240_and_direction`,
`test_build_hot_money_tiering_thresholds`,
`test_build_hot_money_sell_side_symmetric_tiering`,
`test_build_hot_money_sorted_by_score_desc`,
`test_build_hot_money_empty_snaps_empty_rows`,
`test_compute_big_moves_delta_direction_and_min_score`,
`test_compute_big_moves_deterministic_under_fixed_clock`,
`test_compute_big_moves_empty_history_no_moves`,
`test_compute_big_moves_min_score_filters_weak_deltas`.

The 12 tests added in `backend/tests/test_tablokhani_capability.py` deliberately use
DIFFERENT hand-computed inputs (30.0-minute cross case; exact 200M/100M/99M tier
boundaries; rank surfaces; service-level filters) — complementary pins, not re-runs
of the wave-2 cases.

## 4. Honesty notes

1. **Every `EXISTS` row cites a named test** exercising the actual public
   function/service with hand-derived expectations (arithmetic in test comments),
   never values copied from an engine run.
2. **`PARTIAL` rows claim implementation, not verification** — direct-test gaps
   are stated, not papered over (rows 14–21; the API route, market game,
   industry flow, thermometer, market map and the three frontend surfaces remain
   unpinned).
3. **No superiority/parity claim anywhere** — rows 23–24 record that comparison
   with the vendor is NOT-VERIFIED and stays out of scope until a lawful,
   measured, repeatable public-interface comparison exists (03:111 evidence rule;
   2026-11-02 matrix §2.3 and claim inventory C1–C8 remain authoritative on
   comparative phrasing).
4. Status tally: **EXISTS 13 · PARTIAL 8 · MISSING 1 · NOT-VERIFIED 2** (24 rows).

## 5. Related WDA-D deliverables (research-integrity, outside TabloKhani scope)

This wave also closed two P2 research-integrity gaps with direct tests (out of
the TabloKhani matrix scope, recorded for the roadmap):

- `backend/app/domain/corporate_actions.py` + `backend/tests/test_corporate_actions.py`
  (18 tests): closed Iranian-market event taxonomy, hand-computed adjustment
  factors, chronological composition with fail-closed chronology/window refusals,
  publish-time PIT discipline (`APPLICABLE_ANNOUNCE_UNKNOWN` honest unknown,
  `NOT_YET_PUBLIC` refusal).
- `backend/app/domain/universe_membership.py` + `backend/tests/test_universe_membership.py`
  (18 tests): half-open `[effective_from, effective_to)` membership convention,
  fail-closed `UNKNOWN_UNCLASSIFIED`, and `survivorship_risk_verdict()`
  delegating to the existing `survivorship_guard` verdicts.
