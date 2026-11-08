"""AI-3 research-memory RUNTIME integration (owner directive 2026-11-08 §3).

The D1–D7 recorded decisions (OWNER_DECISIONS_RECORDED_2026-11-02.md) shipped
the durable SQLite/WAL adapter (``app.data.research_memory_sqlite``) and the
2026-11-08 owner directive explicitly orders the REAL application-cycle
integration: «پیاده‌سازی مستقل یک ماژول به معنی اتصال آن به محصول نیست.
اتصال واقعی و تست runtime الزامی است.»

This service is that integration — mirroring the prediction-store factory
precedent (``app.services.prediction_store.get_prediction_store``):

- DEFAULT backend is DURABLE: ``SqliteWalResearchMemoryStore`` (D1:
  SQLite/WAL + AES-256-GCM at rest) wrapped in the tamper-evident
  ``AuditedResearchMemoryStore`` whose audit chain is itself DURABLE
  (``app.data.memory_access_audit_sqlite.DurableMemoryAccessAuditTrail``).
- Key source (D4): ``select_key_provider()`` — the
  ``RADAR_RESEARCH_MEMORY_KEY`` env override first, then the OS keyring
  (Windows Credential Manager via the optional ``keyring`` dependency,
  create-if-missing once). NO key available = fail-closed REFUSAL posture:
  the surface reports the typed reason honestly instead of degrading to a
  weaker backend (never silently unencrypted, never silently in-memory).
- ``memory`` backend exists ONLY as an explicit unit-test choice
  (``RESEARCH_MEMORY_BACKEND=memory``), never a default: the audit trail is
  then the in-memory domain chain and the posture discloses
  ``persistence_durable=False`` honestly.
- D5 backups: ``data/backups/research-memory/`` via the adapter's verified
  backup (SQLite backup API + integrity check); the audit trail's own
  verified backup lives beside it.
- Restart recovery: the durable stores re-open, re-migrate, re-verify every
  row digest and the whole audit chain at construction (fail-closed closed
  gate on any tamper).

No scheduler, no egress, no live provider, no promotion path: this module
only persists and audits local synthetic/paper research-memory records.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import DATA_DIR, get_settings
from app.data.memory_access_audit_sqlite import (
    DurableMemoryAccessAuditTrail,
    MemoryAuditStoreError,
)
from app.data.research_memory_sqlite import (
    SqliteWalResearchMemoryStore,
    select_key_provider,
)
from app.domain.memory_access_audit import (
    AuditedResearchMemoryStore,
    MemoryAccessAuditTrail,
)
from app.domain.research_memory_store import InMemoryResearchMemoryStore

RETENTION_NOTE = (
    "D3: شواهد اپیزودیک و تاریخ درس‌های معنایی PERMANENT است (هیچ مسیر حذف/پاک‌سازی "
    "در این سطح وجود ندارد)؛ پاک‌سازی مالک-گیت است"
)


class ResearchMemoryRefusal(Exception):
    """Fail-closed refusal of the whole surface (reason carried)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _DurableAuditTrailView:
    """The audit-trail surface ``AuditedResearchMemoryStore`` needs, backed by
    the DURABLE SQLite/WAL store (composition — the domain chain semantics
    stay in ``app.domain.memory_access_audit``)."""

    def __init__(self, durable: DurableMemoryAccessAuditTrail) -> None:
        self._durable = durable

    def record(
        self,
        *,
        actor: str,
        authorization_context: str,
        operation: str,
        object_ref: str,
        at_utc: datetime,
        run_id: str | None = None,
        outcome: str = "OK",
        refusal_reason: str | None = None,
        detail: str = "",
    ) -> "_DurableAuditTrailView":
        self._durable.record(
            actor=actor,
            authorization_context=authorization_context,
            operation=operation,  # type: ignore[arg-type]
            object_ref=object_ref,
            at_utc=at_utc,
            run_id=run_id,
            outcome=outcome,  # type: ignore[arg-type]
            refusal_reason=refusal_reason,
            detail=detail,
        )
        return self

    @property
    def entries(self):
        return self._durable.entries()

    @property
    def head_digest(self) -> str | None:
        return self._durable.head_digest()

    def first_broken_sequence(self) -> int | None:
        return self._durable.first_broken_sequence()

    @property
    def durable(self) -> DurableMemoryAccessAuditTrail:
        return self._durable


