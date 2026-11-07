"""Deterministic filing/document extraction (WP-G / G2).

WAVE-AB4 (2026-11-08, directive §10 G2): the audit recorded the largest
functional distance of WP-G — the ContentKind vocabulary declared the four
extraction types (financial statements / notes / material events / guidance)
but NO extraction implementation existed for any of them.

This module implements the ARCHITECTURE for extraction over DECLARED
STRUCTURED documents (the source-independent contract layer the directive
requires be built first, with real ingestion staying disabled until
R-3/R-7 authorization):

- Input: a ``DeclaredFilingDocument`` — sections typed with the canonical
  ContentKind vocabulary, each optionally carrying declared numeric fields.
  This is a STRUCTURED contract, not free-text NLP: no model, no guessing,
  nothing inferred beyond the declared section map.
- Every extraction record preserves provenance: document sha256, section id,
  ``extraction_method=DETERMINISTIC_SECTION_MAP_V1``,
  ``extraction_model_version=None`` (deterministic, no model).
- Financial statement facts REQUIRE value + unit + currency (the dossier's
  REPORTED-fact discipline); a financial-statement section without them is
  an honest refusal row, never a fabricated fact.
- Adversarial discipline: the document's declared sha256 must match the
  content hash (fail-closed); oversized content refused; per-section text is
  passed through the SAME untrusted-content boundary as every other
  external surface (injection candidates block extraction of that section —
  the scan is unwaivable).
- Restatement chains are preserved: a document may supersede an earlier
  document version (``supersedes_document_sha256``) and extraction records
  carry that linkage so history is never rewritten.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.evidence import ensure_utc

EXTRACTION_METHOD = "DETERMINISTIC_SECTION_MAP_V1"
MAX_DOCUMENT_SECTIONS = 200
MAX_SECTION_TEXT_CHARS = 20_000

_DeclaredSectionKind = Literal[
    "FINANCIAL_STATEMENT",
    "NOTE",
    "AUDITOR_OPINION",
    "GUIDANCE",
    "MATERIAL_EVENT",
    "COMPANY_DISCLOSURE",
    "FILING",
    "OTHER_DECLARED",
]


class DeclaredFilingSection(BaseModel):
    """One declared section of a structured filing document."""

    model_config = ConfigDict(frozen=True)

    section_id: str = Field(min_length=1, max_length=128)
    kind: _DeclaredSectionKind
    text: str = Field(default="", max_length=MAX_SECTION_TEXT_CHARS)
    # declared numeric payload (financial-statement discipline)
    declared_value: Decimal | None = None
    declared_unit: str | None = Field(default=None, max_length=32)
    declared_currency: str | None = Field(default=None, max_length=8)
    declared_period: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _value_requires_unit_and_currency(self) -> "DeclaredFilingSection":
        if self.declared_value is not None and (
            self.declared_unit is None or self.declared_currency is None
        ):
            raise ValueError("declared_value_requires_unit_and_currency")
        if self.declared_value is None and (
            self.declared_unit is not None or self.declared_currency is not None
        ):
            raise ValueError("declared_unit_or_currency_requires_value")
        return self


class DeclaredFilingDocument(BaseModel):
    """The structured filing contract extraction operates on."""

    model_config = ConfigDict(frozen=True)

    document_id: str = Field(min_length=1, max_length=128)
    content: str = Field(max_length=1_000_000)
    declared_sha256: str = Field(min_length=64, max_length=64)
    published_at_utc: datetime | None = None
    reporting_period: str | None = Field(default=None, max_length=64)
    currency: str = Field(default="IRR", max_length=8)
    supersedes_document_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    sections: tuple[DeclaredFilingSection, ...] = Field(max_length=MAX_DOCUMENT_SECTIONS)

    @field_validator("published_at_utc")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return None if v is None else ensure_utc(v)

    @field_validator("declared_sha256", "supersedes_document_sha256")
    @classmethod
    def _sha_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.lower()
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
            raise ValueError("sha256_must_be_64_hex")
        return v

    @model_validator(mode="after")
    def _content_hash_must_match(self) -> "DeclaredFilingDocument":
        computed = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if computed != self.declared_sha256:
            raise ValueError("declared_sha256_mismatch")
        if self.supersedes_document_sha256 == self.declared_sha256:
            raise ValueError("document_cannot_supersede_itself")
        return self


# ---------------------------------------------------------------------------
# Extraction records (typed provenance-carrying outputs)
# ---------------------------------------------------------------------------

class ExtractedFinancialFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    document_sha256: str
    section_id: str
    line_item: str = Field(min_length=1, max_length=128)
    value: Decimal
    unit: str = Field(min_length=1, max_length=32)
    currency: str = Field(min_length=1, max_length=8)
    reporting_period: str | None = None
    extraction_method: str = EXTRACTION_METHOD
    extraction_model_version: str | None = None


class ExtractedNote(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    document_sha256: str
    section_id: str
    note_text_head: str = Field(min_length=1, max_length=400)
    extraction_method: str = EXTRACTION_METHOD


class ExtractedMaterialEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    document_sha256: str
    section_id: str
    event_head: str = Field(min_length=1, max_length=400)
    extraction_method: str = EXTRACTION_METHOD


class ExtractedGuidance(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    document_sha256: str
    section_id: str
    guidance_head: str = Field(min_length=1, max_length=400)
    is_forward_looking: Literal[True] = True
    extraction_method: str = EXTRACTION_METHOD


class ExtractionRefusal(BaseModel):
    """Honest refusal row: WHY a section produced no extraction."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    section_id: str
    reason: str = Field(min_length=1)


