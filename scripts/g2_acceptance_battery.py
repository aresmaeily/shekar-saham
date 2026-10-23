#!/usr/bin/env python3
"""G2 acceptance battery harness (CONSOL-GOV-14 §9).

Executes every machine-checkable G2 predicate against the CURRENT commit and
emits a machine-readable criteria-to-evidence report. Read-only: the harness
never mutates repository state, never flips a gate, and can never set G2 to
PASSED -- the G2 verdict authority is the owner alone (charter 04:72 Role 1 A;
register 05:148-150; D-AI-26; review procedure v0.2 T6). A fully green run is
reported as HARNESS_GREEN, which is evidence, not a gate decision.

Evidence freshness (GOV-15): when --evidence-dir is given, the bundle must
commit-bind the CURRENT HEAD via its *harness_report*.json file(s) or the
G2-C-v-fresh predicate reports STALE_EVIDENCE / NO_COMMIT_BINDING /
PARSE_ERROR / NO_HARNESS_REPORT honestly (stale evidence is never accepted).

Implementation binding (GOV-16): the additional G2-C-v-impl predicate
distinguishes implementation evidence from later documentation-only commits:
when the bundle binds a commit B != HEAD, it classifies `git diff --name-only
B..HEAD` as DOCS_ONLY_SINCE (every changed file is a markdown document --
evidence stays valid FOR THE TESTED COMMIT B, which is recorded verbatim;
no claim is made that anything ran at HEAD) or SUBSTANTIVE_CHANGES_SINCE.
This NEVER weakens G2-C-v-fresh: the two predicates are reported separately
and the tested commit is always named exactly.

Predicate sources (canonical):
  - T3 objective criteria: G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md
    (i) full battery green; (ii) findings dispositioned; (iii) gate invariants
    in code; (iv) corpus byte-identity 7/7; (v) evidence manifests verify OK.
  - E1-E6 entry criteria: AI2_G2_REVIEWER_CHECKLIST.md section 9.
  - D-AI-26 (05:102-107): G2 blocks real-data AI-2 until independent
    validation + owner acceptance.

Exit code semantics: 0 = harness executed to completion (verdict is data in
the output); 2 = harness internal failure. A nonzero exit is never a G2
verdict.

Usage:
    python scripts/g2_acceptance_battery.py [--full-battery] [--json OUT.json]
        [--evidence-dir DIR]  (default: latest GOV-14 battery evidence dir)

--full-battery runs the complete backend pytest suite (approx. 80 s).
Without it, the battery predicate is evaluated as NOT_EXECUTED (honest gap),
so the default run is fast and safe for repeated use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Reference digests for the 7 canonical amendment-corpus documents.
# Provenance: captured GOV-6 (consolgov6_audit_scratch/11_corpus_integrity.txt),
# re-verified byte-identical GOV-8/9/10/12/13 and now GOV-14 pre-commit battery.
CORPUS_REFERENCE_DIGESTS = {
    "00_OWNER_ROADMAP_DECISION_CURRENT_2026-10-02.md":
        "be2f08366666320c4e0b16ac9d2d9db0c48449b47c2d7f637b8b299e8e68bca0",
    "02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md":
        "1c44ebe114d42fbe06aeb06db43aeb50b4a8766017800e53a426990878004c8f",
    "02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE_CURRENT_2026-10-02.md":
        "80b09728e5b7a11b041ccc31e09feca6065f9da5fa7377e54dcdd620fd65cf3b",
    "03_AI_GOVERNANCE_BOUNDARIES_CURRENT_2026-10-02.md":
        "e824e1ef2e068acb0f2d138644993d3a5b3a7d955c1a44df73546e6babd727a0",
    "04_17_ROLE_GOVERNANCE_CHARTER_CURRENT_2026-10-02.md":
        "61c413b8c6ebcc5499aaefd3609045fa9b4726a1b32f20344d04dc8b9c3d1176",
    "05_GOVERNANCE_DECISION_REGISTER_CURRENT_2026-10-02.md":
        "2cdb57efd02e8c26860a521199aaa0d365e03e77424c17637526a0dfacaa71a7",
    "06_PRODUCT_CAPABILITY_CHARTER_CONTINUOUS_INTELLIGENCE_2026-10-02.md":
        "2bfbbf05065e303d2c64836268b489f1e1ad7c06d3ecb1f8af3c36fa5f3e5080",
}

PROCEDURE_V02 = (
    "docs/active/G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md"
)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


# --------------------------------------------------------------------------
# pure, individually testable predicates
# --------------------------------------------------------------------------

def approval_block_filled(text: str) -> bool:
    """True iff every approval-block field carries a non-underscore value.

    The v0.2 approval block has four fields; an empty field line looks like
    'Approving authority:        ______...' (only underscores/whitespace
    after the colon). A field is considered FILLED when any non-underscore,
    non-whitespace character follows the colon. Owner-only fields must never
    be filled by the implementing side; this predicate detects a filled
    block honestly (a filled block alone still does NOT constitute a
    verified approval -- the recorded owner decision is separately required).
    """
    filled = 0
    seen = 0
    for line in text.splitlines():
        match = re.match(
            r"^(Approving authority|Approved version|Approval date \(UTC\)|"
            r"Approval evidence / locus):\s*(.*)$",
            line,
        )
        if not match:
            continue
        seen += 1
        value = match.group(2).strip()
        if value and re.search(r"[^_\s]", value):
            filled += 1
    return seen == 4 and filled == 4


def corpus_identity(corpus_dir: Path, reference: dict[str, str]) -> dict:
    """Byte-identity of the 7 canonical corpus docs vs reference digests."""
    results = {}
    for name, expected in reference.items():
        path = corpus_dir / name
        if not path.is_file():
            results[name] = {"ok": False, "reason": "MISSING"}
            continue
        actual = sha256_of(path)
        results[name] = {"ok": actual == expected,
                         "actual": actual, "expected": expected}
    return {
        "identical": sum(1 for r in results.values() if r["ok"]),
        "total": len(reference),
        "all_ok": all(r["ok"] for r in results.values()),
        "files": results,
    }


def gate_flags(config_text: str) -> dict:
    """Extract the two hard-coded gate predicates from config.py text.

    Returns observed values; the caller compares against required values.
    """
    ai2_enabled_default = None
    verified_hardcoded = None
    for line in config_text.splitlines():
        m = re.search(r'ai2_enabled:\s*bool\s*=\s*_env_bool\(\s*"AI2_ENABLED",\s*"([^"]*)"', line)
        if m and ai2_enabled_default is None:
            ai2_enabled_default = m.group(1)
        m2 = re.search(r"^\s{4}verified\s*=\s*(True|False)\s*$", line)
        if m2 and verified_hardcoded is None:
            verified_hardcoded = m2.group(1)
    return {"ai2_enabled_default": ai2_enabled_default,
            "verified_hardcoded": verified_hardcoded}


def ai2_api_surface(api_dir: Path) -> list[str]:
    """Files under app/api referencing ai2 (an AI-2 HTTP route would need one)."""
    hits = []
    for path in sorted(api_dir.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"\bai2\b", text, re.IGNORECASE):
            hits.append(str(path.relative_to(api_dir)))
    return hits


def verify_manifest(evidence_dir: Path) -> dict:
    """Verify a SHA256SUMS.manifest (self + .exit excluded by convention)."""
    manifest = evidence_dir / "SHA256SUMS.manifest"
    if not manifest.is_file():
        return {"ok": False, "reason": "MANIFEST_MISSING"}
    bad, checked = [], 0
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        target = evidence_dir / name
        checked += 1
        if not target.is_file() or sha256_of(target) != digest:
            bad.append(name)
    return {"ok": not bad, "checked": checked, "mismatched": bad}


def evidence_freshness(evidence_dir: Path, current_commit: str) -> dict:
    """Commit-binding check for an evidence bundle (anti-stale-evidence).

    A bundle is FRESH only when every harness report JSON it contains binds
    the CURRENT commit. Any other state is reported honestly:
      - STALE_EVIDENCE     report(s) exist, none binds the current commit
      - MIXED_BINDING      some reports bind the current commit, others do not
      - NO_COMMIT_BINDING  report(s) exist but carry no commit field
      - PARSE_ERROR        a report file is not valid JSON
      - NO_HARNESS_REPORT  no *harness_report*.json in the bundle
    This check is DATA for the reviewer; it can never flip a gate.
    """
    reports = sorted(evidence_dir.glob("*harness_report*.json"))
    if not reports:
        return {"ok": False, "reason": "NO_HARNESS_REPORT", "reports": []}
    bound = []
    for path in reports:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"ok": False, "reason": "PARSE_ERROR", "reports": [path.name]}
        commit = data.get("commit") if isinstance(data, dict) else None
        if not commit:
            return {"ok": False, "reason": "NO_COMMIT_BINDING",
                    "reports": [path.name]}
        bound.append(commit)
    distinct = sorted(set(bound))
    if distinct == [current_commit]:
        return {"ok": True, "reason": "FRESH", "bound_commit": current_commit,
                "reports": [p.name for p in reports]}
    if current_commit in distinct:
        return {"ok": False, "reason": "MIXED_BINDING",
                "bound": distinct, "current": current_commit,
                "reports": [p.name for p in reports]}
    return {"ok": False, "reason": "STALE_EVIDENCE",
            "bound": distinct, "current": current_commit,
            "reports": [p.name for p in reports]}


_DOC_ONLY_RE = re.compile(r"^(docs/|[^/]+\.md$)")


def _is_docs_only(path: str) -> bool:
    """A documentation-only change: markdown under docs/ or a root *.md.

    Code, configuration, tests, scripts, and every non-markdown file are
    SUBSTANTIVE by definition. Markdown documents (product docs and
    governance records alike) carry no executable behavior; the COMPLETE
    delta file list is recorded in the predicate output either way, so a
    reviewer can re-classify any file independently.
    """
    return path.endswith(".md") and bool(_DOC_ONLY_RE.match(path))


def implementation_binding(evidence_dir: Path, current_commit: str) -> dict:
    """GOV-16 evidence-workflow predicate: implementation-evidence binding.

    Establishes the rigorous relationship between the tested implementation
    commit B (the commit bound by the bundle's harness reports) and the
    current HEAD. Self-contained (does NOT inherit G2-C-v-fresh's verdict):
      - FRESH_AT_HEAD              every report binds HEAD
      - DOCS_ONLY_SINCE            all reports bind ONE commit B != HEAD and
                                   every file in `git diff --name-only B..HEAD`
                                   is documentation; the tested implementation
                                   commit is recorded verbatim and remains the
                                   valid evidence anchor (NO claim that
                                   anything ran at HEAD)
      - SUBSTANTIVE_CHANGES_SINCE  a non-documentation file changed in
                                   B..HEAD -- the bundle can no longer stand
                                   for the current tree
      - MIXED_BINDING              reports bind differing commits
      - NO_COMMIT_BINDING / PARSE_ERROR / NO_HARNESS_REPORT
                                   honest structural states
    This predicate is ADDITIVE data for the reviewer; it never flips a gate
    and never relaxes G2-C-v-fresh (which still reports STALE_EVIDENCE for
    any bundle not bound to HEAD -- the two predicates answer DIFFERENT
    questions and are reported side by side).
    """
    reports = sorted(evidence_dir.glob("*harness_report*.json"))
    if not reports:
        return {"ok": False, "reason": "NO_HARNESS_REPORT",
                "tested_commit": None, "delta_files": []}
    bound = []
    for path in reports:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"ok": False, "reason": "PARSE_ERROR",
                    "tested_commit": None, "delta_files": [],
                    "reports": [path.name]}
        commit = data.get("commit") if isinstance(data, dict) else None
        if not commit:
            return {"ok": False, "reason": "NO_COMMIT_BINDING",
                    "tested_commit": None, "delta_files": [],
                    "reports": [path.name]}
        bound.append(commit)
    distinct = sorted(set(bound))
    if distinct == [current_commit]:
        return {"ok": True, "reason": "FRESH_AT_HEAD",
                "tested_commit": current_commit, "delta_files": []}
    if len(distinct) > 1:
        return {"ok": False, "reason": "MIXED_BINDING",
                "tested_commit": None, "delta_files": [],
                "bound": distinct, "current": current_commit}
    tested = distinct[0]
    out = git("diff", "--name-only", tested, current_commit)
    delta = [ln for ln in out.splitlines() if ln.strip()]
    non_docs = [p for p in delta if not _is_docs_only(p)]
    if non_docs:
        return {"ok": False, "reason": "SUBSTANTIVE_CHANGES_SINCE",
                "tested_commit": tested, "delta_files": delta,
                "substantive": non_docs}
    return {"ok": True, "reason": "DOCS_ONLY_SINCE",
            "tested_commit": tested, "delta_files": delta}


# --------------------------------------------------------------------------
# harness assembly
# --------------------------------------------------------------------------

def run_full_pytest() -> dict:
    proc = subprocess.run(
        [str(REPO / ".venv" / "bin" / "python"), "-m", "pytest", "-q", "tests"],
        cwd=REPO / "backend", capture_output=True, text=True,
    )
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    m = re.search(r"(\d+) passed(?:, (\d+) warnings?)?(?: in ([\d.]+)s)?", tail[0])
    return {
        "exit_code": proc.returncode,
        "summary_line": tail[0],
        "passed": int(m.group(1)) if m else None,
        "warnings": int(m.group(2)) if m and m.group(2) else 0,
        "seconds": float(m.group(3)) if m and m.group(3) else None,
    }


def collect(evidence_dir: Path | None, full_battery: bool) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = git("rev-parse", "HEAD")
    parent = git("rev-parse", "HEAD~1")
    branch = git("branch", "--show-current")
    dirty = git("status", "--porcelain")

    checks: list[dict] = []

    def add(cid, predicate, method, observed, required, satisfied, evidence):
        checks.append({"id": cid, "predicate": predicate, "method": method,
                       "observed": observed, "required": required,
                       "satisfied": bool(satisfied), "evidence": evidence})

    # ---- T3(iii) gate invariants in code --------------------------------
    config_text = (REPO / "backend/app/core/config.py").read_text(encoding="utf-8")
    flags = gate_flags(config_text)
    add("G2-C-iii-1",
        "AI2_ENABLED default '0' in backend/app/core/config.py",
        "CODE_PARSE", flags["ai2_enabled_default"], "'0'",
        flags["ai2_enabled_default"] == "0",
        "backend/app/core/config.py (ai2_enabled _env_bool default)")
    add("G2-C-iii-2",
        "live-verification boundary verified=False hard-coded",
        "CODE_PARSE", flags["verified_hardcoded"], "False",
        flags["verified_hardcoded"] == "False",
        "backend/app/core/config.py (verified = False in is_verified_live)")
    api_hits = ai2_api_surface(REPO / "backend/app/api")
    add("G2-C-iii-3",
        "no AI-2 HTTP route (zero ai2 references under backend/app/api)",
        "TREE_SCAN", api_hits or "none", "none", not api_hits,
        "rg-style scan of backend/app/api/*.py")

    # ---- T3(iv) corpus byte-identity ------------------------------------
    corpus = corpus_identity(REPO / "docs/governance/amendment_sources_2026-10-02",
                             CORPUS_REFERENCE_DIGESTS)
    add("G2-C-iv", "amendment corpus byte-identity 7/7 vs pinned digests",
        "DIGEST_COMPARE", f"{corpus['identical']}/{corpus['total']}", "7/7",
        corpus["all_ok"], "embedded reference digests (GOV-6 provenance)")

    # ---- T3(v) evidence manifest ----------------------------------------
    manifest_state = {"ok": False, "reason": "NO_EVIDENCE_DIR_SELECTED"}
    if evidence_dir is not None:
        manifest_state = verify_manifest(evidence_dir)
    add("G2-C-v", "evidence bundle SHA256SUMS.manifest verifies OK",
        "MANIFEST_VERIFY",
        manifest_state.get("reason") or f"checked={manifest_state.get('checked')}, mismatches={len(manifest_state.get('mismatched', []))}",
        "ok", manifest_state.get("ok", False),
        str(evidence_dir) if evidence_dir else "not provided")

    # ---- evidence freshness / commit binding (anti-stale) ----------------
    fresh_state = {"ok": False, "reason": "NO_EVIDENCE_DIR_SELECTED"}
    if evidence_dir is not None:
        fresh_state = evidence_freshness(evidence_dir, head)
    add("G2-C-v-fresh",
        "evidence bundle commit-binds the CURRENT HEAD (no stale evidence)",
        "EVIDENCE_COMMIT_BINDING",
        fresh_state.get("reason"),
        "FRESH",
        fresh_state.get("ok", False),
        str(evidence_dir) if evidence_dir else "not provided")

    # ---- implementation binding (GOV-16: docs-only delta honesty) --------
    impl_state = {"ok": False, "reason": "NO_EVIDENCE_DIR_SELECTED"}
    if evidence_dir is not None:
        impl_state = implementation_binding(evidence_dir, head)
    add("G2-C-v-impl",
        "implementation evidence binds the tested commit; HEAD delta is "
        "docs-only or empty",
        "EVIDENCE_IMPLEMENTATION_BINDING",
        f"{impl_state.get('reason')}; tested={impl_state.get('tested_commit')}",
        "FRESH_AT_HEAD or DOCS_ONLY_SINCE (tested commit recorded)",
        impl_state.get("ok", False),
        str(evidence_dir) if evidence_dir else "not provided")

    # ---- T3(i) full battery ---------------------------------------------
    if full_battery:
        battery = run_full_pytest()
        add("G2-C-i", "full pytest battery green at the current commit",
            "PYTEST_RUN", battery["summary_line"], "exit 0 + N passed",
            battery["exit_code"] == 0 and (battery["passed"] or 0) > 0,
            "pytest -q backend/tests (current-run evidence)")
    else:
        add("G2-C-i", "full pytest battery green at the current commit",
            "PYTEST_RUN", "NOT_EXECUTED (run with --full-battery)",
            "exit 0 + N passed", False,
            "delegate to consolgov14 battery evidence for the current cycle")

    # ---- T3(ii) findings disposition (documentation-derived) -------------
    findings_note = ("documented-state check: canonical record set declares "
                     "zero open CRITICAL/HIGH/MEDIUM; this harness does NOT "
                     "independently re-audit (T4: implementing-side audits "
                     "are evidence for the review, not a substitute)")
    add("G2-C-ii", "all CRITICAL/HIGH/MEDIUM findings dispositioned",
        "DOC_DERIVED", "declared-zero-open (see GOV-13 record defects ledger)",
        "zero open CRITICAL/HIGH/MEDIUM + independent confirmation",
        False, findings_note)

    # ---- E1..E6 entry criteria -------------------------------------------
    add("G2-E1", "reviewed SHA fixed and tree state matches",
        "GIT_STATE", f"HEAD={head} dirty_entries={len(dirty.splitlines())}",
        "review fixed at one full SHA by the reviewer",
        False, "review not convened; reviewed-SHA fixing is a reviewer act")
    add("G2-E2", "evidence package present and internally consistent",
        "DOC_DERIVED", "checklist + AI2-D package present in docs/active",
        "reviewer confirmation", False, "E2 completion requires the reviewer")
    add("G2-E3", "battery reproducible by the reviewer at the reviewed SHA",
        "REVIEWER_ACT", "NOT_VERIFIED", "reviewer-executed reproduction",
        False, "blocked on reviewer appointment (D-O2)")
    e4_ok = (flags["ai2_enabled_default"] == "0"
             and flags["verified_hardcoded"] == "False" and not api_hits)
    add("G2-E4", "governance gates verified in code (subset of C-iii)",
        "CODE_PARSE", f"ai2_default={flags['ai2_enabled_default']}, "
                      f"verified={flags['verified_hardcoded']}, api_hits={len(api_hits)}",
        "all three hold", e4_ok,
        "E4's machine-checkable portion holds; E4 completion = reviewer act")
    add("G2-E5", "known limitations acknowledged in writing by the reviewer",
        "REVIEWER_ACT", "NOT_VERIFIED (E5 NOT_VERIFIED since GOV-10 §A9)",
        "reviewer written acknowledgement (R-A1)", False,
        "blocked on reviewer appointment (D-O2)")
    add("G2-E6", "amendment-corpus status acknowledged",
        "DOC_DERIVED", corpus["identical"] == corpus["total"]
        and "SYNCED" or "MISMATCH",
        "corpus supplied + re-baselined (R1)", corpus["all_ok"],
        "corpus is present and byte-identical; acknowledgement is a reviewer act")

    # ---- procedure approval state (D-O1) ---------------------------------
    proc_text = (REPO / PROCEDURE_V02).read_text(encoding="utf-8")
    filled = approval_block_filled(proc_text)
    decision_record = REPO / "docs/active/OWNER_DELEGATED_DECISIONS_CONSOLGOV16_2026-10-23.md"
    pre_approval_hash = ("0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed"
                         "9b88a9b2cc65dafc")
    dec_ok = False
    if decision_record.is_file():
        dec_text = decision_record.read_text(encoding="utf-8")
        dec_ok = (pre_approval_hash in dec_text
                  and "D-16-1" in dec_text
                  and "APPROVE" in dec_text)
    add("G2-D-O1", "R2 review procedure approved (v1.0; delegated D-16-1)",
        "DOC_STATE+CROSSREF",
        f"approval block {'FILLED' if filled else 'EMPTY'}; "
        f"delegated decision record {'PRESENT' if dec_ok else 'ABSENT'}",
        "block filled AND delegated decision record cites the pre-approval "
        "candidate hash (verbatim-transcription path of the procedure's own "
        "approval clause)",
        filled and dec_ok,
        "delegated approval per CONSOL-GOV-16 §1/§4 — NOT an owner personal "
        "signature; the G2 verdict remains owner-only (T6)")

    harness_green = all(c["satisfied"] for c in checks)
    return {
        "harness": "g2_acceptance_battery.py",
        "generated_utc": now,
        "commit": head,
        "parent": parent,
        "branch": branch,
        "harness_green": harness_green,
        "g2_verdict": "NOT_PASSED",
        "g2_verdict_reason": (
            "G2 verdict authority is the owner alone (04:72 Role 1 A; 05:148-150; "
            "D-AI-26; v0.2 T6). Required but absent: owner-approved procedure "
            "(D-O1), appointed reviewer with written acknowledgement (D-O2/R-A1 "
            "-> E5), COI adjudication (D-O3), convened review at a fixed SHA, "
            "owner-recorded verdict. No harness run can substitute for any of "
            "these. AI2_ENABLED must remain 0 (real-data AI-2 stays blocked)."),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--full-battery", action="store_true",
                        help="run the full backend pytest suite")
    parser.add_argument("--json", metavar="OUT",
                        help="also write the report as JSON")
    parser.add_argument("--evidence-dir", metavar="DIR",
                        help="evidence dir whose SHA256SUMS.manifest to verify")
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir).resolve() if args.evidence_dir else None
    try:
        report = collect(evidence_dir, args.full_battery)
    except Exception as exc:  # noqa: BLE001 - harness must report, not crash
        print(json.dumps({"harness_error": repr(exc)}, indent=2))
        return 2

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.json:
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
