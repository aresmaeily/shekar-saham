"""AI-6 deterministic reference injection scanner for RADAR BOURSE.

Corpus loci (2026-10-02 amendment corpus; see also
AI4_AI7_P343_DEPENDENCY_MATRIX.md §AI-6):
- 02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 97-100: "AI-6 --- External
  Intelligence: Only after untrusted-content boundaries, provenance,
  verification, injection controls and Two-Key Rule."
- 02 lines 161-170: "All external content is untrusted input.
  Prompt-injection and content-instruction isolation, provenance, tool
  boundaries and the Two-Key Rule remain mandatory."
- 03_AI_GOVERNANCE_BOUNDARIES lines 19-25 / 73-76: untrusted content is not
  executable; "injection defense" is required before any AI-6 flow.
- Dependency matrix §AI-6 "Authorized NOW": untrusted-content boundary +
  injection-isolation CONTRACT design (pre-G2 class).

This module is the caller-side deterministic reference scanner the
``external_intelligence`` contract layer anticipated ("The SCAN that
produces findings is a caller-side deterministic scanner"). It composes the
canonical AI-6 schemas by direct import — no parallel vocabulary:

- findings use exactly ``external_intelligence.InjectionFindingKind``
  (DIRECT_INSTRUCTION / INSTRUCTION_CONFLICT / TOOL_INVOCATION_ATTEMPT /
  PRIVILEGE_ESCALATION / OBFUSCATED_INSTRUCTION / NONE_DETECTED);
- candidates are emitted as ``EmbeddedInstructionCandidate`` (executable
  structurally False) inside a ``ContentSegmentation``;
- the scan result is recorded as an ``InjectionScanRecord``.

Pure heuristics only: a SMALL, explicit, documented pattern table (each
pattern carries a fixed confidence inside the declared closed band
[CONFIDENCE_MIN, CONFIDENCE_MAX]) plus two structural evasion probes
(zero-width hidden characters; NFKC fullwidth/homoglyph normalization).
No LLM, no network, no I/O, no clock read — ``now_utc`` is injected, and
the content text is supplied by the caller (the envelope exchanges payload
by reference only, D-AI-23). Scanning never raises trust: a clean scan
yields NONE_DETECTED and the envelope stays UNTRUSTED.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.evidence import ensure_utc
from app.domain.external_intelligence import (
    InjectionFindingKind,
    UntrustedContentEnvelope,
    ContentSegmentation,
    EmbeddedInstructionCandidate,
    InjectionScanRecord,
)

__all__ = [
    "CONFIDENCE_MAX",
    "CONFIDENCE_MIN",
    "MAX_SCAN_CONTENT_CHARS",
    "OBFUSCATION_CONFIDENCE",
    "DEFAULT_SCANNER_ID",
    "DEFAULT_POLICY_VERSION",
    "ScanVerdict",
    "DetectedInstruction",
    "InjectionScanResult",
    "PATTERN_TABLE",
    "scan_content",
]

# ---------------------------------------------------------------------------
# Declared closed band and module-level ceilings (documented; the envelope
# schema carries no content-size bound, so the ceiling lives here).
# ---------------------------------------------------------------------------

#: Closed confidence band for every emitted candidate confidence.
CONFIDENCE_MIN: float = 0.50
CONFIDENCE_MAX: float = 1.00

#: Fixed confidence for the two structural (non-regex) obfuscation probes.
OBFUSCATION_CONFIDENCE: float = 0.70

#: Documented module-level content ceiling. The envelope defines no content
#: limit, so the scanner imposes this one and refuses larger inputs
#: deterministically (fail-closed, never truncates silently).
MAX_SCAN_CONTENT_CHARS: int = 200_000

#: Excerpt ceiling inherited from the canonical candidate schema.
_EXCERPT_MAX_CHARS = 2000

DEFAULT_SCANNER_ID = "reference.deterministic-injection-scanner"
DEFAULT_POLICY_VERSION = "injection-heuristics-v1"

#: Closed verdict vocabulary of THIS module (the finding kinds stay the
#: canonical closed taxonomy; the verdict is the scanner's decision label).
ScanVerdict = Literal[
    "NO_INJECTION_FOUND",
    "SUSPECTED_INSTRUCTION",
    "QUARANTINE_RECOMMENDED",
]

#: Canonical emission order for finding kinds (taxonomy order, not discovery).
_FINDING_ORDER: tuple[str, ...] = (
    "DIRECT_INSTRUCTION",
    "INSTRUCTION_CONFLICT",
    "TOOL_INVOCATION_ATTEMPT",
    "PRIVILEGE_ESCALATION",
    "OBFUSCATED_INSTRUCTION",
)

#: Finding kinds whose presence alone recommends quarantine. OBFUSCATED alone
#: is SUSPECTED_INSTRUCTION (suspicion, not confirmation).
_ELEVATED_KINDS: frozenset[str] = frozenset(
    {
        "DIRECT_INSTRUCTION",
        "INSTRUCTION_CONFLICT",
        "TOOL_INVOCATION_ATTEMPT",
        "PRIVILEGE_ESCALATION",
    }
)

# ---------------------------------------------------------------------------
# Explicit, small, documented pattern table.
# ---------------------------------------------------------------------------
# Each row: (finding_kind, probe_name, compiled_regex, fixed_confidence).
# The list is intentionally SHORT and auditable; each entry cites the trick
# it detects. Confidences are engineering-declared constants inside the
# closed band — no learned/ML scoring anywhere.


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


PATTERN_TABLE: tuple[tuple[str, str, re.Pattern[str], float], ...] = (
    # --- DIRECT_INSTRUCTION: classic instruction-override phrasing --------
    (
        "DIRECT_INSTRUCTION",
        "ignore_previous_instructions",
        _c(r"\bignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?|directives?)\b"),
        0.95,
    ),
    (
        "DIRECT_INSTRUCTION",
        "disregard_instructions",
        _c(r"\bdisregard\b[^.\n]{0,60}?\b(?:instructions?|rules?|guardrails?|directives?)\b"),
        0.90,
    ),
    (
        "DIRECT_INSTRUCTION",
        "forget_everything",
        _c(r"\bforget\s+(?:everything|all)\b"),
        0.70,
    ),
    (
        "DIRECT_INSTRUCTION",
        "new_instructions_for_model",
        _c(r"\b(?:new|updated|revised)\s+(?:instructions?|system\s*prompt|directives?)\s*:"),
        0.85,
    ),
    (
        "DIRECT_INSTRUCTION",
        "imperative_to_model",
        _c(r"\b(?:you\s+must\s+now|from\s+now\s+on\s+you|you\s+are\s+now|do\s+not\s+tell\s+the\s+user|keep\s+this\s+(?:secret|confidential)|respond\s+only\s+with)\b"),
        0.75,
    ),
    # --- INSTRUCTION_CONFLICT: conflict with governed instructions --------
    (
        "INSTRUCTION_CONFLICT",
        "override_governed_rules",
        _c(r"\boverride\s+(?:your\s+|the\s+)?(?:rules|instructions|policies|guardrails)\b"),
        0.90,
    ),
    (
        "INSTRUCTION_CONFLICT",
        "no_longer_bound",
        _c(r"\byou\s+are\s+no\s+longer\s+bound\b"),
        0.90,
    ),
    (
        "INSTRUCTION_CONFLICT",
        "disable_guardrails",
        _c(r"\b(?:ignore|bypass|disable)\s+(?:your\s+|the\s+)?(?:safety|guardrails?|content\s+policy)\b"),
        0.90,
    ),
    # --- TOOL_INVOCATION_ATTEMPT: content trying to invoke tools ----------
    (
        "TOOL_INVOCATION_ATTEMPT",
        "explicit_tool_command",
        _c(r"\b(?:run|execute|invoke|call)\s+(?:the\s+|this\s+)?(?:tool|function|command|script|shell)\b"),
        0.85,
    ),
    (
        "TOOL_INVOCATION_ATTEMPT",
        "network_fetch_command",
        _c(r"\b(?:curl|wget)\s+\S+"),
        0.80,
    ),
    (
        "TOOL_INVOCATION_ATTEMPT",
        "directed_download",
        _c(r"\b(?:fetch|retrieve|download)\s+(?:the\s+)?(?:content|page|url|file)\s+(?:at|from)\s+https?://\S+"),
        0.80,
    ),
    # --- PRIVILEGE_ESCALATION: owner/authority claims inside content ------
    (
        "PRIVILEGE_ESCALATION",
        "owner_approval_claim",
        _c(r"\b(?:the\s+)?owner\s+(?:has\s+)?(?:approved|authorized)\b"),
        0.90,
    ),
    (
        "PRIVILEGE_ESCALATION",
        "grant_privilege",
        _c(r"\b(?:grant|elevate|escalate)\s+(?:\w+\s+){0,3}(?:permissions?|privileges?|access|autonomy)\b"),
        0.85,
    ),
    (
        "PRIVILEGE_ESCALATION",
        "disable_kill_switch",
        _c(r"\b(?:disable|release|bypass)\s+(?:the\s+)?(?:kill\s*switch|governor|two[\s-]?key(?:\s+rule)?)\b"),
        0.90,
    ),
)

# Import-time fail-fast: every declared confidence must sit inside the band.
for _kind, _name, _rx, _conf in PATTERN_TABLE:
    if _kind not in _FINDING_ORDER or _kind == "OBFUSCATED_INSTRUCTION":
        raise RuntimeError("scanner_pattern_table_kind_invalid")
    if not (CONFIDENCE_MIN <= _conf <= CONFIDENCE_MAX):
        raise RuntimeError("scanner_pattern_confidence_out_of_band")

_ZERO_WIDTH_CHARS: tuple[str, ...] = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff")
_ZERO_WIDTH_IN_WORD = re.compile(r"\w[\u200b\u200c\u200d\u2060\ufeff]+\w")


# ---------------------------------------------------------------------------
# Detection detail record (scanner bookkeeping; the canonical exchange shape
# remains EmbeddedInstructionCandidate / ContentSegmentation).
# ---------------------------------------------------------------------------


class DetectedInstruction(BaseModel):
    """One deterministic detection: kind, char/byte span, confidence.

    ``start_char``/``end_char`` are Python string indices into the scanned
    content; ``start_byte``/``end_byte`` are UTF-8 byte offsets (the offsets
    exchanged in audit evidence). ``probe`` names the explicit table entry
    or structural probe that produced the detection.
    """

    model_config = ConfigDict(frozen=True)

    finding_kind: InjectionFindingKind
    probe: str = Field(min_length=1, max_length=128)
    excerpt: str = Field(min_length=1, max_length=_EXCERPT_MAX_CHARS)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)
    confidence: float = Field(ge=CONFIDENCE_MIN, le=CONFIDENCE_MAX)

    @model_validator(mode="after")
    def _span_order(self) -> "DetectedInstruction":
        if self.end_char <= self.start_char or self.end_byte <= self.start_byte:
            raise ValueError("detected_span_must_be_nonempty")
        return self


# ---------------------------------------------------------------------------
# Scan result bundle (composes the canonical records + scanner verdict)
# ---------------------------------------------------------------------------


class InjectionScanResult(BaseModel):
    """Deterministic output of one ``scan_content`` invocation.

    Binds the canonical ``InjectionScanRecord`` and
    ``ContentSegmentation`` (both composed, not forked) with this module's
    closed verdict and reason codes. ``reason_codes`` is a stable,
    fixed-order tuple — empty never occurs (a clean scan records
    ``none_detected``).
    """

    model_config = ConfigDict(frozen=True)

    scan: InjectionScanRecord
    segmentation: ContentSegmentation
    verdict: ScanVerdict
    reason_codes: tuple[str, ...] = Field(min_length=1)
    detections: tuple[DetectedInstruction, ...] = ()


# ---------------------------------------------------------------------------
# The deterministic reference scanner
# ---------------------------------------------------------------------------


def _byte_offset(content: str, char_index: int) -> int:
    return len(content[:char_index].encode("utf-8"))


def _make_detection(
    content: str,
    finding_kind: str,
    probe: str,
    start_char: int,
    end_char: int,
    excerpt: str,
    confidence: float,
) -> DetectedInstruction:
    return DetectedInstruction(
        finding_kind=finding_kind,  # type: ignore[arg-type]
        probe=probe,
        excerpt=excerpt[:_EXCERPT_MAX_CHARS],
        start_char=start_char,
        end_char=end_char,
        start_byte=_byte_offset(content, start_char),
        end_byte=_byte_offset(content, end_char),
        confidence=confidence,
    )


def _pattern_detections(content: str) -> tuple[DetectedInstruction, ...]:
    detections: list[DetectedInstruction] = []
    for kind, probe_name, regex, confidence in PATTERN_TABLE:
        for match in regex.finditer(content):
            detections.append(
                _make_detection(
                    content,
                    kind,
                    probe_name,
                    match.start(),
                    match.end(),
                    match.group(0),
                    confidence,
                )
            )
    return tuple(detections)


def _zero_width_detections(
    content: str, raw_detections: tuple[DetectedInstruction, ...]
) -> tuple[DetectedInstruction, ...]:
    """Structural probe 1: zero-width hidden characters (evasion markers).

    Zero-width characters embedded INSIDE a word break the literal text
    (``ig\\u200bnore`` is not ``ignore`` to a raw pattern) while remaining
    invisible to a reader. When stripping them exposes a pattern match the
    raw text could not produce, an OBFUSCATED_INSTRUCTION detection is
    emitted: the span covers the hidden characters themselves (real
    positions in the original content) and the excerpt carries the
    exposed text. When nothing is exposed, zero-width characters embedded
    between word characters are still reported as an obfuscation marker.
    """
    zw_positions = [i for i, ch in enumerate(content) if ch in _ZERO_WIDTH_CHARS]
    if not zw_positions:
        return ()
    detections: list[DetectedInstruction] = []
    stripped = content
    for zw in _ZERO_WIDTH_CHARS:
        stripped = stripped.replace(zw, "")
    raw_keys = {(d.finding_kind, d.excerpt) for d in raw_detections}
    exposed = False
    if stripped != content:
        for kind, probe_name, regex, _conf in PATTERN_TABLE:
            for match in regex.finditer(stripped):
                if (kind, match.group(0)) in raw_keys:
                    continue  # already visible in raw text — not evasion
                detections.append(
                    _make_detection(
                        content,
                        "OBFUSCATED_INSTRUCTION",
                        f"zero_width_strip:{probe_name}",
                        min(zw_positions),
                        max(zw_positions) + 1,
                        match.group(0),
                        OBFUSCATION_CONFIDENCE,
                    )
                )
                exposed = True
                break  # one probe hit per pattern is enough (deterministic)
    if not exposed:
        for match in _ZERO_WIDTH_IN_WORD.finditer(content):
            detections.append(
                _make_detection(
                    content,
                    "OBFUSCATED_INSTRUCTION",
                    "zero_width_embedded",
                    match.start(),
                    match.end(),
                    match.group(0),
                    OBFUSCATION_CONFIDENCE,
                )
            )
    return tuple(detections)


def _nfkc_detections(content: str) -> tuple[DetectedInstruction, ...]:
    """Structural probe 2: tiny NFKC-based confusable check.

    Lines whose NFKC normalization differs from the raw text (fullwidth
    forms, compatibility homoglyphs) are re-scanned after normalization; a
    pattern match on the NORMALIZED line that the raw line could not
    produce is reported as OBFUSCATED_INSTRUCTION. The reported span is the
    containing line; the excerpt is the normalized match text.
    """
    detections: list[DetectedInstruction] = []
    offset = 0
    for line in content.split("\n"):
        line_end = offset + len(line)
        normalized = unicodedata.normalize("NFKC", line)
        if normalized != line:
            for kind, probe_name, regex, _conf in PATTERN_TABLE:
                for match in regex.finditer(normalized):
                    if regex.search(line):
                        continue  # raw line already matches — not evasion
                    detections.append(
                        _make_detection(
                            content,
                            "OBFUSCATED_INSTRUCTION",
                            f"nfkc_normalize:{probe_name}",
                            offset,
                            line_end,
                            match.group(0),
                            OBFUSCATION_CONFIDENCE,
                        )
                    )
                    break
        offset = line_end + 1  # account for the split newline
    return tuple(detections)


def _dedupe(
    detections: tuple[DetectedInstruction, ...]
) -> tuple[DetectedInstruction, ...]:
    seen: set[tuple[str, str, int, int]] = set()
    unique: list[DetectedInstruction] = []
    for d in detections:
        key = (d.finding_kind, d.probe, d.start_char, d.end_char)
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)
    return tuple(unique)


def scan_content(
    envelope: UntrustedContentEnvelope,
    content: str,
    *,
    now_utc: datetime,
    scanner_id: str = DEFAULT_SCANNER_ID,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> InjectionScanResult:
    """Deterministic reference injection scan over one piece of content.

    Refusals (deterministic ``ValueError`` reason codes):
    - ``scan_content_empty`` — empty or whitespace-only content;
    - ``scan_content_exceeds_ceiling`` — content longer than
      ``MAX_SCAN_CONTENT_CHARS`` (the envelope defines no content limit, so
      the module ceiling applies; oversized input is refused, never
      silently truncated);
    - ``content_sha256_mismatch`` — the content bytes do not hash to the
      envelope's declared ``content_sha256`` (provenance binding, 02:170).

    Verdict rules (deterministic):
    - no detections → ``NO_INJECTION_FOUND`` / reason ``none_detected``;
    - any DIRECT_INSTRUCTION / INSTRUCTION_CONFLICT /
      TOOL_INVOCATION_ATTEMPT / PRIVILEGE_ESCALATION detection →
      ``QUARANTINE_RECOMMENDED`` with one reason per elevated kind
      (canonical order) plus ``obfuscated_instruction_present`` when an
      obfuscation probe also fired;
    - only OBFUSCATED_INSTRUCTION detections → ``SUSPECTED_INSTRUCTION``.

    A clean scan never raises trust: the envelope stays UNTRUSTED and the
    scan record carries ``NONE_DETECTED`` (03:75 untrusted by default).
    """
    now = ensure_utc(now_utc)
    if not isinstance(content, str) or len(content.strip()) == 0:
        raise ValueError("scan_content_empty")
    if len(content) > MAX_SCAN_CONTENT_CHARS:
        raise ValueError("scan_content_exceeds_ceiling")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != envelope.content_sha256:
        raise ValueError("content_sha256_mismatch")

    raw = _pattern_detections(content)
    detections = _dedupe(
        raw + _zero_width_detections(content, raw) + _nfkc_detections(content)
    )

    if detections:
        findings: tuple[str, ...] = tuple(
            kind for kind in _FINDING_ORDER if any(d.finding_kind == kind for d in detections)
        )
    else:
        findings = ("NONE_DETECTED",)

    scan = InjectionScanRecord(
        scan_id=f"{envelope.content_id}-scan",
        content_id=envelope.content_id,
        scanner_id=scanner_id,
        policy_version=policy_version,
        findings=findings,  # type: ignore[arg-type]
        scanned_at_utc=now,
        notes=f"content_sha256={digest}",
    )

    candidates: list[EmbeddedInstructionCandidate] = []
    for index, detection in enumerate(detections, start=1):
        candidates.append(
            EmbeddedInstructionCandidate(
                instruction_id=f"{envelope.content_id}-cand-{index:04d}",
                content_id=envelope.content_id,
                excerpt=detection.excerpt,
                executable=False,
                notes=(
                    f"finding_kind={detection.finding_kind};"
                    f"probe={detection.probe};"
                    f"start_byte={detection.start_byte};"
                    f"end_byte={detection.end_byte};"
                    f"confidence={detection.confidence:.2f}"
                ),
            )
        )
    segmentation = ContentSegmentation(
        segmentation_id=f"{envelope.content_id}-seg",
        content_id=envelope.content_id,
        payload_segment_count=1,
        instruction_candidates=tuple(candidates),
        separated_at_utc=now,
        notes="reference scanner: payload exchanged by reference (D-AI-23)",
    )

    elevated = [k for k in findings if k in _ELEVATED_KINDS]
    obfuscated_present = "OBFUSCATED_INSTRUCTION" in findings
    if elevated:
        verdict: ScanVerdict = "QUARANTINE_RECOMMENDED"
        reasons = [f"quarantine_recommended:{k}" for k in elevated]
        if obfuscated_present:
            reasons.append("obfuscated_instruction_present")
    elif obfuscated_present:
        verdict = "SUSPECTED_INSTRUCTION"
        reasons = ["obfuscated_instruction_suspected"]
    else:
        verdict = "NO_INJECTION_FOUND"
        reasons = ["none_detected"]

    return InjectionScanResult(
        scan=scan,
        segmentation=segmentation,
        verdict=verdict,
        reason_codes=tuple(reasons),
        detections=detections,
    )
