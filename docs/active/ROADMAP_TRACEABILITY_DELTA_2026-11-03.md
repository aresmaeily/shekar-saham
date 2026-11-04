# ROADMAP TRACEABILITY DELTA — 2026-11-03 (directive §5/§7.6)

Requirement-level delta at this cycle; the standing matrices
(`W2_ROAD_MASTER_ROADMAP_STATUS.md`, `PRODUCT_ROADMAP_LOCK.md`, 17-role audit)
remain authoritative for untouched rows. No accepted work re-opened; no
contract described as an operational runtime feature.

| Requirement (directive §5 list) | Delta this cycle | Status now | Evidence |
|---|---|---|---|
| P2 corporate actions | **IMPLEMENTED** — closed event taxonomy (CASH_DIVIDEND/STOCK_DIVIDEND/SPLIT/REVERSE_SPLIT/CAPITAL_RAISE/CAPITAL_REDUCTION), factor arithmetic, chronological composition with anachronism refusals, publish-time PIT gate (ANNOUNCE_UNKNOWN honest) | IMPLEMENTED (domain contract + tests; no runtime wiring implied) | `app/domain/corporate_actions.py`; `test_corporate_actions.py` (18) |
| P2 historical universe membership | **IMPLEMENTED** — versioned half-open interval table, `members_asof`/`status_asof` fail-closed (UNKNOWN_UNCLASSIFIED), overlap/unordered refusals, survivorship composition DELEGATING to `survivorship_guard` | IMPLEMENTED (domain contract + tests) | `app/domain/universe_membership.py`; `test_universe_membership.py` (18) |
| P2 liquidity pinning | NOT ADDRESSED this cycle — recorded, not hidden | PARTIAL (unchanged) | — |
| P2 fundamental PIT handling | COVERED at the event/membership layer (publish-time PIT + as-of resolution); per-fundamental-line PIT module remains | PARTIAL → improved | corporate_actions PIT statuses |
| P3 research integrity & reproducibility | Reinforced: TabloKhani direct capability tests (12, hand-derived), determinism battery for seeded candles (83), independent indicator fixtures (9); all offline-deterministic | COMPLETE at contract+test layer (unchanged verdicts elsewhere) | new test files |
| P5/P6 internal lifecycle & evidence handling | No delta — already pinned (P6 lifecycle 14 tests in WS-5 wave) | unchanged | — |
| Five product loops | No runtime-wiring delta (owner-gated class); loop contracts unchanged | unchanged | connectivity matrix |
| AI runtime connectivity | Zero runtime callers added (dormancy re-proven); AI-3 adapter status recorded per-item + D5/R-6 reconciled + owner trigger CLI shipped (dormant) | unchanged (by governance) | AI3_OPERATIONAL_STATUS_2026-11-03.md |
| TabloKhani direct capability tests | **DELIVERED** — 12 direct tests on actual public functions + capability matrix doc (24 rows: EXISTS 13 / PARTIAL 8 / MISSING 1 / NOT-VERIFIED 2) | IMPLEMENTED | `test_tablokhani_capability.py`; `TABLOKHANI_CAPABILITY_MATRIX_2026-11-03.md` |
| Security & reliability | No delta this cycle (C-1..C-12 posture intact; new modules scanned: no network, no eval, no secrets) | unchanged | pyflakes + static scans |
| Windows/Electron interactive validation | Static shell gates + version consistency added (16 tests); interactive/behavioral Electron tests remain TARGET-MACHINE-ONLY | PARTIAL (honest) | `test_wda_electron_shell_gates.py`; checklist |

Battery arithmetic for the delta: 1594 (hygiene SHA, WS1 §8/§9) + 200 = **1794
passed / 1 skipped** (one env-conditional skip: G2 harness docs-only-delta
guard — explained, not a failure).
