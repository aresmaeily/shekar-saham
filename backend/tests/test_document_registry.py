"""AI-6 append-only document version ledger — acceptance tests.

Sources: 02:161-170 (document version tracking; restatement handling),
02:194 (PIT source records; restatement evidence), 06 charter §3
(publication vs retrieval time; restatements create new versions),
D-AI-33 (version/restatement state), dependency matrix §AI-6. Synthetic
tests only — no network, no I/O, no clock reads.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.document_registry import (
    DocumentLedger,
    DocumentReRetrieval,
    DocumentVersion,
)

UTC = timezone.utc
T0 = datetime(2026, 10, 1, 8, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 2, 8, 0, 0, tzinfo=UTC)
T3 = datetime(2026, 10, 3, 8, 0, 0, tzinfo=UTC)


def _sha(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _version(doc_key: str = "doc-1", version_index: int = 1, **kw) -> DocumentVersion:
    base = dict(
        doc_key=doc_key,
        version_index=version_index,
        sha256_hex=_sha(f"{doc_key}:{version_index}"),
        source_ref=f"registry://source/{doc_key}/v{version_index}",
        published_at_utc=T0 if version_index == 1 else T2,
        retrieved_at_utc=T1 if version_index == 1 else T2,
    )
    base.update(kw)
    return DocumentVersion(**base)


# ---------------------------------------------------------------------------
# Registration discipline
# ---------------------------------------------------------------------------


def test_first_and_second_version_register_ok() -> None:
    ledger = DocumentLedger().register(_version(version_index=1))
    assert len(ledger.versions) == 1
    ledger2 = ledger.register(_version(version_index=2))
    assert len(ledger2.versions) == 2
    assert ledger2.latest("doc-1").version_index == 2
    # value-object discipline: the previous ledger is unchanged
    assert len(ledger.versions) == 1


def test_version_index_must_be_contiguous() -> None:
    with pytest.raises(ValueError, match="version_index_out_of_order"):
        DocumentLedger().register(_version(version_index=2))
    ledger = DocumentLedger().register(_version(version_index=1))
    with pytest.raises(ValueError, match="version_index_out_of_order"):
        ledger.register(_version(version_index=3))


def test_duplicate_sha256_refused() -> None:
    ledger = DocumentLedger().register(_version(version_index=1))
    duplicate = _version(version_index=2, sha256_hex=_sha("doc-1:1"))
    with pytest.raises(ValueError, match="duplicate_sha256_refused"):
        ledger.register(duplicate)


def test_restatement_must_supersede_existing_earlier_version() -> None:
    ledger = DocumentLedger().register(_version(version_index=1))
    with pytest.raises(ValueError, match="supersedes_unknown_version"):
        ledger.register(
            _version(version_index=2, is_restatement=True, supersedes_version_index=5)
        )


def test_restatement_schema_discipline() -> None:
    with pytest.raises(ValidationError, match="restatement_requires_supersedes_version"):
        _version(is_restatement=True)
    with pytest.raises(ValidationError, match="supersedes_requires_restatement"):
        _version(supersedes_version_index=1, is_restatement=False)


def test_honest_restatement_chain_ok() -> None:
    ledger = DocumentLedger().register(_version(version_index=1))
    restatement = _version(version_index=2, is_restatement=True, supersedes_version_index=1)
    ledger2 = ledger.register(restatement)
    assert ledger2.latest("doc-1").is_restatement is True
    assert ledger2.latest("doc-1").supersedes_version_index == 1


# ---------------------------------------------------------------------------
# Honest re-retrieval record class
# ---------------------------------------------------------------------------


def _re_retrieval(**kw) -> DocumentReRetrieval:
    base = dict(
        doc_key="doc-1",
        sha256_hex=_sha("doc-1:1"),
        retrieved_at_utc=T3,
        retrieval_ref="registry://source/doc-1/refetch",
    )
    base.update(kw)
    return DocumentReRetrieval(**base)


def test_duplicate_bytes_accepted_only_via_re_retrieval() -> None:
    ledger = DocumentLedger().register(_version(version_index=1))
    ledger2 = ledger.register_re_retrieval(_re_retrieval())
    # a retrieval FACT — no new version, history not rewritten
    assert len(ledger2.versions) == 1
    assert len(ledger2.re_retrievals) == 1


def test_re_retrieval_fail_closed_unknown_doc_key() -> None:
    with pytest.raises(ValueError, match="unknown_doc_key"):
        DocumentLedger().register_re_retrieval(_re_retrieval(doc_key="ghost"))


def test_re_retrieval_unknown_sha256_refused() -> None:
    ledger = DocumentLedger().register(_version(version_index=1))
    with pytest.raises(ValueError, match="re_retrieval_unknown_sha256"):
        ledger.register_re_retrieval(_re_retrieval(sha256_hex=_sha("unregistered")))


def test_re_retrieval_idempotent_and_conflicting() -> None:
    ledger = DocumentLedger().register(_version(version_index=1))
    once = ledger.register_re_retrieval(_re_retrieval())
    twice = once.register_re_retrieval(_re_retrieval())
    assert twice == once  # idempotent re-append, no duplicate record
    with pytest.raises(ValueError, match="re_retrieval_conflict"):
        once.register_re_retrieval(_re_retrieval(retrieval_ref="other://ref"))


# ---------------------------------------------------------------------------
# Point-in-time retrieval (by published_at_utc) — fail-closed
# ---------------------------------------------------------------------------


def test_versions_as_of_filters_by_publication_time() -> None:
    ledger = (
        DocumentLedger()
        .register(_version(version_index=1))  # published T0
        .register(_version(version_index=2))  # published T2
    )
    assert [v.version_index for v in ledger.versions_as_of("doc-1", T1)] == [1]
    # boundary is inclusive: a version published exactly at the cutoff counts
    assert [v.version_index for v in ledger.versions_as_of("doc-1", T2)] == [1, 2]
    assert [v.version_index for v in ledger.versions_as_of("doc-1", T3)] == [1, 2]


def test_unknown_doc_key_fail_closed() -> None:
    ledger = DocumentLedger().register(_version(version_index=1))
    with pytest.raises(ValueError, match="unknown_doc_key"):
        ledger.versions_as_of("ghost", T3)
    with pytest.raises(ValueError, match="unknown_doc_key"):
        ledger.latest("ghost")


def test_retrieval_time_does_not_drive_pit() -> None:
    # v2 published T2 but RETRIEVED earlier (T1): PIT uses publication time
    # (06 §3), so at T1 the v2 bytes are NOT yet available.
    ledger = DocumentLedger().register(_version(version_index=1)).register(
        _version(version_index=2, retrieved_at_utc=T1)
    )
    assert [v.version_index for v in ledger.versions_as_of("doc-1", T1)] == [1]


# ---------------------------------------------------------------------------
# Append-only structure and integrity
# ---------------------------------------------------------------------------


def test_ledger_is_append_only_by_construction() -> None:
    public_api = {
        name for name in dir(DocumentLedger) if not name.startswith("_")
    }
    forbidden = {"update", "delete", "purge", "remove", "rewrite", "expire", "retire", "drop"}
    assert public_api & forbidden == set()
    assert {
        "register",
        "register_re_retrieval",
        "versions_as_of",
        "latest",
        "integrity_digest",
    } <= public_api


def test_integrity_digest_deterministic_and_sensitive_to_appends() -> None:
    a = DocumentLedger().register(_version(version_index=1)).register(_version(version_index=2))
    b = DocumentLedger().register(_version(version_index=1)).register(_version(version_index=2))
    assert a.integrity_digest() == b.integrity_digest()
    with_re_retrieval = a.register_re_retrieval(_re_retrieval())
    assert with_re_retrieval.integrity_digest() != a.integrity_digest()
    assert DocumentLedger().integrity_digest() == DocumentLedger().integrity_digest()


def test_version_record_is_frozen_and_sha_validated() -> None:
    version = _version(version_index=1)
    with pytest.raises(ValidationError):
        version.version_index = 9  # type: ignore[misc]
    with pytest.raises(ValidationError, match="sha256_hex_must_be_64_hex"):
        _version(sha256_hex="not-hex")