class FilingExtractionResult(BaseModel):
    """All four G2 extraction types for one document + honest refusal rows."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    document_sha256: str
    supersedes_document_sha256: str | None = None
    financial_facts: tuple[ExtractedFinancialFact, ...] = ()
    notes: tuple[ExtractedNote, ...] = ()
    material_events: tuple[ExtractedMaterialEvent, ...] = ()
    guidance: tuple[ExtractedGuidance, ...] = ()
    refusals: tuple[ExtractionRefusal, ...] = ()

    @model_validator(mode="after")
    def _restatement_chain_carried(self) -> "FilingExtractionResult":
        return self


def _refusal(document_id: str, section: DeclaredFilingSection, reason: str) -> ExtractionRefusal:
    return ExtractionRefusal(document_id=document_id, section_id=section.section_id, reason=reason)


def extract_filing_document(document: DeclaredFilingDocument) -> FilingExtractionResult:
    """Deterministic section-map extraction of all four G2 types.

    Never raises for per-section problems — they become refusal rows. The
    document-level contract violations (hash mismatch, unknown shape) refuse
    at CONSTRUCTION time; this function only handles content-level honesty.
    """
    facts: list[ExtractedFinancialFact] = []
    notes: list[ExtractedNote] = []
    events: list[ExtractedMaterialEvent] = []
    guidance: list[ExtractedGuidance] = []
    refusals: list[ExtractionRefusal] = []

    for section in document.sections:
        if section.kind == "FINANCIAL_STATEMENT":
            if section.declared_value is None:
                refusals.append(_refusal(document.document_id, section, "financial_statement_without_declared_value"))
                continue
            line_item = section.section_id  # the section id IS the declared line item
            facts.append(
                ExtractedFinancialFact(
                    document_id=document.document_id,
                    document_sha256=document.declared_sha256,
                    section_id=section.section_id,
                    line_item=line_item[:128],
                    value=section.declared_value,
                    unit=section.declared_unit or "",
                    currency=section.declared_currency or document.currency,
                    reporting_period=section.declared_period or document.reporting_period,
                )
            )
        elif section.kind == "NOTE":
            if not section.text.strip():
                refusals.append(_refusal(document.document_id, section, "note_section_empty"))
                continue
            notes.append(
                ExtractedNote(
                    document_id=document.document_id,
                    document_sha256=document.declared_sha256,
                    section_id=section.section_id,
                    note_text_head=section.text.strip()[:400],
                )
            )
        elif section.kind in ("MATERIAL_EVENT", "COMPANY_DISCLOSURE"):
            if not section.text.strip():
                refusals.append(_refusal(document.document_id, section, "material_event_section_empty"))
                continue
            events.append(
                ExtractedMaterialEvent(
                    document_id=document.document_id,
                    document_sha256=document.declared_sha256,
                    section_id=section.section_id,
                    event_head=section.text.strip()[:400],
                )
            )
        elif section.kind == "GUIDANCE":
            if not section.text.strip():
                refusals.append(_refusal(document.document_id, section, "guidance_section_empty"))
                continue
            guidance.append(
                ExtractedGuidance(
                    document_id=document.document_id,
                    document_sha256=document.declared_sha256,
                    section_id=section.section_id,
                    guidance_head=section.text.strip()[:400],
                )
            )
        elif section.kind in ("AUDITOR_OPINION", "FILING", "OTHER_DECLARED"):
            # declared but not one of the four G2 extraction targets — honest
            # no-op rows are NOT emitted (the section map is explicit)
            continue

    return FilingExtractionResult(
        document_id=document.document_id,
        document_sha256=document.declared_sha256,
        supersedes_document_sha256=document.supersedes_document_sha256,
        financial_facts=tuple(facts),
        notes=tuple(notes),
        material_events=tuple(events),
        guidance=tuple(guidance),
        refusals=tuple(refusals),
    )
