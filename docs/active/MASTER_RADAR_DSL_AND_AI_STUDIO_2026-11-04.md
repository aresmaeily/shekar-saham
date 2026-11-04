# MASTER-RADAR: Strategy DSL (RSL-1) SPECIFICATION + AI STUDIO ARCHITECTURE & SAFETY — 2026-11-04

## Part 1 — Strategy DSL specification (directive §C2; M6)

**Language:** RADAR Strategy Language v1 — `RSL-1.0.0`. Line-oriented, case-insensitive keywords, `#` comments, ASCII identifiers. Reference implementation: `backend/app/engines/strategy_dsl/` (9 modules, 182 dedicated tests).

```
INPUT name = number            # ≤16; typed by literal (int if no decimal point)
RISK stop_loss_pct=2.0, take_profit_pct=4.0, trailing_pct=1.0, max_position_pct=25.0
ENTRY <bool-expr>              # required, exactly one
EXIT <bool-expr>               # optional (default False)
ALERT <bool-expr>              # optional (default False)
```

- **Series bases:** `open high low close volume`. **MTF refs:** `D1/W1/M1/H4/H1` × base (≤3 distinct). **Symbol refs:** `sym("ID").base` (≤2). **Operators:** `+ - * / > < >= <= == != AND OR NOT`, unary minus. **Functions (whitelist, exact arity):** `sma, ema, rsi, stdev, highest, lowest, atr(high,low,close,period), abs, min, max, crossover, crossunder, ref(series, n≥0)`.
- **Types:** number/bool/series; `INPUT`→number; polymorphic `abs/min/max`; comparisons need numeric/series sides; boolean ops need booleans. Errors are typed (`TYPE_*`, `PARSE_*`, `LEX_*`, `SEM_*`, `BUDGET_*`, `LOOKAHEAD_*`, `RUN_*`) with line/col.
- **Deterministic semantics (documented warm-ups):** `sma` 0.0 before period−1; `ema` SMA-seeded at period−1, k=2/(n+1); `rsi` Wilder seeded at index `period`, avg_loss=0→100 / avg_gain=0→0; `stdev` population, 0.0 before warm-up; `highest/lowest` partial-window honestly documented; `atr` Wilder on true-range; `crossover/crossunder` strict with i=0→False; `ref` warm-up 0.0; `x/0 → 0.0` (documented, deterministic).
- **Resource budgets:** ≤512 AST nodes, depth ≤64, source ≤4096 chars, ≤8 args, MTF ≤3, symbols ≤2, INPUT ≤16. Lexer/parser recursion guard 80.
- **Look-ahead safety:** grammar has NO future access; `ref(x, n<0)` is a `LOOKAHEAD_NEGATIVE_REF` error; the runtime regression test appends future bars and proves decisions on the prefix are byte-identical.
- **Sandbox:** no `eval/exec/compile/__import__` (source-scan enforced); hostile inputs (dunder chains, `__import__`, traversal strings, 10k idents, deep unary chains, unicode keyword lookalikes, `1e9` literals) → typed DSLError, never execution (39 tests + 9 fresh audit hostiles).
- **Versioning/migration:** `StrategyApiContract` (dsl_version RSL-1.0.0, api_version 1); `MigrationPolicy.accepted_versions`; no migrations yet (initial version) — policy object exists so future versions migrate explicitly, never silently.
- **Pine-like syntax:** RSL-1 is Pine-INSPIRED for usability. NO Pine Script compatibility is claimed anywhere; an actual compatibility suite would be required first (directive §C2).
- **Execution path:** DSL programs run ONLY through the interpreter over the audited function whitelist. The backtest engine consumes programs via the adapter (`strategy_lab_service.DslBacktestAdapter`); fills happen exclusively in the shared execution model with structural no-look-ahead.

## Part 2 — AI Studio architecture & safety report (directive §C; M7)

**Implemented workflow (§C1 steps 4–10), today, honest:**
1. The user authors RSL-1 source in the Strategy Lab tab (Persian RTL UI, sample template provided; source persisted to localStorage).
2. `POST /api/v10/strategylab/validate` — parse + typecheck + budgets; machine-readable errors.
3. `POST /spec` — formal versioned specification: digest (sha256 of exact source), typed inputs, risk block, canonical expression rendering, DSL contract echo, `generated_by: "user-authored RSL source; AI-proposal seam owner-gated and disconnected"`.
4. `POST /backtest` — product-engine run over seeded SYNTHETIC candles with declared execution assumptions; full §D5 report + reproducibility digest.
5. `POST /paper-replay` — §E paper simulation over a synthetic window, labeled `PAPER_REPLAY_OVER_SYNTHETIC_WINDOW` with an explicit Persian not-live note.
6. `POST /versions` (+`approve`) and `/versions/{id}/promote` — §C3 approval chain `DRAFT → APPROVED (explicit user approve flag) → PROMOTED (paper forward only)`; promotion without APPROVED → 409; registry lists an explicit Persian in-memory-persistence note.

**Safety/governance invariants (verified by tests + audit):**
- AI proposal generation (steps 1–3 of §C1: ambiguity questions, NL→spec, spec→code) is NOT a live path. The seam is documented in `strategy_lab_service` and the router docstrings; `AI2_ENABLED=0`, `verified=False`, `SYNTHETIC_OR_PAPER` unchanged; no provider call exists in any new module (audit C grep: zero network/exec primitives).
- User approval REQUIRED before promotion to paper forward testing (state machine, server-enforced).
- No live trading / broker egress / production mutation / self-modification / autonomy expansion (R-8) — no such code path exists; scope statement in the execution record §5.
- No self-escalation of model permissions: the DSL runtime has a fixed function whitelist; the indicator manager has a fixed permission whitelist; both fail closed.
- Reproducibility metadata: source digest, DSL version, execution model version, engine versions, result digests on every run; ledger hash-chain for paper runs.
- Model/version/prompt recording: NOT-APPLICABLE until the AI seam is owner-enabled (no model call exists to record).
