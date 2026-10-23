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

    def test_real_v02_file_block_is_empty(self):
        # the live canonical candidate must remain unapproved until D-O1
        text = (REPO / "docs/active/"
                "G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md"
                ).read_text(encoding="utf-8")
        assert g2.approval_block_filled(text) is False


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
                         "G2-C-iii-3", "G2-C-iv", "G2-C-v", "G2-E5",
                         "G2-D-O1"):
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
        # and these must NOT be claimed satisfied by the implementer
        assert by_id["G2-C-ii"]["satisfied"] is False
        assert by_id["G2-E5"]["satisfied"] is False
        assert by_id["G2-D-O1"]["satisfied"] is False


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__]))
