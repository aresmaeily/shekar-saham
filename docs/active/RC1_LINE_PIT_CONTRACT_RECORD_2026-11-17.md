# RC1 — LINE-LEVEL PIT CONTRACT RECORD (2026-11-17)

Record of the intended contract, decided and documented BEFORE the
implementation change, per the final RC1 audit directive (Section 1). This is
a forward-only remediation record; nothing here weakens the statement-level
guarantees delivered in 78ad314 and nothing changes the publication-time /
retrieval-time cutoff semantics.

## 1. Scope

Two remaining audit findings in `backend/app/domain/fundamental_line_pit.py`,
function `resolve_line_at_cutoff()`:

1. With `reporting_period` omitted, the docstring says the function collapses
   to the latest reporting period, but the implementation checked conflicts
   across ALL eligible periods and returned `CONFLICTING_SOURCES` before
   selecting the latest-period winner. An older-period conflict could
   therefore prevent a valid latest-period result from being returned.
2. `LineResolution.reporting_period` was defined but not populated by direct
   calls to `resolve_line_at_cutoff()` (including calls WITH an explicit
   `reporting_period`).

## 2. Contract decision (the intended contract)

The line-level API is and remains a SINGLE-PERIOD, SELECTED-PERIOD
resolution. The statement-level API (`resolve_statement_at_cutoff`) is and
remains the complete MULTI-PERIOD view. The five contract clauses:

* **C1 — period selection.** With an explicit `reporting_period` (a period
  key as produced by `_period_key`), the pool is EXACTLY that period — exact
  key match, never fuzzy: a key matching no fact returns `NO_FACT` with the
  requested key still named in `LineResolution.reporting_period` (fail-closed;
  the function never guesses a neighbouring period, so an ambiguous or
  malformed key cannot silently resolve to something else).
* **C2 — collapse.** With no explicit period, the pool spans every period
  present and the function collapses to the MOST RECENT REPORTING PERIOD
  (period_end, ties broken by latest availability then fact_id — the same
  deterministic ordering as the documented collapse winner).
* **C3 — conflict scoping.** Conflict detection applies ONLY to the selected
  period. A conflict in a non-selected period can never mask the selected
  period's result. Nothing is silently resolved: older periods — including
  any of their conflicts — remain fully resolvable and inspectable via
  `resolve_statement_at_cutoff`, which resolves every
  `(metric, reporting_period)` pair independently, and `period_keys` always
  surfaces which periods were present in the pool. A conflict in the SELECTED
  period still refuses to silently choose (`CONFLICTING_SOURCES`).
* **C4 — metadata.** `LineResolution.reporting_period` is populated on every
  return path: the requested key for explicit selections (including
  `NO_FACT`), the selected period's key for the collapse path whenever a
  period was selected (`RESOLVED` / `NOT_AVAILABLE` / `CONFLICTING_SOURCES`),
  and `None` only where no period could be selected (empty pool, or no
  eligible fact with no explicit selection — the pool periods remain visible
  via `period_keys`).
* **C5 — chain scoping + unchanged semantics.** `superseded_chain` is the
  SELECTED period's chain (history recorded, never deleted); per-period chains
  for other periods are available through the statement API. Eligibility
  (KNOWN publication time <= cutoff, otherwise retrieval time <= cutoff),
  restatement-version precedence, `NOT_AVAILABLE` honesty and the
  statement-level multi-period API are byte-for-byte unchanged.

## 3. Why this contract (rationale)

* The module's own docstrings already pinned the line-level collapse to the
  latest period; the implementation deviated from its documented contract.
  The fix restores implementation == documentation instead of redefining the
  contract to match the defect.
* The corpus discipline ("conflicting figures ... are SURFACED, never
  silently resolved") is preserved: a conflict in the selected period still
  surfaces; older-period conflicts are surfaced by the statement API, which
  is the documented multi-period surface. The line-level collapse result now
  NAMES the period it collapsed to, so nothing is implicit.
* No pre-existing test pinned the old all-periods conflict scan for the
  omitted-period path (verified against the full test file); the
  statement-level behavior is untouched (its per-pair explicit-period calls
  are unaffected by construction).

## 4. Required tests (added; all new, none modified)

1. older-period conflict with a valid latest period — latest period resolves;
   the older conflict is NOT silently resolved (statement API still surfaces
   it, `conflicting_fact_ids` stays scoped to the selected period).
2. conflict in the selected period — `CONFLICTING_SOURCES` with explicit and
   with omitted selection; metadata names the conflicting period.
3. explicit period selection returns the selected period in the result
   metadata for every state (`RESOLVED`, and the fail-closed paths).
4. missing or ambiguous period — unknown key and malformed key both fail
   closed as `NO_FACT` with the requested key named; no fuzzy fallback.
5. existing statement-level multi-period, restatement, conflict-isolation and
   cutoff tests remain unchanged and passing (full battery re-run at the
   remediation tree; counts recorded in the evidence package).
