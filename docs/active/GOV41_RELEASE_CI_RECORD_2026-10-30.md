# CONSOL-GOV-41 — Release and CI Execution Record (publication attempt outcome)

**Date:** 2026-10-30 (Asia/Tehran) · **Directive:** CONSOL-GOV-41 A5/A6 · **Discipline:** push target described HEAD-relatively (GOV-40R D8 lesson); the authoritative absolute identity of the final delivery HEAD is sealed ONLY in the post-commit evidence `gov41_evidence/41_identity.txt`.

## 1. Pre-flight checks (all executed, raw output sealed in `gov41_evidence/41_publication.txt`)

| # | Check | Result |
|---|---|---|
| 1 | `git fetch origin` | exit 0 |
| 2 | Remote `main` SHA | `c1984e7979f89f2d727b471deb602953ec62fad5` — unchanged, == expected |
| 3 | Local identity | HEAD-relative: descendant of `c1984e79…`; **75 ahead / 0 behind** at the publication attempt (final count sealed in `gov41_evidence/41_identity.txt`) |
| 4 | FF ancestry (`merge-base --is-ancestor`) | true — a plain fast-forward suffices; no force/rewrite |
| 5 | Tracked worktree | clean (0 dirty) |
| 6 | Credential availability (existence probes; no secret read/printed) | gh ABSENT · credential.helper UNSET · `.netrc` ABSENT · `.git-credentials` ABSENT · `~/.ssh` ABSENT · gh config ABSENT · GitHub env tokens: 0 |
| 7 | Secret scan of the publication delta `c1984e79…..HEAD` (172 files) | **CLEAN** — corrected scan `gov41_evidence/41_secret_scan.txt`: 0 credential-pattern hits; single long-hex hit = SHA-256 prose reference |

## 2. Push attempt (owner-authorized normal fast-forward, no force)

- Command: `GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/true git push origin main`
- Result: **`remote: No anonymous write access.` / `fatal: Authentication failed …` → PUSH_EXIT=128**
- Post-attempt remote SHA: `c1984e7979f89f2d727b471deb602953ec62fad5` (unchanged — nothing published, nothing discarded)

## 3. Honest outcome — acceptance conditions C1–C4 UNMET

- **C1 (local HEAD == origin/main): NOT MET.** **C2 (full history published by FF): NOT MET** (0 of 75+ commits published; the entire chain remains local-only). **C3 (Windows CI success on final commit): NOT MET — no run exists.** **C4 (Ubuntu CI + Docker on final commit): NOT MET — no run exists.**
- **Exact failing condition:** the owner authorized the push (A5) but this execution environment holds **no authorized GitHub write credential and no connected write integration** (all seven existence probes negative). This is the same class of externally-blocked barrier previously recorded as B5/B6 — now with authorization GRANTED and only the credential holder missing.
- This is recorded as a failing condition with raw evidence, NOT disguised as a roadmap item, per the directive's reporting rule.

## 4. CI evidence (git-level authoritative; GitHub REST API rate-limited 403 for this IP)

- Remote `main` tree contains `.github/workflows/ci.yml` ONLY (`git ls-tree origin/main`).
- The local final branch contains `ci.yml` (identical blob) **plus** `.github/workflows/windows.yml` — the approved Windows validation workflow (push/PR-triggered, `windows-latest`, Python 3.12, F-RV1 fixed) is committed locally and will execute on the first authorized push.
- No GOV-41 commit exists on the remote → **zero workflow runs can reference any GOV-41 HEAD**; old CI runs are not evidence for the new HEAD (A6).

## 5. Operator sequence for the authorized credential holder (unchanged in kind)

1. In an environment holding the authorized credential: `git fetch origin`
2. Verify `git rev-parse origin/main` == `c1984e7979f89f2d727b471deb602953ec62fad5` (if it moved: STOP, re-evaluate ancestry, never force)
3. `git push origin main` — plain fast-forward `c1984e79… → <current local main HEAD>` (the local chain already contains everything: decisions, D-AI-30 implementation, tests, this record)
4. Capture from the triggered runs: workflow run IDs + URLs, per-job conclusions, Windows/Ubuntu/Docker results — this record then completes C1–C4.

Prohibitions remain: no `--force`, no history rewrite, no squash, no credential in any log.
