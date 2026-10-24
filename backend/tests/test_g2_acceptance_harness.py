"""Tests for scripts/g2_acceptance_battery.py (CONSOL-GOV-14).

Positive and negative cases for the harness's pure predicates, using
synthetic in-test fixtures (never the real governance files) so a negative
case cannot falsely pass. The harness itself is read-only and can never set
G2 to PASSED; these tests pin that contract.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HARNESS = REPO / "scripts" / "g2_acceptance_battery.py"

_spec = importlib.util.spec_from_file_location("g2_acceptance_battery", HARNESS)
g2 = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("g2_acceptance_battery", g2)
_spec.loader.exec_module(g2)


EMPTY_BLOCK = """\
```text
Approving authority:        ______________________
Approved version:           ______________________  (effective on approval)
Approval date (UTC):        ______________________
Approval evidence / locus:  ______________________
```
"""

FILLED_BLOCK = """\
```text
Approving authority:        OWNER-SIGNATURE-HERE
Approved version:           v0.2  (effective on approval)
Approval date (UTC):        2026-10-23T00:00:00Z
Approval evidence / locus:  decision record §X
```
"""

PARTIAL_BLOCK = """\
```text
Approving authority:        OWNER-SIGNATURE-HERE
Approved version:           ______________________  (effective on approval)
Approval date (UTC):        ______________________
Approval evidence / locus:  ______________________
```
"""


class TestApprovalBlock:
    def test_empty_block_is_not_approved(self):
        assert g2.approval_block_filled(EMPTY_BLOCK) is False

    def test_filled_block_detected(self):
        assert g2.approval_block_filled(FILLED_BLOCK) is True

    def test_partial_block_is_not_approved(self):
        # one filled field of four must NOT count as approved
        assert g2.approval_block_filled(PARTIAL_BLOCK) is False

    def test_missing_fields_is_not_approved(self):
        assert g2.approval_block_filled("no block here at all") is False

    def test_real_procedure_block_state_matches_delegated_decision(self):
        # GOV-16 D-16-1: the live canonical procedure is APPROVED v1.0 via the
        # delegated transcription path; the block is FILLED and the delegated
        # decision record cites the pre-approval candidate hash.
        text = (REPO / "docs/active/"
                "G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md"
                ).read_text(encoding="utf-8")
        assert g2.approval_block_filled(text) is True
        dec = (REPO / "docs/active/"
               "OWNER_DELEGATED_DECISIONS_CONSOLGOV16_2026-10-23.md"
               ).read_text(encoding="utf-8")
        assert "0045febaa59a7baae0baf093c0bb6525b1a5ba138f648eed" \
               "9b88a9b2cc65dafc" in dec
        assert "D-16-1" in dec


class TestCorpusIdentity:
    def test_correct_digests_pass(self, tmp_path):
        ref = {"a.md": "AA" * 32, "b.md": "BB" * 32}
        for name, digest in ref.items():
            # craft content whose sha256 equals the reference via double bookkeeping:
            # instead write real content and compute the real digest list
            data = name.encode()
            real = __import__("hashlib").sha256(data).hexdigest()
            data_ref = {name: real}
            (tmp_path / name).write_bytes(data)
            result = g2.corpus_identity(tmp_path, data_ref)
            assert result["all_ok"] is True
        # silence unused-var warnings for the template refs
        del ref

    def test_tampered_digest_fails(self, tmp_path):
        (tmp_path / "a.md").write_bytes(b"original")
        tampered = {"a.md": "ff" * 32}
        result = g2.corpus_identity(tmp_path, tampered)
        assert result["all_ok"] is False
        assert result["identical"] == 0

    def test_missing_file_fails(self, tmp_path):
        result = g2.corpus_identity(tmp_path, {"absent.md": "aa" * 32})
        assert result["all_ok"] is False
        assert result["files"]["absent.md"]["reason"] == "MISSING"

    def test_live_corpus_matches_pinned_reference(self):
        # 7/7 byte-identity of the real corpus vs the embedded pins
        result = g2.corpus_identity(
            REPO / "docs/governance/amendment_sources_2026-10-02",
            g2.CORPUS_REFERENCE_DIGESTS,
        )
        assert result["all_ok"] is True, result
        assert result["total"] == 7


class TestGateFlags:
    def test_real_config_defaults_off(self):
        text = (REPO / "backend/app/core/config.py").read_text(encoding="utf-8")
        flags = g2.gate_flags(text)
        assert flags["ai2_enabled_default"] == "0"
        assert flags["verified_hardcoded"] == "False"

    def test_flipped_flag_detected_as_violation(self):
        text = 'ai2_enabled: bool = _env_bool("AI2_ENABLED", "1")\n'
        flags = g2.gate_flags(text)
        assert flags["ai2_enabled_default"] == "1"  # observed, caller must reject

    def test_unparseable_config_yields_none(self):
        flags = g2.gate_flags("nothing relevant here\n")
        assert flags["ai2_enabled_default"] is None
        assert flags["verified_hardcoded"] is None


class TestAi2ApiSurface:
    def test_real_api_dir_has_zero_ai2_references(self):
        hits = g2.ai2_api_surface(REPO / "backend/app/api")
        assert hits == [], hits

    def test_synthetic_route_reference_detected(self, tmp_path):
        (tmp_path / "routers.py").write_text(
            'PROHIBITED = "ai2"  # an AI-2 HTTP route would need a bare reference\n',
            encoding="utf-8")
        hits = g2.ai2_api_surface(tmp_path)
        assert hits == ["routers.py"]


class TestManifestVerify:
    def test_valid_manifest_ok(self, tmp_path):
        import hashlib
        (tmp_path / "x.txt").write_bytes(b"hello")
        digest = hashlib.sha256(b"hello").hexdigest()
        (tmp_path / "SHA256SUMS.manifest").write_text(f"{digest}  x.txt\n")
        assert g2.verify_manifest(tmp_path)["ok"] is True

    def test_tampered_file_rejected(self, tmp_path):
        import hashlib
        (tmp_path / "x.txt").write_bytes(b"hello")
        digest = hashlib.sha256(b"hello").hexdigest()
        (tmp_path / "SHA256SUMS.manifest").write_text(f"{digest}  x.txt\n")
        (tmp_path / "x.txt").write_bytes(b"tampered!")
        state = g2.verify_manifest(tmp_path)
        assert state["ok"] is False and state["mismatched"] == ["x.txt"]

    def test_missing_manifest_rejected(self, tmp_path):
        assert g2.verify_manifest(tmp_path)["ok"] is False


class TestEvidenceFreshness:
    """GOV-15: anti-stale-evidence commit-binding checks (positive+negative)."""

    def _write_report(self, evidence_dir, name, payload):
        import json
        (evidence_dir / name).write_text(json.dumps(payload), encoding="utf-8")

    def _current_head(self):
        return g2.git("rev-parse", "HEAD")

    def test_fresh_report_detected(self, tmp_path):
        self._write_report(tmp_path, "g2_harness_report.json",
                           {"commit": self._current_head()})
        state = g2.evidence_freshness(tmp_path, self._current_head())
        assert state["ok"] is True and state["reason"] == "FRESH"

    def test_stale_report_flagged(self, tmp_path):
        stale = "0" * 40
        assert stale != self._current_head()
        self._write_report(tmp_path, "g2_harness_report.json",
                           {"commit": stale})
        state = g2.evidence_freshness(tmp_path, self._current_head())
        assert state["ok"] is False and state["reason"] == "STALE_EVIDENCE"
        assert state["bound"] == [stale]

    def test_mixed_binding_flagged(self, tmp_path):
        stale = "0" * 40
        assert stale != self._current_head()
        self._write_report(tmp_path, "g2_harness_report_a.json",
                           {"commit": self._current_head()})
        self._write_report(tmp_path, "g2_harness_report_b.json",
                           {"commit": stale})
        state = g2.evidence_freshness(tmp_path, self._current_head())
        assert state["ok"] is False and state["reason"] == "MIXED_BINDING"
        assert set(state["bound"]) == {self._current_head(), stale}

    def test_report_without_commit_binding_rejected(self, tmp_path):
        self._write_report(tmp_path, "g2_harness_report.json", {"verdict": "x"})
        state = g2.evidence_freshness(tmp_path, self._current_head())
        assert state["ok"] is False
        assert state["reason"] == "NO_COMMIT_BINDING"

    def test_malformed_report_honest_failure(self, tmp_path):
        (tmp_path / "g2_harness_report.json").write_text("{not json", encoding="utf-8")
        state = g2.evidence_freshness(tmp_path, self._current_head())
        assert state["ok"] is False and state["reason"] == "PARSE_ERROR"

    def test_no_report_in_dir(self, tmp_path):
        state = g2.evidence_freshness(tmp_path, self._current_head())
        assert state["ok"] is False and state["reason"] == "NO_HARNESS_REPORT"

    def test_harness_emits_freshness_check_honestly_without_evidence_dir(self):
        report = g2.collect(None, full_battery=False)
        by_id = {c["id"]: c for c in report["checks"]}
        check = by_id["G2-C-v-fresh"]
        assert check["observed"] == "NO_EVIDENCE_DIR_SELECTED"
        assert check["satisfied"] is False


class TestImplementationBinding:
    """GOV-16: implementation-evidence binding (docs-only delta honesty)."""

    def _write_report(self, evidence_dir, name, payload):
        import json
        (evidence_dir / name).write_text(json.dumps(payload), encoding="utf-8")

    def _current_head(self):
        return g2.git("rev-parse", "HEAD")

    def test_fresh_at_head(self, tmp_path):
        head = self._current_head()
        self._write_report(tmp_path, "g2_harness_report.json", {"commit": head})
        state = g2.implementation_binding(tmp_path, head)
        assert state["ok"] is True and state["reason"] == "FRESH_AT_HEAD"
        assert state["tested_commit"] == head

    def test_docs_only_since(self, tmp_path):
        head = self._current_head()
        docs_only_parent = None
        parent = g2.git("rev-parse", "HEAD~1")
        out = g2.git("diff", "--name-only", parent, head)
        delta = [ln for ln in out.splitlines() if ln.strip()]
        if delta and all(g2._is_docs_only(p) for p in delta):
            docs_only_parent = parent
        if docs_only_parent is None:
            pytest.skip("no docs-only parent commit at this HEAD")
        self._write_report(tmp_path, "g2_harness_report.json",
                           {"commit": docs_only_parent})
        state = g2.implementation_binding(tmp_path, head)
        assert state["ok"] is True and state["reason"] == "DOCS_ONLY_SINCE"
        assert state["tested_commit"] == docs_only_parent

    def test_substantive_changes_since_rejected(self, tmp_path):
        head = self._current_head()
        parent = g2.git("rev-parse", "HEAD~1")
        out = g2.git("diff", "--name-only", parent, head)
        delta = [ln for ln in out.splitlines() if ln.strip()]
        if delta and all(g2._is_docs_only(p) for p in delta):
            pytest.skip("parent..HEAD delta is docs-only; use a synthetic case")
        self._write_report(tmp_path, "g2_harness_report.json", {"commit": parent})
        state = g2.implementation_binding(tmp_path, head)
        assert state["ok"] is False
        assert state["reason"] == "SUBSTANTIVE_CHANGES_SINCE"
        assert state["substantive"]

    def test_synthetic_substantive_classification(self):
        # pure classification unit: code/config/test paths are never docs-only
        assert g2._is_docs_only("backend/app/core/config.py") is False
        assert g2._is_docs_only("backend/tests/test_x.py") is False
        assert g2._is_docs_only("scripts/g2_acceptance_battery.py") is False
        assert g2._is_docs_only("docs/governance/PROJECT_EXECUTION_STATE.md") is True
        assert g2._is_docs_only("docs/active/SOME_RECORD.md") is True
        assert g2._is_docs_only("README.md") is True
        assert g2._is_docs_only("docs/evidence/raw/x.txt") is False

    def test_inherits_honest_states(self, tmp_path):
        head = self._current_head()
        # NO_HARNESS_REPORT
        state = g2.implementation_binding(tmp_path, head)
        assert state["ok"] is False and state["reason"] == "NO_HARNESS_REPORT"
        # NO_COMMIT_BINDING
        self._write_report(tmp_path, "g2_harness_report.json", {"verdict": "x"})
        state = g2.implementation_binding(tmp_path, head)
        assert state["ok"] is False and state["reason"] == "NO_COMMIT_BINDING"

    def test_harness_emits_impl_check_honestly_without_evidence_dir(self):
        report = g2.collect(None, full_battery=False)
        by_id = {c["id"]: c for c in report["checks"]}
        check = by_id["G2-C-v-impl"]
        assert check["observed"].startswith("NO_EVIDENCE_DIR_SELECTED")
        assert check["satisfied"] is False


class TestManifestExitCoverage:
    """Addendum A1 (G18-1): .exit sidecar coverage checks (D-19-1)."""

    def _write_manifest(self, bundle: Path, names: list[str]) -> None:
        import hashlib
        lines = []
        for n in names:
            digest = hashlib.sha256((bundle / n).read_bytes()).hexdigest()
            lines.append(f"{digest}  {n}")
        (bundle / "SHA256SUMS.manifest").write_text("\n".join(lines) + "\n")

    def test_compliant_bundle_all_exit_listed(self, tmp_path):
        (tmp_path / "cmd.txt").write_text("out\n")
        (tmp_path / "cmd.exit").write_text("0\n")
        self._write_manifest(tmp_path, ["cmd.txt", "cmd.exit"])
        result = g2.manifest_exit_coverage(tmp_path)
        assert result["ok"] is True
        assert result["reason"] == "COMPLIANT"
        assert result["covered"] == 1

    def test_mixed_bundle_exit_present_but_unlisted_rejected(self, tmp_path):
        (tmp_path / "cmd.txt").write_text("out\n")
        (tmp_path / "cmd.exit").write_text("0\n")
        (tmp_path / "other.exit").write_text("0\n")
        self._write_manifest(tmp_path, ["cmd.txt", "cmd.exit"])
        result = g2.manifest_exit_coverage(tmp_path)
        assert result["ok"] is False
        assert result["reason"] == "NONCOMPLIANT_MIXED"
        assert result["unlisted"] == ["other.exit"]

    def test_phantom_listed_exit_rejected(self, tmp_path):
        (tmp_path / "cmd.txt").write_text("out\n")
        # write the manifest by hand: the listed ghost.exit does not exist,
        # so the hash-helper cannot be used for that entry
        import hashlib
        digest = hashlib.sha256(b"out\n").hexdigest()
        (tmp_path / "SHA256SUMS.manifest").write_text(
            f"{digest}  cmd.txt\n"
            f"{'0' * 64}  ghost.exit\n")
        result = g2.manifest_exit_coverage(tmp_path)
        assert result["ok"] is False
        assert result["reason"] == "LISTED_EXIT_MISSING"
        assert result["phantom"] == ["ghost.exit"]

    def test_bundle_without_exit_files_is_vacuously_ok(self, tmp_path):
        (tmp_path / "report.json").write_text("{}\n")
        self._write_manifest(tmp_path, ["report.json"])
        result = g2.manifest_exit_coverage(tmp_path)
        assert result["ok"] is True
        assert result["reason"] == "NO_EXIT_FILES"

    def test_missing_manifest_reports_honestly(self, tmp_path):
        result = g2.manifest_exit_coverage(tmp_path)
        assert result["ok"] is False
        assert result["reason"] == "NO_MANIFEST"

    def test_gov19_era_bundle_is_compliant(self):
        # the real GOV-19 precommit bundle lists all 28 .exit sidecars
        bundle = REPO / ("docs/governance/evidence/raw/"
                         "2026-10-24_consolgov19_battery_precommit")
        if not bundle.is_dir():
            pytest.skip("GOV-19 bundle not present in this checkout")
        result = g2.manifest_exit_coverage(bundle)
        assert result["ok"] is True
        assert result["reason"] == "COMPLIANT"


class TestParsePytestSummary:
    """G18-2 fix (D-19-2): summary parsing tolerates ', N skipped'."""

    def test_full_modern_shape(self):
        parsed = g2.parse_pytest_summary(
            "658 passed, 1 skipped, 2 warnings in 78.14s (0:01:18)")
        assert parsed == {"passed": 658, "skipped": 1, "warnings": 2,
                          "seconds": 78.14}

    def test_legacy_shape_without_skips(self):
        parsed = g2.parse_pytest_summary("512 passed, 2 warnings in 78.24s")
        assert parsed["passed"] == 512
        assert parsed["skipped"] == 0
        assert parsed["warnings"] == 2
        assert parsed["seconds"] == 78.24

    def test_bare_passed_shape(self):
        parsed = g2.parse_pytest_summary("27 passed in 0.22s")
        assert parsed == {"passed": 27, "skipped": 0, "warnings": 0,
                          "seconds": 0.22}

    def test_no_match_reports_none(self):
        parsed = g2.parse_pytest_summary("no tests ran")
        assert parsed["passed"] is None


class TestVerdictContract:
    def test_harness_never_passes_g2(self):
        # structural guarantee: the verdict literal in collect() is NOT_PASSED
        source = HARNESS.read_text(encoding="utf-8")
        assert '"g2_verdict": "NOT_PASSED"' in source
        assert '"g2_verdict": "PASSED"' not in source

    def test_report_shape(self):
        report = g2.collect(None, full_battery=False)
        required = {"harness", "generated_utc", "commit", "parent", "branch",
                    "harness_green", "g2_verdict", "g2_verdict_reason", "checks"}
        assert required.issubset(report.keys())
        ids = [c["id"] for c in report["checks"]]
        for expected in ("G2-C-i", "G2-C-ii", "G2-C-iii-1", "G2-C-iii-2",
                         "G2-C-iii-3", "G2-C-iv", "G2-C-v", "G2-C-v-exit",
                         "G2-C-v-fresh", "G2-C-v-impl", "G2-E5", "G2-D-O1"):
            assert expected in ids
        assert report["g2_verdict"] == "NOT_PASSED"

    def test_machine_checkable_subset_holds_at_current_commit(self):
        report = g2.collect(None, full_battery=False)
        by_id = {c["id"]: c for c in report["checks"]}
        # these are the predicates that CAN hold without a reviewer/owner
        assert by_id["G2-C-iii-1"]["satisfied"] is True
        assert by_id["G2-C-iii-2"]["satisfied"] is True
        assert by_id["G2-C-iii-3"]["satisfied"] is True
        assert by_id["G2-C-iv"]["satisfied"] is True
        # procedure approval now holds via the delegated D-16-1 transcription
        assert by_id["G2-D-O1"]["satisfied"] is True
        # and these must NOT be claimed satisfied by the implementer
        assert by_id["G2-C-ii"]["satisfied"] is False
        assert by_id["G2-E5"]["satisfied"] is False


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__]))
