# OWNER DECISIONS RECORDED — 2026-11-02 (D1–D7 + R-1..R-11)

Provenance and authority: the owner's chat directive of 2026-11-02 enumerated the
gate set (D1–D7, R-1, R-2, R-3, R-5, R-6, R-7, R-8, R-9, R-11) and **explicitly
delegated the selection**: "به دقت بهترین تصمیم رو با دلیل بگو به نحوی که همین الان
انجام بشه و باعث وقفه در کار و به عقب انداختن کارها نشه" — i.e. select the best
executable-now option for each gate, state the reasoning, and complete the
remaining work without delay. Every row below records the chosen option, the
reasoning, and the immediate executable consequence. **Each decision remains
subject to owner veto by a dated reply; nothing here is silently irreversible.**
R-4 was additionally in scope of the same delegation (packet lists it among
owner-gated findings). R-10/R-11 are answered per the delegation; R-11
specifically cannot be exercised by proxy (see row).

Answer-key form (packet template): `D1=A, D2=DEFER-2026-11-02, D3=TABLE-BELOW,
D4=OS-KEYRING+AESGCM, D5=LOCAL-DAILY-KEEP14, D6=SINGLE-USER, D7=RPO24h-RTO15m,
R-1=RECOMMEND-ISSUE-ON-OWNER-MACHINE, R-2=OWNER-EXECUTES-BUNDLE, R-3=KEEP-DENIED,
R-4=REWORD, R-5=ACCEPT-PROPOSAL, R-6=DORMANT-MANUAL-ONLY, R-7=NO-EXTERNAL-CLASS+
TWO-KEY-REQUIRED, R-8=NO-EXPANSION, R-9=INBOX-ONLY-E6-STAYS-DISCONNECTED,
R-10=STANDING-GRANT-FORWARD-ONLY, R-11=READY-FOR-ACT`

## D1–D7 — AI-3 research-memory persistence

| ID | Decision | Reasoning | Executable consequence this cycle |
|---|---|---|---|
| D1 | **SQLite-WAL + content-addressed blobs** (incumbent candidate) | Matches the shipped product store precedent (`Store`, SQLite WAL, `data/shekar.db`); zero new infrastructure; runs offline on a single-user Windows desktop; content-addressing feeds the existing `verify_integrity` contracts unchanged; Postgres-class requires a server the deployment does not have; pure JSONL is the weaker test-layer reference already superseded by this adapter class | Production adapter `app/data/research_memory_sqlite.py` implemented + registered in the acceptance-scaffold factory registry (one-entry addition, by design); no runtime auto-wiring — engine activation stays a separate gate |
| D2 | **Defer, dated 2026-11-02** (no agent access to the target machine) | Least privilege: the engineering agent never receives remote access to the owner's Windows device; nothing repo-side is blocked by this deferment; target-machine evidence collection is owner-executed | Target-machine checklist + evidence-bundle spec remain the operative documents; re-evaluation on the owner's next directive |
| D3 | **Per-class retention table**: episodic evidence = PERMANENT (architectural no-purge); semantic lesson history = PERMANENT (retire ≠ delete; retirement is a version-chain state, never deletion); product tick/snapshot retention unchanged (36h `HISTORY_KEEP_HOURS`); research-memory backups per D5 (keep=14) | Evidence immutability is the core AI-3 guarantee (no purge path exists in the Protocol by construction); storage sizing derives from "everything permanent + daily backups" | Constants exported from the adapter module; no delete/update statements in the adapter (AST-checkable) |
| D4 | **OS keyring (Windows Credential Manager via `keyring`, option E-B) + AES-256-GCM at rest** | DPAPI (E-A) binds secrets to a Windows user profile and breaks under service contexts / non-Windows dev; a vault (E-C infra) adds operations the deployment lacks; none (E-D) is unacceptable for evidence integrity; keyring is cross-platform and the de-facto OS-keychain access path. Key is never in code/logs; **fail-closed** without a key. Optional dependency: `keyring` import-guarded — install-time opt-in, env-var override (`RADAR_RESEARCH_MEMORY_KEY`) supported for headless/CI contexts | Encryption layer implemented in the adapter (AEAD, per-record nonce, table+id as associated data); tests prove ciphertext-at-rest contains no plaintext |
| D5 | **Local destination, daily cadence, keep=14**: `data/backups/research-memory/`, SQLite backup-API snapshot + SHA256SUMS manifest; offsite explicitly deferred until the owner provides destination/credentials | Matches the shipped `Store.backup(keep=7)` precedent; automated offsite requires owner infrastructure that does not exist; local daily is the largest cadence achievable without a scheduler runtime (R-6 posture) | `backup()` + `verify_backup()` implemented and tested (RTO drill support) |
| D6 | **Single-user** access model | Desktop single-operator product posture; the OS file ACL is the boundary; a role file adds attack surface for a deployment that has no shared-machine scenario today | Recorded; re-openable by dated owner act if deployment posture changes |
| D7 | **RPO ≤ 24h, RTO ≤ 15 minutes** | With daily local backups + WAL, worst-case loss = current-day appends (episodic evidence re-appendable from the WAL/archive); restore = file copy-back + `verify_integrity` (minutes). These are the acceptance thresholds for the target-machine recovery drill | Thresholds recorded in `TARGET_MACHINE_EVIDENCE_CHECKLIST_2026-11-02.md` phase table via the decisions packet addendum; functional restore drill covered by tests repo-side |