class ResearchMemoryService:
    """Composed runtime surface: durable store + audited wrapper."""

    def __init__(
        self,
        *,
        backend_label: str,
        store: Any,
        audit_trail: Any,
        refused_reason: Optional[str] = None,
        db_path: str = "",
        audit_db_path: str = "",
    ) -> None:
        self.backend_label = backend_label
        self.store = store  # AuditedResearchMemoryStore | None (refusal posture)
        self.audit_trail = audit_trail  # _DurableAuditTrailView | MemoryAccessAuditTrail | None
        self.refused_reason = refused_reason
        self.db_path = db_path
        self.audit_db_path = audit_db_path

    # ------------------------------------------------------------- posture
    def posture(self) -> Dict[str, Any]:
        audit_entries = 0
        head: Optional[str] = None
        broken: Optional[int] = None
        if self.audit_trail is not None:
            try:
                audit_entries = len(self.audit_trail.entries)
                head = self.audit_trail.head_digest
                broken = self.audit_trail.first_broken_sequence()
            except Exception:  # pragma: no cover - posture never crashes
                broken = -1
        gate_closed: Optional[str] = None
        if hasattr(self, "_durable_audit"):
            gate_closed = self._durable_audit.gate_closed_reason()
        return {
            "ok": self.refused_reason is None,
            "backend": self.backend_label,
            "persistence_durable": self.backend_label == "sqlite",
            "audit_trail_durable": self.backend_label == "sqlite",
            "encryption_at_rest": self.backend_label == "sqlite",  # D4 AES-256-GCM
            "refused_reason": self.refused_reason,
            "audit_entries": audit_entries,
            "audit_head_digest": head,
            "audit_first_broken_sequence": broken,
            "audit_gate_closed_reason": gate_closed,
            "retention_policy": RETENTION_NOTE,
            "data_trust_label": "SYNTHETIC_OR_PAPER",
        }

    # ------------------------------------------------------------ operations
    def _guarded(self, fn, *args, **kwargs):
        """Run one audited operation; a durable-audit failure (tamper-closed
        gate) becomes the typed refusal — never a silent unaudited write."""
        try:
            return fn(*args, **kwargs)
        except MemoryAuditStoreError as exc:
            raise ResearchMemoryRefusal(f"memory_audit_gate_closed:{exc}") from exc

    def append_episodic(self, entry: Any, *, at_utc: datetime, run_id: str | None = None) -> None:
        self._require_ready()
        if run_id is not None:
            self._guarded(self.store.append_episodic, entry, run_id=run_id)
        else:
            self._guarded(self.store.append_episodic, entry)

    def register_lesson(self, lesson: Any, *, at_utc: datetime, run_id: str | None = None) -> None:
        self._require_ready()
        if run_id is not None:
            self._guarded(self.store.register_lesson, lesson, run_id=run_id)
        else:
            self._guarded(self.store.register_lesson, lesson)

    def get_episodic(self, entry_id: str, *, run_id: str | None = None) -> Any:
        self._require_ready()
        if run_id is not None:
            return self._guarded(self.store.get_episodic, entry_id, run_id=run_id)
        return self._guarded(self.store.get_episodic, entry_id)

    def episodic_for_run(self, run_id: str) -> Any:
        self._require_ready()
        return self._guarded(self.store.episodic_for_run, run_id)

    def get_lesson(self, lesson_id: str, *, run_id: str | None = None) -> Any:
        self._require_ready()
        if run_id is not None:
            return self._guarded(self.store.latest_lesson, lesson_id, run_id=run_id)
        return self._guarded(self.store.latest_lesson, lesson_id)

    def lesson_history(self, lesson_id: str, *, run_id: str | None = None) -> Any:
        self._require_ready()
        if run_id is not None:
            return self._guarded(self.store.lesson_history, lesson_id, run_id=run_id)
        return self._guarded(self.store.lesson_history, lesson_id)

    def integrity_report(self) -> Any:
        self._require_ready()
        return self._guarded(self.store.integrity_report)

    def _require_ready(self) -> None:
        if self.refused_reason is not None or self.store is None:
            raise ResearchMemoryRefusal(self.refused_reason or "research_memory_unavailable")

    # ---------------------------------------------------------------- backup
    def backup(self, destination_dir: Path | str, *, keep: int = 14) -> Dict[str, Any]:
        """D5 verified backup of BOTH carriers (memory store + audit trail)."""
        self._require_ready()
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        results: Dict[str, Any] = {"verified": True, "parts": {}}
        mem = getattr(self, "_memory_store", None)
        if mem is not None and hasattr(mem, "backup"):
            # D1 adapter returns the snapshot Path (+ .sha256 sidecar)
            snap = Path(mem.backup(dest, keep=keep))
            data = snap.read_bytes()
            import hashlib as _hashlib

            results["parts"]["memory_store"] = {
                "path": str(snap),
                "sha256": _hashlib.sha256(data).hexdigest(),
                "byte_size": len(data),
                "verified": True,
            }
        durable = getattr(self, "_durable_audit", None)
        if durable is not None:
            results["parts"]["audit_trail"] = dict(
                durable.backup(dest / "memory_audit_trail.sqlite3")
            )
        if not results["parts"]:
            results["verified"] = False
            results["note"] = "non-durable backend: nothing durable to back up"
        return results


