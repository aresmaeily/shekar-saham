"""user_indicator_store.py — MASTER-RADAR directive §B4 (WAVE-B).

Installation & lifecycle manager for UIDL-1 user indicators. Like
:mod:`indicator_manager` this is a *metadata state machine over compiled
programs*: the ONLY executable content is the UIDL-1 DSL source, and the
ONLY execution path in the entire product is the RSL-1 interpreter inside
:mod:`app.engines.strategy_dsl` (no eval/exec/compile, no dynamic import,
no network, no clock — persistence is the caller's concern via
:func:`export_package` / :func:`import_package`).

Guarantees (directive §4.3):

* ids live in the reserved ``user.dsl.`` namespace; the shipped builtin
  catalog (``builtin.*``) can never collide.
* Every record carries a SHA-256 checksum over the canonical JSON of its
  definition fields (everything except ``checksum``/``enabled``), verified
  on import — a tamper-evidence seal, not obfuscation.
* Import re-COMPILES every source through ``compile_indicator_source``
  before storing anything: a package that does not parse/validate under the
  current UIDL-1 rules is rejected wholesale (fail closed, never trusted).
* Size budgets mirror the indicator package policy: max 256 KiB serialized
  package, max 64 entries; DSL source budget is enforced by the compiler
  (``BUDGET_SOURCE_LEN``).
* Every rejection is a typed result code; raw pydantic/DSL errors never
  leak to callers.
* Imported/installed entries start DISABLED; enabling is an explicit
  operator action (fail-closed default).
* Versioning: semver X.Y.Z; a same-id reinstall requires a strictly
  greater version AND ``allow_upgrade=True``; upgrades stay disabled.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from app.engines.indicator_catalog import parse_semver
from app.engines.indicator_manager import (
    BUDGET_ENTRIES,
    BUDGET_PACKAGE_SIZE,
    canonical_json,
    scan_forbidden_keys,
)
from app.engines.strategy_dsl.errors import DSLError
from app.engines.strategy_dsl.indicator_program import (
    UIDL_VERSION,
    IndicatorProgram,
    compile_indicator_source,
    validation_advisories,
)

UIDL_PACKAGE_VERSION = "UIDL-PKG-1"
USER_DSL_PREFIX = "user.dsl."


def _valid_slug(slug: str) -> bool:
    """Strict slug check — deliberately regex-free (mirrors
    indicator_catalog.parse_semver: no ``re.compile`` in this module)."""
    if not slug or len(slug) > 32:
        return False
    allowed = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")
    return all(c in allowed for c in slug)


def _sanitize(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:3]:
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{err.get('type', 'invalid')}@{loc}")
    return ("; ".join(parts) or "invalid document")[:240]


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]", "_", name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:32]


def record_checksum(record: dict) -> str:
    """SHA-256 over the canonical JSON of definition fields (see module doc)."""
    excluded = ("checksum", "enabled")
    payload = {k: v for k, v in record.items() if k not in excluded}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class UserIndicatorRecord(BaseModel):
    """One installed UIDL-1 indicator (metadata + the compiled source)."""

    model_config = {"extra": "forbid"}

    id: str
    name: str
    name_fa: str = ""
    author: str = Field(default="operator", max_length=64)
    dsl_version: str
    version: str
    source: str
    source_digest: str
    inputs: Dict[str, float]
    plots: List[Dict[str, Any]]  # [{name, warmup_bars}]
    warmup_bars: int
    declarations: Dict[str, Any]
    checksum: str = ""
    enabled: bool = False


class UserRejection(BaseModel):
    id: str
    code: str
    detail: str = ""


class UserInstallReport(BaseModel):
    ok: bool
    installed: int = 0
    rejected: List[UserRejection] = Field(default_factory=list)
    id: str = ""
    checksum: str = ""
    manifest_digest: str = ""


class UserOpResult(BaseModel):
    ok: bool
    code: str = "OK"
    detail: str = ""
    manifest_digest: str = ""


class UserIndicatorStore:
    """In-memory installation & lifecycle manager (persistence = caller)."""

    def __init__(self) -> None:
        self._records: Dict[str, UserIndicatorRecord] = {}

    # -- introspection ------------------------------------------------------
    def installed_ids(self) -> List[str]:
        return sorted(self._records)

    def is_installed(self, indicator_id: str) -> bool:
        return indicator_id in self._records

    def is_enabled(self, indicator_id: str) -> Optional[bool]:
        rec = self._records.get(indicator_id)
        return None if rec is None else rec.enabled

    def get_record(self, indicator_id: str) -> Optional[UserIndicatorRecord]:
        rec = self._records.get(indicator_id)
        return None if rec is None else rec.model_copy(deep=True)

    def manifest_digest(self) -> str:
        """Deterministic digest over the whole installed state."""
        payload = [
            {
                "id": r.id,
                "version": r.version,
                "checksum": r.checksum,
                "enabled": r.enabled,
            }
            for r in sorted(self._records.values(), key=lambda x: x.id)
        ]
        return hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest()

    # -- compilation --------------------------------------------------------
    @staticmethod
    def _id_for(program: IndicatorProgram) -> str:
        slug = _slugify(program.name)
        if not _valid_slug(slug):
            return USER_DSL_PREFIX + "indicator"
        return USER_DSL_PREFIX + slug

    @classmethod
    def _record_from_program(
        cls,
        program: IndicatorProgram,
        *,
        version: str,
        name_fa: str,
        author: str,
        enabled: bool,
    ) -> UserIndicatorRecord:
        record = {
            "id": cls._id_for(program),
            "name": program.name,
            "name_fa": name_fa,
            "author": author,
            "dsl_version": UIDL_VERSION,
            "version": version,
            "source": program.source,
            "source_digest": program.source_digest,
            "inputs": {k: float(v) for k, v in program.inputs.items()},
            "plots": [
                {"name": p.name, "warmup_bars": int(p.warmup_bars)}
                for p in program.plots
            ],
            "warmup_bars": int(program.warmup_bars),
            "declarations": {
                "repaint": "NONE_DECLARED",
                "lookahead_declared": False,
                "lookahead_enforced": "ref offsets >= 0 (compile-time refusal)",
                "missing_data": "WARMUP_ZERO",
                "advisories": validation_advisories(program),
            },
            "enabled": enabled,
        }
        record["checksum"] = record_checksum(record)
        return UserIndicatorRecord.model_validate(record)

    # -- installation -------------------------------------------------------
    def install(
        self,
        source: str,
        *,
        version: str = "1.0.0",
        name_fa: str = "",
        author: str = "operator",
        allow_upgrade: bool = False,
    ) -> UserInstallReport:
        """Compile + validate + install one UIDL-1 source (disabled)."""
        if not isinstance(source, str) or not source.strip():
            return UserInstallReport(
                ok=False,
                rejected=[UserRejection(id="", code="EMPTY_SOURCE", detail="source is empty")],
            )
        if not isinstance(version, str) or parse_semver(version) is None:
            return UserInstallReport(
                ok=False,
                rejected=[
                    UserRejection(
                        id="",
                        code="BAD_VERSION",
                        detail="version must be semver X.Y.Z",
                    )
                ],
            )
        semver = parse_semver(version)
        try:
            program = compile_indicator_source(source)
        except DSLError as exc:
            return UserInstallReport(
                ok=False,
                rejected=[
                    UserRejection(
                        id="",
                        code=f"DSL_{type(exc).__name__}",
                        detail=str(getattr(exc, "code", "")) + ": " + str(exc)[:200],
                    )
                ],
            )
        try:
            record = self._record_from_program(
                program, version=version, name_fa=name_fa, author=author, enabled=False
            )
        except ValidationError as exc:
            return UserInstallReport(
                ok=False,
                rejected=[UserRejection(id="", code="SCHEMA_INVALID", detail=_sanitize(exc))],
            )

        rid = record.id
        existing = self._records.get(rid)
        if existing is not None:
            cur = parse_semver(existing.version)
            greater = cur is not None and semver > cur
            if not greater or not allow_upgrade:
                return UserInstallReport(
                    ok=False,
                    manifest_digest=self.manifest_digest(),
                    rejected=[
                        UserRejection(
                            id=rid,
                            code="DUPLICATE_ID",
                            detail=(
                                f"installed at {existing.version}; incoming {version}; "
                                "policy: same/lower versions always rejected, higher "
                                "needs allow_upgrade"
                            ),
                        )
                    ],
                )
        self._records[rid] = record
        return UserInstallReport(
            ok=True,
            installed=1,
            id=rid,
            checksum=record.checksum,
            manifest_digest=self.manifest_digest(),
        )

    # -- lifecycle ----------------------------------------------------------
    def uninstall(self, indicator_id: str) -> UserOpResult:
        if indicator_id not in self._records:
            return UserOpResult(
                ok=False, code="NOT_INSTALLED", detail=indicator_id,
                manifest_digest=self.manifest_digest(),
            )
        del self._records[indicator_id]
        return UserOpResult(ok=True, code="REMOVED", manifest_digest=self.manifest_digest())

    def set_enabled(self, indicator_id: str, enabled: bool) -> UserOpResult:
        rec = self._records.get(indicator_id)
        if rec is None:
            return UserOpResult(
                ok=False, code="NOT_INSTALLED", detail=indicator_id,
                manifest_digest=self.manifest_digest(),
            )
        rec.enabled = bool(enabled)
        return UserOpResult(
            ok=True,
            code="ENABLED" if enabled else "DISABLED",
            manifest_digest=self.manifest_digest(),
        )

    # -- package export / import -------------------------------------------
    def export_package(self) -> dict:
        """Versioned JSON document over every installed record."""
        entries = []
        for rec in sorted(self._records.values(), key=lambda r: r.id):
            payload = rec.model_dump(mode="json")
            payload["checksum"] = record_checksum(payload)
            entries.append(payload)
        return {"package_version": UIDL_PACKAGE_VERSION, "indicators": entries}

    def import_package(self, doc: Any, *, allow_upgrade: bool = False) -> UserInstallReport:
        """Deep-validate, re-compile and install a package document.

        Every entry is re-compiled under the CURRENT UIDL-1 rules before it
        is stored — a package is data until this store accepts it, and a
        source that no longer compiles fails closed.
        """
        rejected: List[UserRejection] = []
        if not isinstance(doc, dict):
            return UserInstallReport(
                ok=False,
                rejected=[UserRejection(id="", code="SCHEMA_INVALID", detail="document must be a JSON object")],
            )
        try:
            size = len(canonical_json(doc).encode("utf-8"))
        except (TypeError, ValueError):
            return UserInstallReport(
                ok=False,
                rejected=[UserRejection(id="", code="SCHEMA_INVALID", detail="document is not JSON-serializable")],
            )
        if size > BUDGET_PACKAGE_SIZE:
            return UserInstallReport(
                ok=False,
                rejected=[
                    UserRejection(
                        id="",
                        code="BUDGET_PACKAGE_SIZE",
                        detail=f"serialized package is {size} bytes > budget {BUDGET_PACKAGE_SIZE}",
                    )
                ],
            )
        bad = scan_forbidden_keys(doc)
        if bad is not None:
            return UserInstallReport(
                ok=False,
                rejected=[UserRejection(id="", code="FORBIDDEN_FIELD", detail=f"forbidden key at {bad}")],
            )
        if doc.get("package_version") != UIDL_PACKAGE_VERSION:
            return UserInstallReport(
                ok=False,
                rejected=[
                    UserRejection(
                        id="",
                        code="SCHEMA_INVALID",
                        detail=f"package_version must be {UIDL_PACKAGE_VERSION!r}",
                    )
                ],
            )
        raw_entries = doc.get("indicators")
        if not isinstance(raw_entries, list):
            return UserInstallReport(
                ok=False,
                rejected=[UserRejection(id="", code="SCHEMA_INVALID", detail="'indicators' must be a list")],
            )
        if len(raw_entries) > BUDGET_ENTRIES:
            return UserInstallReport(
                ok=False,
                rejected=[
                    UserRejection(
                        id="",
                        code="BUDGET_ENTRIES",
                        detail=f"package declares {len(raw_entries)} entries > budget {BUDGET_ENTRIES}",
                    )
                ],
            )

        installed = 0
        for raw in raw_entries:
            if not isinstance(raw, dict):
                rejected.append(UserRejection(id="", code="SCHEMA_INVALID", detail="entry must be a JSON object"))
                continue
            rid = raw.get("id")
            if not isinstance(rid, str) or not rid.startswith(USER_DSL_PREFIX):
                rejected.append(
                    UserRejection(
                        id=str(rid or ""),
                        code="ID_NAMESPACE",
                        detail=f"ids must start with {USER_DSL_PREFIX!r}",
                    )
                )
                continue
            provided = raw.get("checksum")
            expected = record_checksum(raw)
            if not isinstance(provided, str) or provided != expected:
                rejected.append(UserRejection(id=rid, code="CHECKSUM_MISMATCH", detail="declared checksum does not match content"))
                continue
            source = raw.get("source")
            if not isinstance(source, str):
                rejected.append(UserRejection(id=rid, code="SCHEMA_INVALID", detail="'source' must be a string"))
                continue
            report = self.install(
                source,
                version=str(raw.get("version") or "1.0.0"),
                name_fa=str(raw.get("name_fa") or ""),
                author=str(raw.get("author") or "operator")[:64],
                allow_upgrade=allow_upgrade,
            )
            if report.ok:
                installed += 1
            else:
                rejected.extend(report.rejected)
        return UserInstallReport(
            ok=len(rejected) == 0,
            installed=installed,
            rejected=rejected,
            manifest_digest=self.manifest_digest(),
        )