## R-1..R-11

| ID | Decision | Reasoning |
|---|---|---|
| R-1 | INSTALL stays **NOT ISSUED remotely**; recommendation recorded: owner issues `INSTALL=ISSUED <date>` and runs `scripts/windows/install.ps1` per `P343_INSTALL_CHECKLIST.md` | Per-step exit criteria can only be observed on the target machine (P3.43 principle); a remote AI-issued INSTALL cannot observe them. Everything repo-side is made install-ready this cycle so the owner's single act suffices |
| R-2 | Access **NOT granted to the agent**; the owner runs the scripted sequence and returns the evidence bundle (the packet's own alternative path) | Least privilege; checklist Phase-8 bundle spec is ready; nothing repo-side is blocked |
| R-3 | **KEEP-DENIED** for the current release: `SYNTHETIC_OR_PAPER` only, `AI2_ENABLED=0`, `verified=False` unchanged; live provider = **next-version governed work item** requiring a dated act + secure credential delivery + compliance review | Mandatory controls preserved; no credentials exist in this environment; the chart surface is built to run on synthetic/paper with honest badges. F-1 (`DATA_SOURCE=auto` display-layer nuance) stays HIGH/OWNER-GATED/technically-unresolved in the shipped product — severity not downgraded by this record |
| R-4 | **(a) Reword** to evidence-backed neutral phrasing — the three live loci (`README.md:3`, `watchlist_excellent.js:2`, `:53`) reworded this cycle; archived docs untouched (history) | 03:111 evidence rule; the capability matrix honestly reports 31/32 rows `NOT_COMPARED_WITH_EVIDENCE` — an unsupported "بهینه‌تر از/بهتر از" comparative claim is a product-integrity risk. Neutral phrasing keeps the inspiration attribution without the unsupported comparison |
| R-5 | **ACCEPT `AI4_SANDBOX_LIMITS_PROPOSAL.md` §4 verbatim**: `max_evaluator_invocations=8`, `max_wall_seconds=3600`, `retry_attempts=3`, `concurrency=2`, kill switch default ENGAGED | All five values sit inside the project's own shipped structural caps (no contract widening); grounded in monitoring/AI-2 precedents; the sandbox runtime still does not exist, so nothing activates — budgets leave proposal class for the future runtime integration |
| R-6 | **Dormant runtime only**: scheduler may exist in code with kill switch default ENGAGED (already the posture, `domain/proactive_research.py:102`); cadence = **manual trigger only** this release; budget = R-5 numbers; scheduled operation requires a separate dated owner act on the owner machine | No autonomous behavior without owner supervision; consistent with 06 §9 (no hard-coded budgets before approval — now satisfied by R-5) |
| R-7 | **No external source class admitted this release** (`admission_state` stays `PENDING_OWNER_DECISION` for external tiers; only first-party/local classes in use); **Two-Key Rule = REQUIRED** (`requires_two_key=True`) for any future external-class admission; custodian identities remain unassigned until the owner names two distinct people (blocks nothing — nothing is admitted); D-AI-29 stays gate-deferred | Consistent with R-3 (no live/external data); the Two-Key structural mechanism already makes compliant authorization expressible and non-compliant unrepresentable; injection-scan floor stays unwaivable |
| R-8 | **No autonomy expansion** — D-AI-31 deferred posture remains until a dated owner act with evidence | Autonomy expansion is the highest-irreversibility class; evidence cannot exist yet; "best executable-now decision" = keep the gate |
| R-9 | **IN_PRODUCT_INBOX only**; E6 stays **disconnected**; no external delivery channel is implemented or configured | No external delivery without owner-provided channel credentials + consent; the type-closed inbox and its AST no-egress proof remain the shipped posture; wiring stays a documented future-work item |
| R-10 | **STANDING GRANT** for forward-only publication through the authorized deploy-key path, with remote read-back + exact-SHA CI verification each cycle; amend/rebase/reset/force-push remain forbidden | Formalizes the working practice already proven across every prior cycle; retains every safety property while removing per-cycle friction (the owner asked for no delays) |
| R-11 | **READY-FOR-ACT**: final acceptance remains the owner's single Role-1 act; this cycle delivers the consolidated acceptance bundle (records, matrix, decisions, checklist) | Acceptance cannot be delegated or proxy-executed; per directive §11 no global percentage is computed — phase-by-phase status is reported |

## Governance invariants re-verified this cycle (unchanged)

`AI2_ENABLED=0`; `verified=False`; `SYNTHETIC_OR_PAPER` evidence class only; no
live trading; kill switch ENGAGED; no purge/destructive-retention path; no
unauthorized external alert delivery; no autonomous production learning; no
history rewrite (forward-only commits); no secrets in source/logs/reports.
