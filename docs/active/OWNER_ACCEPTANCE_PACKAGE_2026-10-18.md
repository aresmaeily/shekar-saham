# OWNER ACCEPTANCE PACKAGE — 2026-10-18 (pre-G2 contract blocks)

Status: PREPARED FOR OWNER DECISION — nothing in this package is owner-accepted
by its author. Every "independently verified" statement below was re-executed or
re-inspected at HEAD `37c529d` during the 2026-10-18 acceptance audit (fresh
baseline: ahead 19 / behind 0 vs `origin/main` `c1984e7`, tracked tree clean,
4 untracked bootstrap paths preserved, 7-file amendment corpus byte-identical).

Evidence basis for ALL items (re-executed 2026-10-18, raw outputs preserved at
`docs/governance/evidence/raw/2026-10-18_acceptance/`):

| Check | Command (cwd) | Result |
|---|---|---|
| Full suite | `.venv/bin/python -m pytest tests/ -q` (backend/) | **512 passed / 2 warnings / 78.24s / exit 0** (2 warnings = pre-existing starlette/anyio deprecations) |
| New-block focused | `pytest tests/test_ai2_f_governance.py tests/test_ai_ma_contracts.py tests/test_ai3_research_memory.py -q` | 62 passed (24 + 25 + 13) — raw `pytest_focused_new_blocks_3file.txt`; all-blocks focused run (5 files) = 164 passed, raw `pytest_new_blocks.txt` |
| Bytecode | `python -m compileall -q app tests` | exit 0 |
| Lint | `python -m pyflakes app tests` | exit 0, 0 findings |
| Dependencies | `python -m pip_audit -f json` | 67 deps, 0 vulnerable |
| Bootstrap | `python scripts/validate_bootstrap_config.py` (repo root) | 8/8 PASS, 0 FAIL |
| Git hygiene | `git diff --check` | clean |

