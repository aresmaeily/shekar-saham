"""Runtime G2 gate — fail-closed evaluation of the recorded formal gate state.

Closes the roadmap gap (GOV-32 Phase 3C). Canonical sources:

- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md line 37: "Governance G2 is
  verified. Runtime G2 is not yet implemented." — this module implements the
  runtime half.
- 02 lines 10–11 / 201–202: "G2 blocks all real-data AI-2 execution until
  formally passed. Design, contracts, paper/synthetic tests and dry-runs may
  proceed before G2." — the gate therefore blocks REAL-DATA execution only;
  synthetic/paper execution stays explicitly labeled as such and is never
  represented as LIVE.
- D-AI-26 (05:102–107): G2 blocks real-data AI-2 until independent validation
  + owner acceptance.
- Review procedure v1.0 (G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md,
  delegated approval D-16-1) T6: the G2 verdict is owner authority alone
  (04:72 Role 1 A; 05:148–150). This module NEVER flips a gate and NEVER
  executes anything: it only evaluates a recorded state and returns
  ``(allowed, refusal_tags)``.

Fail-closed contract (every GOV-32 §3C failure class denies execution):

- MISSING state (unreadable/absent state document)          -> ``gate_state_missing``
- MALFORMED state (unparseable JSON / schema violation)     -> ``gate_state_malformed``
- STALE state (convened review commit != running commit)    -> ``gate_state_stale``
- CONTRADICTORY state (verdict vs owner decision disagree)  -> ``gate_state_contradictory``
- UNVERIFIABLE evidence (owner decision document missing /
  hash mismatch / approval block incomplete)                -> ``owner_decision_unverifiable``

Additional deny tags: ``g2_gate_not_passed`` (the honest current verdict —
designed denial, not an error), ``owner_verdict_not_recorded``,
``procedure_not_approved``, ``reviewer_acknowledgement_missing``,
``coi_adjudication_missing``.

Anti-bypass and audit properties:

- The evaluator is a pure function of its arguments: no environment variable,
  retry, alternate route, or default configuration can flip the verdict. The
  caller supplies the state document contents; anything unreadable denies.
- Gate-state transitions are auditable: the state document is a tracked,
  committed file binding ``convened_review_commit`` (40-hex), the approved
  procedure identity/version, the reviewer acknowledgement (R-A1), the COI
  adjudication (D-O3), and an owner-decision document reference + SHA-256.
  A ``PASSED`` state without a verifying owner-decision document is denied.
- Not self-approving: the owner-decision document must exist on disk, hash-match
  the reference recorded in the state, and contain a complete owner approval
  block (``owner_decision_document_complete``). The implementation being
  evaluated cannot mint any of these by calling this module — it can only read
  what was committed.

State-document resolution (service layer): default path
``<repo root>/docs/active/G2_GATE_STATE.json`` (tracked), overridable via the
``G2_GATE_STATE_PATH`` setting for deployments. The path changes WHERE the
state is read from, never WHAT it says.

Domain discipline (same as ``ai2_governance.py``): frozen records,
deterministic, clock-free (timestamps passed in), no I/O, no network, no LLM.
All I/O (reading the state document and the owner-decision document) belongs
to the service layer and is fail-closed there.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc

G2GateVerdict = Literal["NOT_PASSED", "PASSED"]

#: The approved review procedure identity (delegated approval D-16-1,
#: CONSOL-GOV-16; recorded in OWNER_DELEGATED_DECISIONS_CONSOLGOV16_2026-10-23.md).
PROCEDURE_IDENTITY = "G2_REVIEW_PROCEDURE_PROPOSED_FINAL_v0.2_2026-10-22.md"
PROCEDURE_VERSION_APPROVED = "1.0"

OwnerDecisionLabel = Literal["G2_PASSED", "G2_NOT_PASSED"]


class G2OwnerDecision(BaseModel):
    """Owner-recorded acceptance decision bound to its decision document.

    T6 (procedure v1.0): the G2 verdict is recorded by the owner only. The
    decision here is a REFERENCE to that recorded act — document path plus
    exact SHA-256 — never a substitute for it. An inline decision without a
    verifying document is denied by :func:`evaluate_g2_gate`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    decision: OwnerDecisionLabel
    authority: str = Field(min_length=1, max_length=256)
    decided_at_utc: datetime
    decision_document: str = Field(min_length=1, max_length=512)
    decision_document_sha256: str = Field(min_length=64, max_length=64)

    @field_validator("decided_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("decision_document_sha256")
    @classmethod
    def _hex64(cls, v: str) -> str:
        if any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("decision_document_sha256_must_be_hex")
        return v.lower()


class G2GateState(BaseModel):
    """Immutable, machine-readable record of the formal G2 gate state.

    Stored as a tracked document (default ``docs/active/G2_GATE_STATE.json``).
    Every field is evidence-binding: a ``PASSED`` verdict is only evaluable
    when the whole chain (convened commit, procedure, reviewer acknowledgement,
    COI adjudication, owner decision document) verifies. Structural format is
    validated here; cross-record consistency is evaluated by
    :func:`evaluate_g2_gate` so defect classes stay distinguishable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    gate: Literal["G2"] = "G2"
    verdict: G2GateVerdict
    recorded_at_utc: datetime
    recorded_by: str = Field(min_length=1, max_length=256)
    procedure_identity: str = Field(min_length=1, max_length=256)
    procedure_version: str = Field(min_length=1, max_length=32)
    reviewer_identity: str | None = Field(default=None, max_length=256)
    reviewer_acknowledgement_utc: datetime | None = None
    coi_adjudication: str | None = Field(default=None, max_length=256)
    convened_review_commit: str = Field(min_length=40, max_length=40)
    evidence_harness_report_sha256: str = Field(min_length=64, max_length=64)
    owner_decision: G2OwnerDecision | None = None
    previous_state_sha256: str | None = Field(default=None, max_length=64)
    notes: str = ""

    @field_validator("recorded_at_utc", "reviewer_acknowledgement_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("convened_review_commit")
    @classmethod
    def _hex40(cls, v: str) -> str:
        if any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("convened_review_commit_must_be_hex40")
        return v.lower()

    @field_validator("evidence_harness_report_sha256", "previous_state_sha256")
    @classmethod
    def _hex64_opt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("sha256_fields_must_be_hex64")
        return v.lower()


def sha256_text(text: str) -> str:
    """Deterministic SHA-256 of document text (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def owner_decision_document_complete(text: str) -> bool:
    """True iff the owner-decision document carries a complete approval block.

    Required fields (the same approval-block style the review procedure's
    sign-off and the harness's ``approval_block_filled`` use — a field counts
    only when a non-underscore, non-whitespace value follows the colon):

    - ``G2 verdict:`` whose value is ``PASSED`` (the recorded verdict);
    - ``Approving authority:`` (the named owner authority);
    - ``Approval date (UTC):``;
    - ``Approval evidence / locus:`` (where the acceptance is recorded).

    A filled block alone is still not a pass: :func:`evaluate_g2_gate` also
    requires the exact document hash to be referenced by a PASSED gate state.
    """
    required = ("Approving authority", "Approval date (UTC)", "Approval evidence / locus")
    filled = 0
    verdict_passed = False
    for line in text.splitlines():
        for field in required:
            prefix = f"{field}:"
            if line.strip().startswith(prefix):
                value = line.strip()[len(prefix):].strip()
                if value and set(value) - {"_", " "}:
                    filled += 1
                break
        stripped = line.strip()
        if stripped.lower().startswith("g2 verdict:"):
            # Exact match only: a verdict value of "PASSED" (case-insensitive,
            # no extra words) — "PASSED_WITH_CAVEATS"-style prefixes are NOT a
            # recorded PASSED verdict (independent-review finding F-RV4).
            value = stripped[len("G2 verdict:"):].strip().upper()
            if value == "PASSED":
                verdict_passed = True
    return verdict_passed and filled == len(required)


def evaluate_g2_gate(
    state: G2GateState | None,
    *,
    current_commit: str | None,
    owner_decision_text: str | None = None,
    load_error: str | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Deterministic, fail-closed G2 gate evaluation.

    Returns ``(allowed, refusal_tags)`` and NEVER executes anything, never
    mutates state, and never flips a gate. ``current_commit`` is the commit of
    the running source (unknown/empty at runtimes that cannot bind it).
    ``load_error`` is the loader's failure tag when the state document could
    not be read or parsed (``gate_state_missing`` / ``gate_state_malformed``);
    it is surfaced verbatim so the denial names the actual failure class. All
    applicable refusal tags are returned in a stable order for audit records.

    Denial classes (GOV-32 §3C): missing, malformed, stale, contradictory,
    unverifiable; plus the designed honest denial ``g2_gate_not_passed`` while
    the formal verdict is NOT_PASSED.
    """
    if state is None:
        return (False, (load_error or "gate_state_missing",))

    if state.verdict != "PASSED":
        # Honest designed denial — the formal verdict is NOT_PASSED, so
        # real-data AI-2 execution is blocked (02:201-202; D-AI-26). No
        # further tags: the state itself is not defective.
        return (False, ("g2_gate_not_passed",))

    refusals: list[str] = []

    # Contradiction: a PASSED verdict requires a recorded owner decision that
    # agrees; anything else is internally contradictory.
    if state.owner_decision is None:
        refusals.append("owner_verdict_not_recorded")
    elif state.owner_decision.decision != "G2_PASSED":
        refusals.append("gate_state_contradictory")

    # Staleness: the convened review must bind the running commit.
    if not current_commit or state.convened_review_commit != current_commit.strip().lower():
        refusals.append("gate_state_stale")

    # Procedure: only the approved v1.0 identity is acceptable.
    if (
        state.procedure_identity != PROCEDURE_IDENTITY
        or state.procedure_version != PROCEDURE_VERSION_APPROVED
    ):
        refusals.append("procedure_not_approved")

    # Reviewer acknowledgement (E5/R-A1) and COI adjudication (D-O3).
    if not state.reviewer_identity or state.reviewer_acknowledgement_utc is None:
        refusals.append("reviewer_acknowledgement_missing")
    if not state.coi_adjudication:
        refusals.append("coi_adjudication_missing")

    # Owner-decision document must verify: exists, hash-matches the reference,
    # and carries a complete owner approval block.
    if state.owner_decision is not None:
        if owner_decision_text is None:
            refusals.append("owner_decision_unverifiable")
        else:
            actual = sha256_text(owner_decision_text)
            if actual != state.owner_decision.decision_document_sha256:
                refusals.append("owner_decision_unverifiable")
            elif not owner_decision_document_complete(owner_decision_text):
                refusals.append("owner_decision_unverifiable")

    return (not refusals, tuple(refusals))


ExecutionMode = Literal["LIVE", "SYNTHETIC_OR_PAPER"]


def execution_mode(live_verified: bool) -> ExecutionMode:
    """Explicit execution-mode label (GOV-32 §3C).

    ``LIVE`` only when independently verified live data is in use; every other
    case is explicitly labeled ``SYNTHETIC_OR_PAPER`` and must never be
    represented as LIVE.
    """
    return "LIVE" if live_verified else "SYNTHETIC_OR_PAPER"
