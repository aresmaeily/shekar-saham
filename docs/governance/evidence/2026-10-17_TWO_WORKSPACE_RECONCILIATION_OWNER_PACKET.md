# OWNER DECISION PACKET — TWO-WORKSPACE RECONCILIATION & BOOTSTRAP ACCEPTANCE

Date: 2026-10-17 (Asia/Tehran) · Tested SHA: `a578abe8296a08152dfb282839519d6d05523647` · Baseline: `c1984e7979f89f2d727b471deb602953ec62fad5`
All facts below are live-verified against this repository on 2026-10-17; raw evidence: `docs/governance/evidence/raw/2026-10-17_two_workspace_reconciliation/`.
**No decision in this packet has been accepted. Each remains PENDING until the owner answers.**

## Verified state summary (inputs to the decisions)

| Fact | Value | Evidence |
|---|---|---|
| Branch / HEAD | `main` @ `a578abe` | `git rev-parse HEAD`; `git status -b` |
| Parent chain | `a578abe` → `6ff6b07` → `c1984e7` → `5206569` | `git log --format=%P` |
| Upstream (live) | GitHub `main` = `c1984e7` (unchanged) | `git ls-remote origin refs/heads/main`, exit 0, 2026-10-17 |
| Ahead / behind | **+2 / −0** | `git rev-list --left-right --count` + live ls-remote |
| Tracked working tree | 0 modified, 0 staged | `git status --porcelain` |
| Untracked (bootstrap set) | `.claude/`, `CLAUDE.md`, `docs/governance/`, `scripts/validate_bootstrap_config.py` | `git status --porcelain` |
| Eight reported commits | ABSENT from object DB | `git cat-file -t` each; full-ref graph |
| Stashes / worktrees | 0 / 1 | `git stash list`; `git worktree list` |
| Fresh battery @ `a578abe` | compileall 0 · pyflakes app 0 · pytest **308 passed / 2 warnings (76.53s)** · pip-audit clean · validator 8/8 · `git diff --check` 0 | raw outputs dir above; exit codes recorded |
| NOT_VERIFIED | Python 3.13 parity · Windows validation · Claude CLI recognition · live providers (`live_verified=false` preserved) | per instruction, marked until directly proven |

## Decision 1 — Which workspace is authoritative

