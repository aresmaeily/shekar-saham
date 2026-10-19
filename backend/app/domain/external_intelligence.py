"""AI-6 External Intelligence untrusted-content boundary contract layer.

Corpus loci (2026-10-02 amendment corpus, byte-verified import):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 97-100: "AI-6 --- External
  Intelligence: Only after untrusted-content boundaries, provenance,
  verification, injection controls and Two-Key Rule."
- 02 lines 161-170: required AI-6/P8 capabilities; "All external content is
  untrusted input. Prompt-injection and content-instruction isolation,
  provenance, tool boundaries and the Two-Key Rule remain mandatory. AI must
  never invent missing financial values or silently reconcile contradictory
  sources."
- 02 line 195-197: acceptance evidence for external/fundamental intelligence
  (point-in-time source records, cross-check/conflict examples, citation
  completeness, restatement handling, missing-source behavior).
- 02 line 201-203: G2 preserved; pre-G2 class = bounded design, schema work,
  source-registry design, synthetic/paper tests, safe dry-run work;
  "source permissions, provenance, untrusted-content isolation and Two-Key
  Rule must be implemented and validated".
- 03_AI_GOVERNANCE_BOUNDARIES lines 19-25: AI may not "treat untrusted
  content as executable".
- 03 lines 73-76: "External intelligence — Untrusted by default. Before
  AI-6: provenance, source verification, injection defense, tool boundary,
  Two-Key Rule and human escalation."
- 03 lines 33-40: run provenance; missing required provenance blocks
  governed acceptance. Lines 85-88: secrets are never opened, copied,
  displayed or hashed.
- 03 lines 113-114: external intelligence remains untrusted by default and
  requires provenance, verification, injection defense, approved tools and
  Two-Key Rule.
- D-AI-29 (05 register lines 123-128): DEFERRED BY GATE — requires
  untrusted-content boundary, provenance, verification and Two-Key Rule.
  This module delivers the boundary-set CONTRACTS; it does not flip the
  gate and does not claim the gate open.
- D-AI-33: facts keep source/publication/period/units/version/trust/conflict;
  missing or contradictory data surfaced, not invented or silently
  reconciled. D-AI-38: coverage/freshness honesty. D-AI-40: all gates remain
  binding. D-AI-41: capability is not implementation evidence.
- 06_PRODUCT_CAPABILITY_CHARTER lines 88-90: "External documents and web
  content are untrusted data, never executable instructions. Use approved
  tools only; preserve provenance and source references; apply
  prompt-injection isolation and the Two-Key Rule where required."
- 06 §3 (lines 20-38): source hierarchy and reconciliation rules 1-7.
- 02_PRODUCT_AI_MULTI_AGENT_ARCHITECTURE line 120: "External source content
  is ingested as untrusted data. Extraction is separated from
  interpretation. ... AI reasoning receives evidence references, not
  authority to change source facts." Line 126: "Source ingestion may not
  bypass existing external-intelligence gates, Two-Key Rule,
  untrusted-content isolation, provenance, or human approval."
- AI4_AI7_P343_DEPENDENCY_MATRIX.md lines 51-69: authorized-now class =
  "untrusted-content boundary + injection-isolation CONTRACT design
  (pre-G2 class); source-class admission schema extension". BLOCKED: any
  network ingestion, any live crawl, any provider contact. Owner decisions
  needed: source classes to admit first; Two-Key Rule operational
  parameters; credentials.

Contract/domain only: frozen records, deterministic, clock-free (every
timestamp is passed in as an argument), no I/O, no network, no LLM, no
scheduler, no scraping. The ingestion/crawl EXECUTION runtime does not
exist and is blocked work (dependency matrix; D-AI-29 still DEFERRED BY
GATE); this module defines the trust-boundary/injection-isolation
CONTRACTS only (pre-G2 authorized class).

Structural boundary guarantees (02:97-100; 02:170; 03:19-25,73-76; 06:88-90):
- the content trust label is structurally locked to UNTRUSTED — no upgrade
  path exists in this module and scan results never raise trust;
- embedded instruction candidates carry ``executable: Literal[False]`` —
  content-borne instructions are non-executable by construction;
- the flow vocabulary contains TOOL_EXECUTION / PRODUCTION_MUTATION /
  AUTONOMOUS_ACTION only as structurally-forbidden members;
- instruction-conflict resolution is structurally locked to
  governed-instruction precedence with quarantine of the content
  instruction — compliance with content-borne instructions is
  unrepresentable;
- the quarantine ledger is append-only (no update/delete/invalidate path);
- release from quarantine requires a named human decision, and a two-key
  authorization when the source-class controls require it;
- source-class controls are structurally locked to
  ``admission_state=PENDING_OWNER_DECISION`` — engineering cannot admit a
  source class;
- this module contains NO fetch/crawl/network function and no credential
  field (03:85-88).

Reuse (no duplication): evidence.py EvidenceItem/EvidenceConflict carry
filing-time provenance and explicit conflicts (the "never invent / never
silently reconcile" rule is served by reuse, not reimplementation);
source_registry.py SourceDescriptor/SourceTier/SourceRegistry/CoverageReport
carry source identity and coverage honesty; run_governance.py
RunContext/RunProvenance/missing_required_provenance carry run identity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import SCHEMA_VERSION, ensure_utc
from app.domain.run_governance import (
    RunContext,
    RunProvenance,
    assert_autonomy_permitted,
    missing_required_provenance,
)
from app.domain.source_registry import SourceRegistry, SourceTier

# ---------------------------------------------------------------------------
# Closed vocabularies (02:97-100; 02:170; 03:19-25,73-76; 06:88-90)
# ---------------------------------------------------------------------------

#: The only trust label external content can carry (02:170 "All external
#: content is untrusted input"; 03:75 "Untrusted by default"). A TRUSTED
#: label is unrepresentable by construction.
TrustLabel = Literal["UNTRUSTED"]

#: Content kinds exactly as the corpus names them for AI-6 extraction
#: (02:164: "financial statements, notes, auditor opinions, guidance,
#: material events and company disclosures"; 02:162 official filings).
#: OTHER_DECLARED covers corpus source classes without a dedicated member;
#: unknown kinds are unrepresentable.
ContentKind = Literal[
    "FILING",
    "FINANCIAL_STATEMENT",
    "NOTE",
    "AUDITOR_OPINION",
    "GUIDANCE",
    "MATERIAL_EVENT",
    "COMPANY_DISCLOSURE",
    "OTHER_DECLARED",
]

#: Trust-boundary flows (03:73-76 tool boundary; 02:170 "tool boundaries";
#: 03:19-25 untrusted content is not executable; 02_PRODUCT:120 extraction
#: separated from interpretation; 02_PRODUCT:126 ingestion may not bypass).
#: The three execution-side flows exist in the vocabulary ONLY as members
#: the gate refuses — they can never be allowed.
TrustBoundaryFlow = Literal[
    "EXTRACTION_DETERMINISTIC",
    "EVIDENCE_FILING",
    "QUARANTINE",
    "ADVISORY_INTERPRETATION",
    "TOOL_EXECUTION",
    "PRODUCTION_MUTATION",
    "AUTONOMOUS_ACTION",
]

_ALLOWED_FLOWS: frozenset[str] = frozenset(
    {
        "EXTRACTION_DETERMINISTIC",
        "EVIDENCE_FILING",
        "QUARANTINE",
        "ADVISORY_INTERPRETATION",
    }
)

_FORBIDDEN_FLOWS: frozenset[str] = frozenset(
    {
        "TOOL_EXECUTION",
        "PRODUCTION_MUTATION",
        "AUTONOMOUS_ACTION",
    }
)

#: Deterministic injection-finding taxonomy (02:170 "Prompt-injection and
#: content-instruction isolation"; 03:75 "injection defense"). The SCAN that
#: produces findings is a caller-side deterministic scanner; this module
#: records and gates on the findings — it never runs content analysis.
InjectionFindingKind = Literal[
    "DIRECT_INSTRUCTION",
    "INSTRUCTION_CONFLICT",
    "TOOL_INVOCATION_ATTEMPT",
    "PRIVILEGE_ESCALATION",
    "OBFUSCATED_INSTRUCTION",
    "NONE_DETECTED",
]

_FINDING_KINDS: frozenset[str] = frozenset(
    {
        "DIRECT_INSTRUCTION",
        "INSTRUCTION_CONFLICT",
        "TOOL_INVOCATION_ATTEMPT",
        "PRIVILEGE_ESCALATION",
        "OBFUSCATED_INSTRUCTION",
    }
)

#: Quarantine reasons (closed; corpus/directive-grounded: injection findings,
#: instruction conflicts, malformed inputs, missing provenance 03:40,
#: non-admitted sources 02_PRODUCT:126).
QuarantineReason = Literal[
    "INJECTION_FINDING",
    "INSTRUCTION_CONFLICT",
    "MALFORMED_CONTENT",
    "PROVENANCE_INCOMPLETE",
    "SOURCE_NOT_ADMITTED",
]

#: Structural instruction-conflict resolution (02:170 content-instruction
#: isolation; 06:89 untrusted data is never executable): governed
#: instructions always take precedence; the content-borne instruction is
#: quarantined. Compliance is not an expressible outcome.
InstructionConflictResolution = Literal["GOVERNED_INSTRUCTION_PRECEDENCE"]
ContentInstructionDisposition = Literal["QUARANTINED"]

#: Two-key structural vocabulary (06:90 "the Two-Key Rule where required";
#: D-AI-29; 02:170). Operational parameters (which action classes require
#: it, custodians, revocation) are owner decisions recorded UNRESOLVED in
#: AI6_SCOPE_DERIVATION.md §7 — no parameter is invented here.
KeyRole = Literal["OWNER", "AUTHORIZED_REVIEWER", "GOVERNOR"]

QuarantineAction = Literal["QUARANTINE", "RELEASE", "DISCARD"]

#: Source-class admission schema state (dependency matrix: "source-class
#: admission schema extension"; owner decisions needed: source classes to
#: admit first). Structurally locked: engineering cannot admit.
SourceClassAdmissionState = Literal["PENDING_OWNER_DECISION"]


def assert_boundary_allowed(flow: TrustBoundaryFlow) -> None:
    """Deterministic trust-boundary gate (03:73-76; 02:170; 03:19-25).

    Raises ``ValueError`` for any execution-side flow (tool execution,
    production mutation, autonomous action); returns ``None`` for the four
    content-side flows. Unknown flows are unrepresentable (closed Literal).
    """
    if flow in _FORBIDDEN_FLOWS:
        raise ValueError(f"trust_boundary_flow_forbidden:{flow}")
    if flow not in _ALLOWED_FLOWS:
        raise ValueError("trust_boundary_flow_unknown")
    return None


# ---------------------------------------------------------------------------
# Untrusted content envelope (R1/R2: 02:170; 03:75; 06:89; 02_PRODUCT:120)
# ---------------------------------------------------------------------------


class UntrustedContentEnvelope(BaseModel):
    """Immutable provenance envelope for one piece of external content.

    Structural guarantees:
    - ``trust_label`` is locked to UNTRUSTED (02:170; 03:75) — the module
      has no trusted-content constructor;
    - ``content_sha256`` is mandatory hex-64 (provenance preservation,
      02:170; 03:33-40);
    - ``source_tier`` reuses the canonical SourceTier vocabulary — no new
      source taxonomy;
    - the envelope binds the governed run that ingested the content
      (02:198);
    - there is no credential field (03:85-88).
    """

    model_config = ConfigDict(frozen=True)

    content_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1, max_length=128)
    source_tier: SourceTier
    content_kind: ContentKind
    content_sha256: str
    retrieval_time_utc: datetime
    trust_label: TrustLabel = "UNTRUSTED"
    run_id: str = Field(min_length=1, max_length=128)
    notes: str = ""

    @field_validator("retrieval_time_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("content_sha256")
    @classmethod
    def _sha256_shape(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("content_sha256_must_be_64_hex")
        return v.lower()


# ---------------------------------------------------------------------------
# Content-instruction separation (R3: 02:170; 03:19-25; 06:89)
# ---------------------------------------------------------------------------


class EmbeddedInstructionCandidate(BaseModel):
    """One content-borne instruction candidate found during segmentation.

    ``executable`` is structurally ``False``: content-borne instructions are
    never executable (03:19-25; 06:89). The excerpt is bounded; candidates
    are recorded, never followed.
    """

    model_config = ConfigDict(frozen=True)

    instruction_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    content_id: str = Field(min_length=1, max_length=128)
    excerpt: str = Field(min_length=1, max_length=2000)
    executable: Literal[False] = False
    notes: str = ""


class ContentSegmentation(BaseModel):
    """Declaration that instructions were separated from untrusted payload.

    The payload itself is exchanged by reference (the envelope hash), never
    embedded here (D-AI-23 artifact-first exchange). Instruction candidates
    must belong to the same content and have distinct ids.
    """

    model_config = ConfigDict(frozen=True)

    segmentation_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    content_id: str = Field(min_length=1, max_length=128)
    payload_segment_count: int = Field(ge=0)
    instruction_candidates: tuple[EmbeddedInstructionCandidate, ...] = ()
    separated_at_utc: datetime
    notes: str = ""

    @field_validator("separated_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _candidate_discipline(self) -> "ContentSegmentation":
        ids = [c.instruction_id for c in self.instruction_candidates]
        if len(set(ids)) != len(ids):
            raise ValueError("instruction_candidate_ids_duplicates")
        for c in self.instruction_candidates:
            if c.content_id != self.content_id:
                raise ValueError("instruction_candidate_content_mismatch")
        return self


# ---------------------------------------------------------------------------
# Injection scan records (R5: 02:97-100; 02:170; 03:75)
# ---------------------------------------------------------------------------


class InjectionScanRecord(BaseModel):
    """Recorded result of one deterministic injection scan.

    The scan itself is executed by a caller-side deterministic scanner; this
    record is the auditable evidence the gates consume. ``NONE_DETECTED``
    must appear alone and never raises the content's trust (03:75 untrusted
    by default; R1).
    """

    model_config = ConfigDict(frozen=True)

    scan_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    content_id: str = Field(min_length=1, max_length=128)
    scanner_id: str = Field(min_length=1, max_length=128)
    policy_version: str = Field(min_length=1)
    findings: tuple[InjectionFindingKind, ...] = Field(min_length=1)
    scanned_at_utc: datetime
    notes: str = ""

    @field_validator("scanned_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @field_validator("findings")
    @classmethod
    def _findings_discipline(
        cls, v: tuple[InjectionFindingKind, ...]
    ) -> tuple[InjectionFindingKind, ...]:
        if len(set(v)) != len(v):
            raise ValueError("injection_findings_duplicates")
        if "NONE_DETECTED" in v and len(v) > 1:
            raise ValueError("none_detected_must_stand_alone")
        return v

    @property
    def has_findings(self) -> bool:
        return bool(set(self.findings) & _FINDING_KINDS)


# ---------------------------------------------------------------------------
# Instruction-conflict record (R6: 02:170; 06:89; directive R2)
# ---------------------------------------------------------------------------


class InstructionConflictRecord(BaseModel):
    """A content-borne instruction that conflicts with governed instructions.

    The resolution is structurally locked: governed instructions take
    precedence and the content instruction is quarantined. An outcome in
    which the content instruction is followed is unrepresentable.
    """

    model_config = ConfigDict(frozen=True)

    conflict_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    content_id: str = Field(min_length=1, max_length=128)
    instruction_id: str = Field(min_length=1, max_length=128)
    governed_instruction_ref: str = Field(min_length=1, max_length=256)
    resolution: InstructionConflictResolution = "GOVERNED_INSTRUCTION_PRECEDENCE"
    content_instruction_disposition: ContentInstructionDisposition = "QUARANTINED"
    declared_at_utc: datetime
    notes: str = ""

    @field_validator("declared_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


# ---------------------------------------------------------------------------
# Quarantine ledger (R7: 03:76 human escalation; directive R2)
# ---------------------------------------------------------------------------


class QuarantineEvent(BaseModel):
    """One append-only quarantine-ledger event for one content id.

    QUARANTINE events carry the reason; RELEASE/DISCARD events carry the
    named human decision (03:76 human escalation). Optional
    ``instruction_id`` scopes the event to one embedded instruction
    candidate instead of the whole content.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    action: QuarantineAction
    content_id: str = Field(min_length=1, max_length=128)
    instruction_id: str | None = None
    reason: QuarantineReason | None = None
    detail_ref: str | None = None
    decided_by: str | None = None
    decision_ref: str | None = None
    event_at_utc: datetime
    notes: str = ""

    @field_validator("event_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _event_discipline(self) -> "QuarantineEvent":
        if self.action == "QUARANTINE":
            if self.reason is None:
                raise ValueError("quarantine_event_requires_reason")
            if self.decided_by is not None or self.decision_ref is not None:
                raise ValueError("quarantine_event_carry_no_release_decision")
        else:
            if self.reason is not None:
                raise ValueError("release_event_cannot_declare_quarantine_reason")
            if not self.decided_by or not self.decision_ref:
                raise ValueError("release_requires_named_human_decision")
        return self


class QuarantineLedger:
    """Append-only quarantine ledger (no update/delete/invalidate path).

    Deterministic rules:
    - a QUARANTINE event for a content (or content+instruction) that is
      already actively quarantined at the same scope is refused;
    - RELEASE/DISCARD must reference an actively quarantined scope;
    - history is never rewritten: ``with_event`` returns a new ledger.
    """

    def __init__(self, events: tuple[QuarantineEvent, ...] = ()) -> None:
        self._events: tuple[QuarantineEvent, ...] = events

    @property
    def events(self) -> tuple[QuarantineEvent, ...]:
        return self._events

    def active_scope(self, content_id: str, instruction_id: str | None) -> str | None:
        """Return the active action at a scope, or ``None`` when free.

        Content-level quarantine covers instruction-level scopes; an
        instruction-level quarantine does not cover the whole content.
        """
        state: str | None = None
        for e in self._events:
            if e.content_id != content_id:
                continue
            if e.instruction_id is None:
                state = e.action  # content-level event governs the content
            elif e.instruction_id == instruction_id and state != "QUARANTINE":
                state = e.action
        return state

    def actively_quarantined(self, content_id: str, instruction_id: str | None = None) -> bool:
        return self.active_scope(content_id, instruction_id) == "QUARANTINE"

    def with_event(self, event: QuarantineEvent) -> "QuarantineLedger":
        state = self.active_scope(event.content_id, event.instruction_id)
        if event.action == "QUARANTINE":
            if state == "QUARANTINE":
                raise ValueError("scope_already_quarantined")
        else:
            if state != "QUARANTINE":
                raise ValueError("release_requires_active_quarantine")
        return QuarantineLedger(self._events + (event,))


# ---------------------------------------------------------------------------
# Two-Key Rule structural mechanism (R8: 02:100,170; 03:76,114; D-AI-29; 06:90)
# ---------------------------------------------------------------------------


class KeyGrant(BaseModel):
    """One authorization key grant: a named human, a role, a time, a ref."""

    model_config = ConfigDict(frozen=True)

    authorized_by: str = Field(min_length=1, max_length=128)
    role: KeyRole
    authorized_at_utc: datetime
    reference: str = Field(min_length=1, max_length=256)

    @field_validator("authorized_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


class TwoKeyAuthorization(BaseModel):
    """Two DISTINCT human authorizations for one governed action.

    Structural discipline (06:90; D-AI-29): both keys are mandatory, the
    authorizer identities must differ, and the authorized action reference
    is bound at construction. Operational parameters (when the rule applies,
    custodians) remain owner decisions — this record only makes a compliant
    authorization EXPRESSIBLE and a non-compliant one UNREPRESENTABLE.
    """

    model_config = ConfigDict(frozen=True)

    authorization_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    action_ref: str = Field(min_length=1, max_length=256)
    policy_version: str = Field(min_length=1)
    key_one: KeyGrant
    key_two: KeyGrant
    notes: str = ""

    @model_validator(mode="after")
    def _distinct_authorizers(self) -> "TwoKeyAuthorization":
        if self.key_one.authorized_by == self.key_two.authorized_by:
            raise ValueError("two_key_authorizers_must_be_distinct")
        return self


# ---------------------------------------------------------------------------
# Source verification (R9: 02:97-100; 03:75; D-AI-29)
# ---------------------------------------------------------------------------


class SourceVerificationRecord(BaseModel):
    """Recorded source-verification evidence (03:75 "source verification").

    The verification EXECUTION is operational work (network; blocked). This
    contract records that a verification happened, by whom, how, and when —
    the evidence_filing_gate consumes it before VERIFIED trust can stand.
    """

    model_config = ConfigDict(frozen=True)

    verification_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1, max_length=128)
    verified_by: str = Field(min_length=1, max_length=128)
    method: str = Field(min_length=1, max_length=256)
    verified_at_utc: datetime
    notes: str = ""

    @field_validator("verified_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)


# ---------------------------------------------------------------------------
# Source-class admission schema extension (R10: dependency matrix)
# ---------------------------------------------------------------------------


class SourceClassControls(BaseModel):
    """Mandatory control declarations for one source class (AI-6 schema).

    ``admission_state`` is structurally ``PENDING_OWNER_DECISION``:
    engineering declares the control schema; admitting actual source
    classes is an owner decision (dependency matrix "Owner decisions
    needed: source classes to admit first"). ``requires_two_key`` encodes
    "the Two-Key Rule where required" (06:90) at schema level; the
    operational parameters remain owner decisions.
    """

    model_config = ConfigDict(frozen=True)

    controls_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    source_tier: SourceTier
    requires_verification: bool
    requires_injection_scan: bool
    requires_two_key: bool
    admission_state: SourceClassAdmissionState = "PENDING_OWNER_DECISION"
    notes: str = ""

    @model_validator(mode="after")
    def _human_escalation_floor(self) -> "SourceClassControls":
        if not self.requires_injection_scan:
            raise ValueError("injection_scan_cannot_be_waived")
        return self


# ---------------------------------------------------------------------------
# Advisory interpretation request (R11: 02_PRODUCT:120)
# ---------------------------------------------------------------------------


class AdvisoryInterpretationRequest(BaseModel):
    """A request for AI reasoning over EXTERNAL evidence references only.

    "AI reasoning receives evidence references, not authority to change
    source facts" (02_PRODUCT:120). The request carries evidence ids and
    content ids; it has NO write-authority field of any kind — the module
    contains no API through which interpretation could mutate source facts
    (structural absence, test-enforced). Citation completeness (02:196) is
    enforced: at least one evidence id is mandatory.
    """

    model_config = ConfigDict(frozen=True)

    request_id: str = Field(min_length=1, max_length=128)
    schema_version: str = SCHEMA_VERSION
    content_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    run_id: str = Field(min_length=1, max_length=128)
    notes: str = ""

    @field_validator("content_ids", "evidence_ids")
    @classmethod
    def _distinct(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("request_reference_ids_duplicates")
        return v


# ---------------------------------------------------------------------------
# Gate functions (R4/R5/R9/R14/R15: 02:97-100; 02:170; 03:33-40,73-76,90-94)
# ---------------------------------------------------------------------------
#
# Every gate is deterministic and clock-free, returns refusal codes in a
# FIXED order (empty tuple = no blocking reason), and mutates nothing.


def external_intake_gate(
    envelope: UntrustedContentEnvelope,
    registry: SourceRegistry,
    segmentation: ContentSegmentation,
    scan: InjectionScanRecord,
    controls_by_tier: dict[str, SourceClassControls],
    context: RunContext,
    provenance: RunProvenance,
    *,
    verification: SourceVerificationRecord | None = None,
    autonomy_ceiling: str = "L2",
) -> tuple[str, ...]:
    """Pre-condition gate for admitting external content into governed flows.

    Encodes 02:97-100 "Only after untrusted-content boundaries, provenance,
    verification, injection controls and Two-Key Rule" at the intake
    boundary plus 02_PRODUCT:126 ("ingestion may not bypass existing
    gates"). Refusal codes, fixed order:
    ``intake_run_id_mismatch``, ``scan_content_id_mismatch``,
    ``segmentation_content_id_mismatch``, ``source_not_registered``,
    ``source_class_controls_missing``, ``source_verification_required``,
    ``provenance_incomplete:<fields>``, ``autonomy_level_exceeds_ceiling``,
    ``injection_findings_require_quarantine``.
    """
    codes: list[str] = []
    if envelope.run_id != context.run_id:
        codes.append("intake_run_id_mismatch")
    if scan.content_id != envelope.content_id:
        codes.append("scan_content_id_mismatch")
    if segmentation.content_id != envelope.content_id:
        codes.append("segmentation_content_id_mismatch")
    descriptor = registry.get(envelope.source_id)
    if descriptor is None:
        codes.append("source_not_registered")
    controls = controls_by_tier.get(envelope.source_tier)
    if controls is None:
        codes.append("source_class_controls_missing")
    elif controls.requires_verification and verification is None:
        codes.append("source_verification_required")
    elif (
        controls is not None
        and verification is not None
        and verification.source_id != envelope.source_id
    ):
        codes.append("verification_source_mismatch")
    missing = missing_required_provenance(
        context, provenance, additionally_required=("dataset_version",)
    )
    if missing:
        codes.append(f"provenance_incomplete:{'+'.join(missing)}")
    try:
        assert_autonomy_permitted(context, autonomy_ceiling)  # type: ignore[arg-type]
    except ValueError:
        codes.append("autonomy_level_exceeds_ceiling")
    if scan.has_findings:
        codes.append("injection_findings_require_quarantine")
    return tuple(codes)


def evidence_filing_gate(
    envelope: UntrustedContentEnvelope,
    registry: SourceRegistry,
    scan: InjectionScanRecord,
    evidence_item: object,
    ledger: QuarantineLedger,
    *,
    verification: SourceVerificationRecord | None = None,
) -> tuple[str, ...]:
    """Gate for filing external content as canonical evidence.

    Provenance preservation is enforced against the canonical EvidenceItem:
    source and document hash must match the envelope (02:170 provenance;
    03:33-40). VERIFIED trust requires a source-verification record
    (03:75). Content with unhandled injection findings or an active
    quarantine cannot be filed (03:76; 06:90).

    ``evidence_item`` is typed loosely on purpose: this module consumes the
    canonical ``evidence.EvidenceItem`` (REUSE, no new schema) and must not
    import it into a type cycle; the gate duck-types the two fields it
    needs and refuses malformed inputs deterministically.
    """
    codes: list[str] = []
    try:
        item_source = getattr(evidence_item, "source_id")
        item_hash = getattr(evidence_item, "document_sha256")
        item_trust = getattr(evidence_item, "trust_status")
    except AttributeError:
        return ("evidence_item_malformed",)
    if not isinstance(item_source, str) or not isinstance(item_trust, str):
        return ("evidence_item_malformed",)
    if item_source != envelope.source_id:
        codes.append("evidence_source_mismatch")
    if item_hash is None or item_hash.lower() != envelope.content_sha256:
        codes.append("evidence_hash_mismatch")
    if registry.get(envelope.source_id) is None:
        codes.append("source_not_registered")
    if item_trust == "VERIFIED" and verification is None:
        codes.append("verified_trust_requires_source_verification")
    if (
        verification is not None
        and item_trust == "VERIFIED"
        and verification.source_id != envelope.source_id
    ):
        codes.append("verification_source_mismatch")
    if scan.has_findings and not ledger.actively_quarantined(envelope.content_id):
        codes.append("filing_blocked_unhandled_injection_findings")
    if ledger.actively_quarantined(envelope.content_id) and not scan.has_findings:
        codes.append("filing_blocked_active_quarantine")
    return tuple(codes)


def injection_response_gate(scan: InjectionScanRecord, ledger: QuarantineLedger) -> tuple[str, ...]:
    """Deterministic injection-response discipline (03:75-76; 06:90).

    Any non-NONE finding must be covered by an active QUARANTINE event
    (safe refusal + quarantine; human escalation happens through the
    ledger's named-human release). A clean scan does NOT upgrade trust —
    the content stays UNTRUSTED (03:75); no code path here raises trust.
    """
    if not scan.has_findings:
        return ()
    if ledger.actively_quarantined(scan.content_id):
        return ()
    return ("quarantine_required_for_injection_findings",)


def quarantine_release_gate(
    event: QuarantineEvent,
    controls: SourceClassControls,
    two_key: TwoKeyAuthorization | None,
) -> tuple[str, ...]:
    """Gate for RELEASE/DISCARD of quarantined content (03:76; 06:90).

    The event validator already enforces a named human decision. When the
    source-class controls require the Two-Key Rule, a compliant
    TwoKeyAuthorization bound to the same content release is mandatory.
    """
    if event.action == "QUARANTINE":
        return ("release_gate_requires_release_or_discard_event",)
    codes: list[str] = []
    if controls.requires_two_key and two_key is None:
        codes.append("two_key_authorization_required")
    elif two_key is not None and two_key.action_ref != event.event_id:
        codes.append("two_key_action_ref_mismatch")
    return tuple(codes)


def advisory_interpretation_gate(
    request: AdvisoryInterpretationRequest,
    registry: SourceRegistry,
    envelopes_by_id: dict[str, UntrustedContentEnvelope],
    ledger: QuarantineLedger,
    context: RunContext,
    provenance: RunProvenance,
) -> tuple[str, ...]:
    """Gate for advisory interpretation over external evidence (02_PRODUCT:120).

    Deterministic rules: run identity binding; required provenance complete
    (03:33-40); every referenced content must be a known envelope and NOT
    actively quarantined (06:90 quarantine honesty). The request itself is
    write-authority-free by construction (R11).
    """
    codes: list[str] = []
    if request.run_id != context.run_id:
        codes.append("interpretation_run_id_mismatch")
    missing = missing_required_provenance(
        context, provenance, additionally_required=("dataset_version",)
    )
    if missing:
        codes.append(f"provenance_incomplete:{'+'.join(missing)}")
    for cid in request.content_ids:
        if cid not in envelopes_by_id:
            codes.append(f"unknown_content_ref:{cid}")
        elif ledger.actively_quarantined(cid):
            codes.append(f"content_actively_quarantined:{cid}")
    return tuple(codes)


def governed_external_intake(
    envelope: UntrustedContentEnvelope,
    registry: SourceRegistry,
    segmentation: ContentSegmentation,
    scan: InjectionScanRecord,
    controls_by_tier: dict[str, SourceClassControls],
    context: RunContext,
    provenance: RunProvenance,
    ledger: QuarantineLedger,
    *,
    verification: SourceVerificationRecord | None = None,
    autonomy_ceiling: str = "L2",
) -> tuple[str, ...]:
    """End-to-end external-intake acceptance (02:97-100; 03:90-94).

    Composes, in fixed order: the intake pre-condition gate; the
    injection-response discipline; embedded-instruction quarantine
    coverage (each separated instruction candidate must be quarantined —
    content-instruction isolation, 02:170). Empty tuple = the content may
    enter governed extraction/evidence flows with its UNTRUSTED label
    intact; any non-empty tuple is the auditable failure-path evidence
    (03:90-94).
    """
    codes: list[str] = list(
        external_intake_gate(
            envelope,
            registry,
            segmentation,
            scan,
            controls_by_tier,
            context,
            provenance,
            verification=verification,
            autonomy_ceiling=autonomy_ceiling,
        )
    )
    codes.extend(injection_response_gate(scan, ledger))
    for candidate in segmentation.instruction_candidates:
        if not ledger.actively_quarantined(
            candidate.content_id, candidate.instruction_id
        ):
            codes.append(f"embedded_instruction_requires_quarantine:{candidate.instruction_id}")
    return tuple(codes)