Each block also carries its own preserved independent audit
(`docs/governance/evidence/2026-10-18_*_independent_audit.md`), including the
original FAIL verdicts and remediation history — none of that history was
rewritten. Classification below follows the roadmap ledger: these five blocks
are at the **pre-G2 contract class** ("bounded design, schema work, synthetic
tests"; `02` line 202) — contract-level completion, NOT runtime integration or
operational readiness (D-AI-41).

---

## Item 1 — P0-AMD-1 / P0-AMD-1a (commits `357f4b6` + `b3cbeb1`)

**Implemented.** Owner amendment corpus import (7 files, byte-identical to the
owner upload — SHA-256 manifest re-verified 2026-10-18) plus six additive P0
contract modules: `source_registry.py` (tiers/precedence/coverage incl.
structurally-unrepresentable universal-coverage claim), `evidence.py`
(mandatory retrieval time; publication-time consistency both directions;
later-of availability; PIT eligibility; corroboration excludes syndicated
copies), `fundamental_dossier.py` (identity ambiguity surfaced; restatement
chains; 3-way role separation; M&A signal requires dedicated evidence),
`monitoring.py` (kill switch default ENGAGED; `idempotency_required` type-locked
True; retry/budget ceilings), `product_audit.py` (`advisory_only` type-locked
True; no APPLIED/DEPLOYED state representable; telemetry repurposing
type-locked False), `prediction.py` (horizon after registration; outcome before
registration rejected; pre-maturity evaluation refused). 44 corpus-derived
tests.

**Independently verified (2026-10-18).** Import byte-integrity (7/7 SHA-256 +
cmp against upload originals); corpus→code traceability of all six modules;
44/44 tests inside the 512-pass battery; additive-only (no route/service
wiring — zero imports in `app/api`, `app/services`); audit verdict chain
FAIL(narrow P0AMD1-01..05) → remediation `b3cbeb1` → PASS, history preserved.

**Unverified / incomplete.** Runtime integration of all six schemas (no job
scheduler, no ingestion pipeline, no telemetry collection exists); the
deployment constants (retry 10 / timeout 3600s / concurrency 8 / 60 runs/h;
rate caps 10,000/min) are engineering-authority values (`05` §Engineering
authority), never numerically owner-approved. Residual honesty notes from the
acceptance inspection: `CompanyDossier.pit_eligible` is a self-declared flag
not cross-validated against `facts_at_cutoff()`; `EvidenceItem.source_tier` is
a free string not bound to the closed `SourceTier` vocabulary; an anomalous
`publication_time > retrieval_time` is neutralized (later-of) rather than
rejected; `attach_outcome` permits mid-horizon observation attach (evaluation
still blocked until maturity) and `evaluate()` does not order
`evaluated_at >= observed_at`. None is a leakage path; all are candidates for
the next contract hardening pass.

**Implications.** Security: no secret fields; credentials_required is
declarative only. Governance: gates unchanged (`AI2_ENABLED=0`, G2 NOT_PASSED,
`live_verified=false`); schemas enforce fail-closed semantics that later
runtime code must reuse (not reimplement). Compatibility: additive; no
pre-existing file modified. Operational: zero runtime footprint today.

**Exact acceptance criteria.** (1) Corpus import byte-identity — evidence:
manifest + cmp outputs. (2) Contract semantics match `02:131-139` — evidence:
audit §2 traceability table + acceptance inspection. (3) 44 tests pass —
evidence: battery. (4) No wiring — evidence: import grep. (5) Honesty: no
capability-status upgrade (D-AI-41) — evidence: record + STATUS rows.

**Recommended decision: ACCEPT** (as pre-G2 contract deliverable), with the
residual notes above scheduled into the next contract hardening pass and
numeric ceilings ratified or amended by the owner at runtime-integration time.

---

## Item 2 — AI1-GC / AI1-GCa (commits `ea3277e` + `2f86c4a`)

**Implemented.** AI-1 Central Brain gap closure (`02` lines 39–42): four
additive modules — `run_governance.py` (frozen RunContext/RunProvenance;
L4 requires APPROVED+approver; provenance-completeness gate per `03:40`),
`memory_interfaces.py` (episodic append-only with no update/delete path;
semantic version chains with supersession), `opportunity.py` (four owner
object kinds; M&A requires evidence basis + dedicated evidence, never
score-only; seven-attribute objects; five-explanation clusters),
`monitoring_governance.py` (cycle record embeds CoverageReport; permission
exclusively via P0 `effective_run_permission`; failed sources force
PARTIAL/FAILED; universal coverage unrepresentable). 58 corpus-derived tests
(31+27). Interpreter/regime/filter-intelligence/risk-context capabilities were
assessed as pre-existing-satisfied (gap matrix, honestly documented).

**Independently verified (2026-10-18).** All four modules re-inspected at
function level; 58/58 tests inside the battery; additive-only, unwired; audit
chain FAIL(narrow AI1GC-01..06) → docs-only remediation `2f86c4a` → PASS,
preserved.

**Unverified / incomplete.** Runtime orchestration does not exist (no caller
of the provenance/autonomy gates — enforcement-by-invocation); opportunity
evidence ids have no referential integrity to the evidence layer (declared
boundary); semantic RETIRED status had no producing operation in this module
(later delivered by AI3-M `research_memory.py:298-318`); `MemoryOperationKind`
is dead schema (disclosed AI1GC-06); monitoring cycle does not check
`sources_attempted` against `spec.target_source_ids`, and budget ceilings are
inherited from P0 contracts rather than enforced at cycle level.

**Implications.** Security/governance: provenance gating and autonomy ceiling
are the canonical reuse points for every later governed run (AI2-F and AI-MA-C
already consume them). Compatibility: additive. Operational: none until wired.

**Exact acceptance criteria.** (1) The four capability contracts implement the
`02:39-42` nouns they claim — evidence: scope report + audit §2 + inspection.
(2) 58 tests pass — evidence: battery. (3) Gap matrix honesty (existing-code
claims verified) — evidence: audit §4. (4) Gates unchanged — evidence:
config + import grep.

**Recommended decision: ACCEPT** (as pre-G2 contract deliverable), noting the
enforcement-by-invocation design means runtime integration must call the gates
— a binding requirement to carry into AI-4/AI-5 contracts.

---

## Item 3 — AI2-F / AI2-Fa (commits `6aeeaa2` + `17ef611`)

**Implemented.** AI-2 required-items layer (`02` lines 44–53) as one additive
module `ai2_governance.py`: frozen run identity + task whitelist; budget
spec bounded (≤16 iterations / ≤64 provider invocations / ≤86400s) with
ceiling-inclusive clock-free verdict; evidence artifacts sha256-bound and
status-consistent; duplicate classification + append-only ledger (no
update/delete path; idempotent re-append; conflict raises); deterministic-gate
refusals never retried (`ESCALATE_FAIL_CLOSED`); invalidation as labels on new
ledger records (canonical trust ranking aligned to
`config._legacy_trust_level_from_state` — the AI2F-05 remediation); governed
acceptance blocking pending/rejected approval and identity/provenance gaps.
24 corpus-derived tests.

**Independently verified (2026-10-18).** All eight required items mapped to
enforcing symbols; trust ranking compared state-by-state against
`config.py:191-196` — exact agreement on all six canonical `DataTrustState`
values incl. `mixed`; 24/24 tests inside battery; unwired; audit chain
FAIL(narrow AI2F-01..06) → `17ef611` → PASS with AI2F-06 residual later fixed
in `e385415` — history preserved.

**Unverified / incomplete.** Runtime integration: `ai2_service.py` remains the
gated, default-off service; the required-items layer is not yet consumed by it
(consumption is post-G2 work). Residual observations: `governed_acceptance`
does not consult `record.status` (a FAILED-status record with clean identity
and NOT_REQUIRED acceptance would pass — undisclosed choice); record-level
APPROVED has no approver field (the docstring delegates to RunContext, but the
record's own approval is taken at face value; a test kwarg is silently ignored
under pydantic v2 `extra=ignore`); unknown trust strings rank −1 (below mock)
where config folds them to synthetic — fail-closed direction but a residual
divergence; `AI2RunStatus` GATED_NOT_EXECUTED/FAILED and `AI2InvalidationRule`
are vocabulary/records with no consuming logic yet; dead validator
`SpecialistContract._shape` and dead constant `MAX_HIERARCHY_DEPTH` live in
`multi_agent.py` (Item 4).

**Implications.** Security: fail-closed posture intact; no LLM, no network, no
clock in the module. Governance: this is the layer G2 will validate for the
required items; keeping it unwired until G2 is the governance-correct state.
Compatibility: additive; `ai2_service.py` untouched by AI2-F. Operational:
none.

**Exact acceptance criteria.** (1) All eight `02:44-53` items enforced —
evidence: audit table + inspection. (2) 24 tests pass — battery. (3) Trust
ranking canonical — inspection vs config. (4) Service untouched, gates
unchanged — grep + config.

**Recommended decision: ACCEPT WITH CONDITIONS** — conditions: (a) the
residual observations (status-consultation gap, record-level approver binding,
unknown-trust-string folding) are dispositioned in the next AI-2 contract
touch (they are one-commit remediable); (b) nothing here implies AI-2 runtime
readiness — G2 + owner acceptance (checklist R3/R4) remain prerequisites.

---

## Item 4 — AI-MA-C / AI-MA-Ca (commits `e385415` + `aa86c3c`)

**Implemented.** Multi-agent runtime **contract** layer AI-MA-1..6 (`02` lines
55–81): thin orchestrator (two-level depth structurally enforced; plan DAG
acyclicity; no financial truth), capability registry + full specialist
contracts (all eight `03` attributes + admission extras incl. owner change
record for consequential specialists), AI-MA-3 composition rule
(`bind_specialist_to_step`), bounded parallelism (`MAX_PARALLEL_BRANCHES=4`,
default 2, waves split never merged), artifact-first exchange (SUCCEEDED
requires artifact unless summary_only; failed/degraded payload-free),
trace log append-only bound to run_id, failure isolation (dependents ⇒
TERMINATE_RUN; independent ⇒ continue), peer-to-peer addressing structurally
refused, no autonomous spawning (no runtime machinery exists at all). 25
corpus-derived tests.

**Independently verified (2026-10-18).** AI-MA-1..6 mapped to symbols; the
`aa86c3c` remediation diff verified (composition rule + `bind_run_context` +
dead-conditional removal + summary bound + disclosures); zero
thread/process/asyncio imports; unwired; audit PASS with dispositions in
`aa86c3c`.

**Unverified / incomplete.** No runtime exists (D-AI-41 respected by design);
DEGRADED `BranchResult` can carry no artifact AND no summary (error names say
`failed_*` but govern DEGRADED too — undisclosed semantics worth one docstring
line); dead code `_shape` validator and `MAX_HIERARCHY_DEPTH` constant;
`isolate_failure` ignores `failure_behavior` contract field (structural
containment only — documented); partial failure-model mapping (nine corpus
failure kinds → generic status/failure_code) — disclosed in module docstring.

**Implications.** Governance: roles-stay-lenses (D-AI-17/18) and no-spawning
are structural, not conventional. Security: payload-free failures prevent
error-channel data leaks. Compatibility: additive. Operational: none.

**Exact acceptance criteria.** (1) AI-MA-1..6 contracts present and enforced —
inspection + audit. (2) 25 tests pass — battery. (3) Prohibition set
(`02:81`) structurally enforced — tests (peer-to-peer, depth, no-spawn-by-
construction). (4) Runtime NOT instantiated — import surface grep.

**Recommended decision: ACCEPT** (as pre-G2 contract deliverable); fold the
DEGRADED-exchange docstring line and dead-code removal into the next AI-MA
touch.

---

## Item 5 — AI3-M / AI3-Ma (commits `80585c8` + `37c529d`)

**Implemented.** Research Memory system contracts (`02` lines 83–85):
`EpisodicRunArtifact` (frozen; mandatory information cutoff with anti-look-
ahead `cutoff ≤ recorded_at`; sha256/commit shapes; explicit-None version
honesty) + `EpisodicRunArchive` (append-only; idempotent/conflict; NO
update/delete/retention-purge path; PIT `available_at`); `SemanticLesson`
(mandatory citation of archived episodic sources — `derive_lesson` refuses
unknown artifact ids; version chains; curation basis DETERMINISTIC_RULE or
HUMAN_REVIEW) + `SemanticLessonStore` (register/supersede/retire as NEW
terminal versions; history never rewritten); `lessons_active_at` PIT view.
13 corpus-derived tests. Persistence technology deliberately unspecified
(corpus specifies none) — see `AI3_PERSISTENCE_DECISION_BRIEF.md`.

**Independently verified (2026-10-18).** Module read in full; corpus loci
(02:83-85/142/159/198, 06 §7, D-AI-22/28) verified verbatim; 13/13 tests in
battery; unwired; audit PASS (AI3M-01 comment-direction fix in `37c529d`,
behavior test-pinned; AI3M-02/03 INFO disclosed).

**Unverified / incomplete.** Persistence (owner deployment decision — the
exactly-isolated blocker); live feeding of episodic artifacts (requires
G2-passed research runtime); `lessons_active_at` uses one-sided conservative
semantics (a supersession recorded after the cutoff hides the older active
version at that cutoff — disclosed AI3M-02 with status-event log as future
additive option); memory acceptance evidence beyond contracts NOT PROVEN
(D-AI-41).

**Implications.** Governance: D-AI-28 split enforced structurally; no memory
operation can express a production mutation (closed operation vocabulary).
Security: no secrets, no I/O. Compatibility: additive; consumes only P0
evidence utilities + AI1-GC ArtifactRef. Operational: none.

**Exact acceptance criteria.** (1) Episodic immutability structural — no
mutation API (test-pinned). (2) Semantic curation/versioning/retirement —
chain guards + retire test. (3) PIT honesty — cutoff mandatory + PIT views.
(4) 13 tests pass — battery. (5) Blocker isolation — persistence decision
brief delivered (companion doc).

**Recommended decision: ACCEPT** (as pre-G2 contract deliverable) **with the
persistence decision explicitly routed to the owner** via
`AI3_PERSISTENCE_DECISION_BRIEF.md` (which lists the missing owner decisions;
it does not choose for the owner).

---

## Ledger statement

Recommended ledger state after owner decisions: each block
`VERIFIED_PENDING_ACCEPTANCE` today; on owner ACCEPT → `ACCEPTED` (contract
class) with runtime integration rows remaining separate and gated. No
project-wide completion percentage is implied or invented. Owner acceptance
must be recorded by the owner (absence of response is not approval).

---

# CURRENCY ADDENDUM — 2026-10-20 (POST-AI-3 directive independent verification cycle)

Status: read-only re-verification of this package's five block verdicts at the
current HEAD; NOT an acceptance; the original 2026-10-18 package (baseline
`37c529d`) is preserved unchanged above as history. No owner decision is
recorded or implied by this addendum.

## What was re-verified at HEAD `a8d6e19` (2026-10-20)

- **Commit chains:** all five blocks' commits (P0-AMD-1 `357f4b6` + P0-AMD-1a
  `b3cbeb1`; AI1-GC `ea3277e` + AI1-GCa `2f86c4a`; AI2-F `6aeeaa2` + AI2-Fa
  `17ef611`; AI-MA-C `e385415` + AI-MA-Ca `aa86c3c`; AI3-M `80585c8` + AI3-Ma
  `37c529d`) are verified ancestors of HEAD; per-commit `--stat` matches the
  recorded file/line counts exactly.
