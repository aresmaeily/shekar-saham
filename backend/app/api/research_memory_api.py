"""AI-3 research-memory HTTP surface (owner directive 2026-11-08 §3).

Additive router — ``/api/v10/memory``. The REAL application cycle of the
research memory: DURABLE SQLite/WAL store (D1, AES-256-GCM at rest per D4)
wrapped in the tamper-evident audited wrapper, with the audit trail itself
DURABLE (hash-chained, per-row digests, verified backup, fail-closed on
tamper). Honest, bounded, synthetic/paper-only:

- every write/read through the surface lands an audit row (OK or REFUSED
  with the contract's reason) in the durable chain;
- instants are CALLER-SUPPLIED (no wall clock in the domain); the API
  validates and forwards them; typed 422 refusals otherwise;
- refusals are honest and typed: a missing key (fail-closed D4 posture),
  a closed audit gate (tamper), contract conflicts (duplicate ids,
  archive-citation rule, supersede rules) — nothing is fabricated;
- no delete/purge path exists (D3 retention: PERMANENT; purge stays
  owner-gated);
- trust labels come from the server fields only (SYNTHETIC_OR_PAPER).
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.domain.research_memory import EpisodicRunArtifact, SemanticLesson
from app.services.research_memory_service import (
    ResearchMemoryRefusal,
    get_research_memory_service,
)

router = APIRouter(prefix="/api/v10/memory", tags=["research-memory"])


def _typed_422(code: str, en: str, fa: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": code,
            "message_en": en,
            "message_fa": fa,
            **extra,
        },
    )


def _service_or_refuse():
    service = get_research_memory_service()
    if service.refused_reason is not None:
        raise _typed_422(
            service.refused_reason,
            "research memory surface is fail-closed refused",
            "سطح حافظه پژوهش به‌صورت fail-closed رد شده است",
        )
    return service


def _refuse(exc: ResearchMemoryRefusal):
    raise _typed_422(
        exc.reason,
        "research memory operation refused",
        "عملیات حافظه پژوهش رد شد",
    )


def _trust_envelope() -> Dict[str, Any]:
    return {
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "note": "حافظه پژوهش فقط رکوردهای محلی SYNTHETIC_OR_PAPER را نگه می‌دارد؛ هیچ منبع زنده‌ای در این سطح نیست",
    }


class EpisodicAppendBody(BaseModel):
    entry: Dict[str, Any] = Field(min_length=1, description="EpisodicRunArtifact payload")


class LessonRegisterBody(BaseModel):
    lesson: Dict[str, Any] = Field(min_length=1, description="SemanticLesson payload")


@router.get("/posture")
async def memory_posture() -> Dict[str, Any]:
    """Honest posture of the research-memory surface (always callable)."""
    service = get_research_memory_service()
    return {
        "ok": True,
        "posture": service.posture(),
        "trust_envelope": _trust_envelope(),
        "disclosures": {
            "no_purge_path": "هیچ مسیر حذف/پاک‌سازی در این سطح وجود ندارد (D3: PERMANENT)",
            "audit_refs_only": "ردیف‌های حسابرسی فقط REFERENCE هستند؛ محتوای خصوصی هرگز وارد دفتر نمی‌شود",
            "fail_closed_key": "بدون کلید (env یا OS keyring) سطح با رد تایپ‌شده بسته می‌شود",
        },
    }


@router.post("/episodic")
async def episodic_append(body: EpisodicAppendBody) -> Dict[str, Any]:
    """Append one episodic run artifact (durable, audited, fail-closed)."""
    service = _service_or_refuse()
    try:
        entry = EpisodicRunArtifact(**body.entry)
    except Exception as exc:
        raise _typed_422(
            "episodic_entry_invalid",
            str(exc)[:256],
            "رکورد اپیزودیک نامعتبر است",
        )
    try:
        service.append_episodic(entry, at_utc=entry.recorded_at_utc, run_id=entry.run_id)
    except ResearchMemoryRefusal as exc:
        _refuse(exc)
    except ValueError as exc:
        raise _typed_422(
            "episodic_append_refused",
            str(exc)[:256],
            "الحاق اپیزودیک رد شد (تعارض قرارداد)",
        )
    return {
        "ok": True,
        "entry_id": entry.entry_id,
        "run_id": entry.run_id,
        "audit_entries": service.posture()["audit_entries"],
        "trust_envelope": _trust_envelope(),
    }


@router.get("/episodic/{entry_id}")
async def episodic_get(entry_id: str) -> Dict[str, Any]:
    service = _service_or_refuse()
    try:
        found = service.get_episodic(entry_id)
    except ResearchMemoryRefusal as exc:
        _refuse(exc)
    if found is None:
        return {
            "ok": True,
            "found": False,
            "entry_id": entry_id,
            "disclosure": "object_not_found",
            "trust_envelope": _trust_envelope(),
        }
    return {
        "ok": True,
        "found": True,
        "entry": found.model_dump(mode="json"),
        "trust_envelope": _trust_envelope(),
    }


@router.get("/episodic/run/{run_id}")
async def episodic_for_run(run_id: str) -> Dict[str, Any]:
    service = _service_or_refuse()
    try:
        rows = service.episodic_for_run(run_id)
    except ResearchMemoryRefusal as exc:
        _refuse(exc)
    return {
        "ok": True,
        "run_id": run_id,
        "count": len(rows),
        "entries": [r.model_dump(mode="json") for r in rows],
        "trust_envelope": _trust_envelope(),
    }


@router.post("/lessons")
async def lesson_register(body: LessonRegisterBody) -> Dict[str, Any]:
    """Register one curated semantic lesson (versioned, audited)."""
    service = _service_or_refuse()
    try:
        lesson = SemanticLesson(**body.lesson)
    except Exception as exc:
        raise _typed_422(
            "lesson_payload_invalid",
            str(exc)[:256],
            "درس معنایی نامعتبر است",
        )
    try:
        service.register_lesson(lesson, at_utc=lesson.created_at_utc, run_id=lesson.run_id)
    except ResearchMemoryRefusal as exc:
        _refuse(exc)
    except ValueError as exc:
        raise _typed_422(
            "lesson_register_refused",
            str(exc)[:256],
            "ثبت درس رد شد (قانون ارجاع آرشیو / قاعده نسخه‌گذاری)",
        )
    return {
        "ok": True,
        "lesson_id": lesson.lesson_id,
        "version": lesson.version,
        "audit_entries": service.posture()["audit_entries"],
        "trust_envelope": _trust_envelope(),
    }


@router.get("/lessons/{lesson_id}")
async def lesson_get(lesson_id: str) -> Dict[str, Any]:
    service = _service_or_refuse()
    try:
        found = service.get_lesson(lesson_id)
        history = service.lesson_history(lesson_id)
    except ResearchMemoryRefusal as exc:
        _refuse(exc)
    return {
        "ok": True,
        "found": found is not None,
        "lesson": found.model_dump(mode="json") if found is not None else None,
        "history_count": len(history),
        "history": [h.model_dump(mode="json") for h in history],
        "trust_envelope": _trust_envelope(),
    }


@router.get("/integrity")
async def memory_integrity() -> Dict[str, Any]:
    """Content integrity report (per-record digests) + audit-chain verdict."""
    service = _service_or_refuse()
    try:
        report = service.integrity_report()
    except ResearchMemoryRefusal as exc:
        _refuse(exc)
    posture = service.posture()
    return {
        "ok": True,
        "integrity": report.model_dump(mode="json") if hasattr(report, "model_dump") else str(report),
        "audit_chain": {
            "entries": posture["audit_entries"],
            "head_digest": posture["audit_head_digest"],
            "first_broken_sequence": posture["audit_first_broken_sequence"],
            "gate_closed_reason": posture["audit_gate_closed_reason"],
            "verdict": "INTACT" if (posture["audit_first_broken_sequence"] is None) else "CLOSED_FAIL_CLOSED",
        },
        "trust_envelope": _trust_envelope(),
    }


@router.get("/audit")
async def memory_audit() -> Dict[str, Any]:
    """The tamper-evident access/operation audit trail (refs only, verbatim)."""
    service = get_research_memory_service()
    posture = service.posture()
    rows = []
    if service.audit_trail is not None:
        for e in service.audit_trail.entries:
            rows.append(
                {
                    "sequence": e.sequence,
                    "actor": e.actor,
                    "authorization_context": e.authorization_context,
                    "operation": e.operation,
                    "memory_layer": e.memory_layer,
                    "object_ref": e.object_ref,
                    "run_id": e.run_id,
                    "at_utc": e.at_utc.isoformat().replace("+00:00", "Z"),
                    "outcome": e.outcome,
                    "refusal_reason": e.refusal_reason,
                    "detail": e.detail,
                    "entry_digest": e.entry_digest,
                    "prior_digest": e.prior_digest,
                }
            )
    return {
        "ok": True,
        "count": len(rows),
        "entries": rows,
        "chain": {
            "head_digest": posture["audit_head_digest"],
            "first_broken_sequence": posture["audit_first_broken_sequence"],
            "gate_closed_reason": posture["audit_gate_closed_reason"],
            "durable": posture["audit_trail_durable"],
        },
        "trust_envelope": _trust_envelope(),
    }


@router.post("/backup")
async def memory_backup() -> Dict[str, Any]:
    """D5 verified backup of both carriers into data/backups/research-memory/."""
    service = _service_or_refuse()
    from app.core.config import DATA_DIR

    try:
        result = service.backup(DATA_DIR / "backups" / "research-memory")
    except ResearchMemoryRefusal as exc:
        _refuse(exc)
    except Exception as exc:  # honest typed failure
        raise _typed_422(
            "memory_backup_failed",
            str(exc)[:256],
            "پشتیبان‌گیری تأییدشده شکست خورد",
        )
    return {
        "ok": True,
        "backup": result,
        "destination": "data/backups/research-memory (D5: محلی، روزانه، keep=14)",
        "trust_envelope": _trust_envelope(),
    }