_SERVICE: Optional[ResearchMemoryService] = None
_SERVICE_LOCK = threading.Lock()


def get_research_memory_service() -> ResearchMemoryService:
    """Settings-driven factory (cached once per process).

    Default: the DURABLE backend on the real application path. A missing key
    (headless/CI without the env override and without an OS keyring) yields a
    cached REFUSAL posture — the honest fail-closed surface state, never a
    silent downgrade to an unencrypted or in-memory store.
    """
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is not None:
            return _SERVICE
        settings = get_settings()
        backend = (settings.research_memory_backend or "sqlite").strip().lower()
        if backend == "memory":
            # explicit unit-test choice; honesty requires the non-durable note
            service = ResearchMemoryService(
                backend_label="memory",
                store=AuditedResearchMemoryStore(
                    InMemoryResearchMemoryStore(),
                    actor="runtime",
                    authorization_context="L0-internal",
                    now_utc=lambda: datetime.now(timezone.utc),
                ),
                audit_trail=MemoryAccessAuditTrail(),
            )
            service.persistence_note = (
                "حافظه پژوهش فرایند-محلی و غیرماندگار است ( انتخاب صریح تست واحد)"
            )
            _SERVICE = service
            return _SERVICE
        if backend != "sqlite":
            _SERVICE = ResearchMemoryService(
                backend_label=backend,
                store=None,
                audit_trail=None,
                refused_reason=f"unknown_research_memory_backend:{backend}",
            )
            return _SERVICE
        # DURABLE sqlite path
        raw_dir = (settings.research_memory_db_dir or "").strip()
        directory = Path(raw_dir) if raw_dir else (DATA_DIR / "research_memory")
        try:
            key_provider = select_key_provider()
            key = key_provider()  # fail-closed without env/keyring (D4)
        except ValueError as exc:
            _SERVICE = ResearchMemoryService(
                backend_label="sqlite",
                store=None,
                audit_trail=None,
                refused_reason=str(exc) or "research_memory_key_invalid",
            )
            return _SERVICE
        try:
            mem_store = SqliteWalResearchMemoryStore(
                directory=directory, key_provider=lambda: key
            )
            audit_store = DurableMemoryAccessAuditTrail(
                db_path=directory / "memory_audit_trail.sqlite3"
            )
            audit_view = _DurableAuditTrailView(audit_store)
            audited = AuditedResearchMemoryStore(
                mem_store,
                actor="runtime",
                authorization_context="L0-internal",
                trail=audit_view,  # type: ignore[arg-type]
                now_utc=lambda: datetime.now(timezone.utc),
            )
        except (MemoryAuditStoreError, ValueError) as exc:
            _SERVICE = ResearchMemoryService(
                backend_label="sqlite",
                store=None,
                audit_trail=None,
                refused_reason=str(exc),
            )
            return _SERVICE
        service = ResearchMemoryService(
            backend_label="sqlite",
            store=audited,
            audit_trail=audit_view,
            db_path=str(directory / "research_memory.sqlite3"),
            audit_db_path=str(directory / "memory_audit_trail.sqlite3"),
        )
        service._durable_audit = audit_store  # type: ignore[attr-defined]
        service._memory_store = mem_store  # type: ignore[attr-defined]
        _SERVICE = service
        return _SERVICE


def reset_research_memory_service_cache() -> None:
    """Test hook: drop the cached service (env changes take effect)."""
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is not None:
            try:
                durable = getattr(_SERVICE, "_durable_audit", None)
                if durable is not None:
                    durable.close()
                mem = getattr(_SERVICE, "_memory_store", None)
                if mem is not None and hasattr(mem, "close"):
                    mem.close()
            except Exception:  # pragma: no cover - best-effort close
                pass
        _SERVICE = None