- **Tests re-executed (fresh at-HEAD run, raw
  `docs/governance/evidence/raw/2026-10-20_postai3_battery/`):** P0-AMD-1 44,
  AI1-GC 58, AI2-F 24, AI-MA-C 25, AI3-M 13 — all green, counts unchanged from
  this package's evidence basis; full suite **621 passed / 2 pre-existing
  warnings / 77.65s** (the suite has since grown by AI-4 51 + AI-6 58 beyond
  this package's 512-test baseline).
- **Audit chains:** each block's independent audit file re-confirmed present
  with its FAIL → remediation → PASS history preserved verbatim (P0-AMD-1,
  AI1-GC, AI2-F) or PASS verdicts (AI-MA-C, AI3-M) intact.
- **Structural spot-checks:** no network/subprocess primitive in any of the 15
  contract modules (no unintended reachability); AI-1 autonomy ceiling +
  `REFUSED_BY_POLICY`; AI-2 canonical `_TRUST_RANK` incl. `mixed` + append-only
  ledger; AI-MA structural `peer_to_peer_addressing_refused` + cycle
  detection; AI-3 no delete/purge path + mandatory cutoffs + archive
  citations; AI-4 no production lifecycle state exists; AI-6 `TrustLabel`
  locked to UNTRUSTED + distinct-authorizer Two-Key + quarantine ledger.
- **Gates re-verified:** `AI2_ENABLED=0` (`config.py:109`); G2 NOT_PASSED;
  `live_verified=false` (`config.py:270` `verified = False`); no route wiring
  of any contract module in `app/api/` or `app/services/`; LLM NOT EXECUTED;
  no push (live remote `c1984e7` re-verified via `git ls-remote` 2026-10-20).
- **Repository deltas since this package was written:** ACC-PKG/ACCPKGa
  (`45f0b8b`+`a3165c4` — the package, G2 matrix, persistence brief, and
  dependency matrix themselves), AI-4/AI-4a (`6a10e5a`+`cc98c64`), and
  AI-6/AI-6a/AI-6b (`adf8cdf`+`1d9030c`+`a8d6e19`) — each separately recorded
  in the state file §2k–§2m; none of them modified the five blocks'
  contract modules or tests (additive-only discipline).

The five blocks' recommended dispositions and conditions in this package
remain unchanged and remain PENDING owner decision.