- **Question**: This sandbox holds `c1984e7` + two local commits (`6ff6b07` P3.93 doc alignment, `a578abe` P3.92 docs reconciliation), ahead 2/0 of LIVE GitHub `main`. The eight previously reported commits (`db16a2c`, `cecbccc`, `7526c23`, `f046101`, `2e53aab`, `fd047ae`, `aa31ad3`, `f538806` — reported Bootstrap finalization, P3.92/P3.93/P3.94, security follow-ups, four-agent rename) do **not** exist here and were never observed on GitHub `main`. They belong to a second workspace (likely the owner's Windows tree `F:\RADAR_BOURSE\repo`).
- **Options**: (a) declare this workspace authoritative; (b) declare the other workspace authoritative and export its commits/objects here for review; (c) declare both partial and reconcile manually per-topic.
- **Unlocks**: publication path (Decision 3), roadmap truth (P3.94 and later tasks are NOT_VERIFIED here), G2 evidence chain.
- **Independent gates remaining**: push authorization; amendment-corpus sync; G2.
- **No action taken by this session**: no cherry-pick, merge, rebase, reset, or push; both histories preserved untouched.

## Decision 2 — Bootstrap ZIP / four-agent & eight-skill configuration acceptance

- **Question**: Accept the bootstrap set as the governed Claude Code environment?
- **Verified**: supplied ZIP `radar-bourse-bootstrap-2026-10-16.zip` (sha256 `6c70d74a97d249809bd844eb43b31346a2775ed28948e1289c74cc3bb2c33bd2`, 17 files) vs repo untracked bootstrap set (45 files): **16 identical (sha256)**, **1 changed** (`PROJECT_EXECUTION_STATE.md` — repo copy newer by design), **0 missing**, **28 additional** (post-ZIP raw evidence only). ZIP contains exactly: 4 agents (radar-auditor, radar-chief-architect, radar-developer, radar-qa), 8 skills (radar-architecture, coding-standards, documentation, evidence, forensics, git-workflow, roadmap, testing), `settings.json`, `CLAUDE.md`, validator, BOOTSTRAP-1 evidence, state file. Structural validation: 8/8 PASS (69 path refs resolve; secret scan clean). Neither copy overwritten.
- **Options**: accept as-is; accept with named modifications; reject.
- **Unlocks**: committing the bootstrap set (currently intentionally untracked); agent/skill runtime use on the owner machine.
- **Independent gates remaining**: Claude CLI recognition (NOT_VERIFIED — no CLI in sandbox); owner-machine audit of BOOTSTRAP-1.

## Decision 3 — Retention of the two local commits for later publication

- **Question**: Retain `6ff6b07` + `a578abe` for later push?
- **Verified**: both commits are docs-only (aggregate 6 files, +114/−20; no application code, tests, env, or governance boundary changed); `git diff --check` clean; independent auditor/QA verdicts recorded (PROVEN_WITH_FINDINGS ×2; 308 passed/2 warnings reproduced twice). They are NOT pushed; GitHub `main` re-verified unchanged at `c1984e7` on 2026-10-17.
- **Options**: retain; drop (requires explicit destructive authorization); amend/squash (history rewrite — owner-only).
- **Unlocks**: a single authorized `git push origin main` (fast-forward) when granted.
- **Independent gates remaining**: push credentials on an owner-authenticated machine; Decision 1 (authoritative lineage) must resolve first if the other workspace also advanced `main`.

## Decision 4 — Supply route for the five 2026-10-02 governance documents

- **Question**: How and where will the five original amendment documents be supplied?
- **Verified**: `docs/governance/amendment_sources_2026-10-02/` does not exist in this repo (re-checked 2026-10-17) → the corpus is **NOT_SYNCED**. Expected files (names from governance references): `02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md`, `02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE_CURRENT_2026-10-02.md`, `03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md`, `04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md`, `05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md`.
- **Required form**: the original files, copied verbatim into `docs/governance/amendment_sources_2026-10-02/` (attachment to this chat, or direct placement on the owner machine's repo). They will NOT be reconstructed, summarized, or inferred under any circumstances.
- **Unlocks**: authoritative definitions of G2, 17-role charter, AI governance boundaries, roadmap weights; removes NOT_SYNCED annotations.
- **Independent gates remaining**: G2 independent validation + owner acceptance (still blocks real-data AI-2).

## Decision 5 — Windows `INSTALL` validation authorization

- **Question**: Does the owner authorize Windows `INSTALL` validation?
- **Verified (NOT_VERIFIED items)**: Windows-target validation has never been executed in this environment (Linux sandbox; no Windows host, no Electron runtime, no browser E2E). Present in repo: `install.sh`, `scripts/windows/install.ps1`, `scripts/windows/start.ps1`, `scripts/windows/validate_install.ps1`, `scripts/windows/validate_alpha.ps1`, `docs/active/INSTALL_GUIDE.md`. No install/deployment action will be run without this authorization.
- **If authorized**: the owner runs the Windows pre-install checklist / validators on `F:\RADAR_BOURSE\repo` (or grants a controlled environment), and the results are recorded as evidence here.
- **Unlocks**: P3.43 Controlled Alpha Launch preconditions (Windows validation leg only).
- **Independent gates remaining**: live-provider verification; GitHub push auth; owner launch acceptance.

## Decision 6 — WebSocket query-parameter authentication

- **Question**: Keep / restrict / remove the WS query-param auth channel at `backend/app/main.py:269-278`?
- **Verified behavior**: `@app.websocket("/ws/live")` — when `auth_required` or `private_mode`: accepts `x-api-key` header **or** `api_key` query param, plus optional `token` query param; logs when the query-param channel is used; fail-closed via `authorize_request(...)`/`authorize_ws(...)`; closes with **4401** on failure. Not covered by browser CSRF (WS), but query strings can leak into proxies/access logs.
- **Options**: (a) **keep** — maximum client compatibility (query-param is the only channel for some browser WS clients that cannot set headers); (b) **restrict** — keep header-first, rate-limit/log-only-observation, or shorten token TTL for query-param use; (c) **remove** — header/`authorize_ws` only, requires verifying no deployed client depends on `?api_key=`/`?token=`.
- **Constraints**: owner-gated channel — this session will not remove or restructure it without explicit authorization; any change must come with tests (auth tests currently 5 in `backend/tests/test_auth.py`; suite 308).
- **Unlocks**: security-posture finalization for private mode; affects `SECURITY_PRIVATE_MODE.md` next revision.
- **Independent gates remaining**: G2 security evidence bundle; owner acceptance.

## Session conduct statement

This session performed read-only verification and preparation only: no push, no merge, no rebase, no reset/clean, no history rewrite, no production change, no secret exposure, no live trading, no self-approval of G2, no real-data AI-2 execution. The two local commits remain local; the eight foreign-workspace commits were not fabricated or reconstructed; both bootstrap copies (ZIP and untracked set) were preserved byte-for-byte (ZIP extracted to scratch only).
