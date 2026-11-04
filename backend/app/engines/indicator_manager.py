"""indicator_manager.py — PKG-F (MASTER-RADAR directive §B4, Wave 3).

Installation & lifecycle manager for indicator packages.  This is a *metadata
state machine only*: an imported package is a validated JSON document and is
NEVER executed.  There is no eval/exec/compile, no dynamic import of anything
declared inside a package, and no network / filesystem / clock access —
persistence is the caller's concern via :meth:`export_manifest` /
:meth:`import_manifest`.

Guarantees (directive §B4):

* ``builtin.*`` ids are RESERVED — imported entries must use ``user.*``.
* Every entry carries a SHA-256 checksum over the canonical JSON of its
  *definition* fields (everything except the ``checksum`` key itself and the
  runtime-context fields ``source`` / ``enabled``, so lifecycle state changes
  never invalidate content integrity); the manager computes it on
  export/install and verifies it on import.
* Any dict key containing ``__`` or named one of
  {``code``, ``script``, ``exec``, ``eval``, ``lambda``, ``compile``} — at ANY
  nesting depth — is rejected (``FORBIDDEN_FIELD``).
* Permissions are whitelisted to {``series:read``, ``chart:overlay``,
  ``chart:pane``}; series inputs to the OHLCV set.
* Size budgets: max 256 KiB serialized package (``BUDGET_PACKAGE_SIZE``) and
  max 64 entries (``BUDGET_ENTRIES``).
* Every rejection is a typed result code (``InstallReport`` / ``OpResult``);
  raw pydantic errors never leak to callers.
* Imported entries are installed disabled; the operator must enable them
  explicitly, and enabling is fail-closed on missing series inputs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, FrozenSet, Iterable, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.engines.indicator_catalog import (
    BUILT_IN_CATALOG,
    IndicatorCategory,
    IndicatorParamSpec,
    catalog_version,
    parse_semver,
)

# ---------------------------------------------------------------------------
# Constants / budgets
# ---------------------------------------------------------------------------
PACKAGE_VERSION = "IP-1"
MANIFEST_VERSION = "IM-1"

BUDGET_PACKAGE_SIZE = 256 * 1024  # max serialized package size in bytes
BUDGET_ENTRIES = 64  # max entries per package

SOURCE_BUILTIN = "BUILTIN"
SOURCE_IMPORTED = "IMPORTED_SAFE_JSON"

BUILTIN_ID_PREFIX = "builtin."
USER_ID_PREFIX = "user."

ALLOWED_PERMISSIONS: FrozenSet[str] = frozenset(
    {"series:read", "chart:overlay", "chart:pane"}
)
ALLOWED_SERIES: FrozenSet[str] = frozenset({"open", "high", "low", "close", "volume"})

# Any dict key that could smuggle executable content is rejected (§B4).
FORBIDDEN_KEY_NAMES: FrozenSet[str] = frozenset(
    {"code", "script", "exec", "eval", "lambda", "compile"}
)

# Documented default-enable set at first construction: the conservative
# trend/volatility/momentum basics trusted for immediate charting.  All other
# built-ins (oscillators, volume, breadth, structure) start disabled and must
# be enabled explicitly by the operator with the series they can supply.
DEFAULT_ENABLED_BUILT_INS: FrozenSet[str] = frozenset(
    {
        "builtin.sma",
        "builtin.ema",
        "builtin.rsi",
        "builtin.macd",
        "builtin.bollinger",
        "builtin.atr",
    }
)

_SEMVER_HINT = "version must be semver X.Y.Z"


# ---------------------------------------------------------------------------
# Canonical JSON / checksum / key scanner
# ---------------------------------------------------------------------------
def canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization used for checksums and digests."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def entry_checksum(entry: dict) -> str:
    """SHA-256 over the canonical JSON of the entry's *definition* fields.

    Excluded: the ``checksum`` key itself plus the runtime-context fields
    ``source`` / ``enabled`` — the checksum is a tamper-evidence seal over the
    indicator definition, not over its installation lifecycle state.
    """
    excluded = ("checksum", "source", "enabled")
    payload = {k: v for k, v in entry.items() if k not in excluded}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def scan_forbidden_keys(obj: Any, path: str = "$") -> Optional[str]:
    """Recursively locate the first forbidden dict key; return its path or None.

    A key is forbidden when it contains ``__`` anywhere or equals (case
    sensitive) one of ``FORBIDDEN_KEY_NAMES``.  Non-string keys are treated as
    forbidden as well.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str) or "__" in k or k in FORBIDDEN_KEY_NAMES:
                return f"{path}.{k!r}"
            sub = scan_forbidden_keys(v, f"{path}.{k}")
            if sub is not None:
                return sub
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            sub = scan_forbidden_keys(item, f"{path}[{idx}]")
            if sub is not None:
                return sub
    return None


def _sanitize_pydantic_error(exc: ValidationError) -> str:
    """Compact, sanitized summary of a pydantic error (no raw dump leakage)."""
    parts = []
    for err in exc.errors()[:3]:
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{err.get('type', 'invalid')}@{loc}")
    summary = "; ".join(parts) if parts else "invalid document"
    return summary[:240]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class PackageEntry(BaseModel):
    """One indicator as carried inside a package / manifest (data-only)."""

    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1)
    name_en: str = Field(min_length=1)
    name_fa: str = Field(min_length=1)
    category: IndicatorCategory
    version: str
    author: str = Field(default="unknown", max_length=64)
    math_definition: str = Field(max_length=2000)
    inputs: List[IndicatorParamSpec] = Field(default_factory=list)
    warmup_bars: int = Field(ge=0)
    series_inputs: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=lambda: ["series:read"])
    checksum: str = ""
    source: str = SOURCE_IMPORTED
    enabled: bool = False

    @field_validator("version")
    @classmethod
    def _semver(cls, v: str) -> str:
        if parse_semver(v) is None:
            raise ValueError(_SEMVER_HINT)
        return v

    @field_validator("source")
    @classmethod
    def _known_source(cls, v: str) -> str:
        if v not in (SOURCE_BUILTIN, SOURCE_IMPORTED):
            raise ValueError(f"source must be {SOURCE_BUILTIN} or {SOURCE_IMPORTED}")
        return v


class IndicatorPackage(BaseModel):
    """Importable/exportable JSON document: a versioned set of entries."""

    model_config = {"extra": "forbid"}

    package_version: str
    indicators: List[PackageEntry] = Field(default_factory=list)

    @field_validator("package_version")
    @classmethod
    def _version(cls, v: str) -> str:
        if v != PACKAGE_VERSION:
            raise ValueError(f"package_version must be {PACKAGE_VERSION!r}")
        return v


class Rejection(BaseModel):
    """One typed rejection inside an :class:`InstallReport`."""

    id: str
    code: str
    detail: str = ""


class InstallReport(BaseModel):
    """Typed result of :meth:`IndicatorManager.install_package`."""

    ok: bool
    installed: int = 0
    rejected: List[Rejection] = Field(default_factory=list)


class OpResult(BaseModel):
    """Typed result for lifecycle operations (enable/disable/remove/import)."""

    ok: bool
    code: str = "OK"
    detail: str = ""


class TemplateEntry(BaseModel):
    """Composed metadata summary for one id inside a template."""

    id: str
    name_en: str
    name_fa: str
    category: str
    warmup_bars: int
    permissions: List[str]


class TemplateValidation(BaseModel):
    """Typed result of :meth:`IndicatorManager.template_compose`."""

    ok: bool
    code: str = "OK"
    detail: str = ""
    ids: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    total_warmup: int = 0
    indicators: List[TemplateEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class IndicatorManager:
    """In-memory installation & lifecycle manager (persistence = caller)."""

    def __init__(self) -> None:
        self._entries: Dict[str, PackageEntry] = {}
        for spec in BUILT_IN_CATALOG:
            entry = PackageEntry(
                id=spec.id,
                name_en=spec.name_en,
                name_fa=spec.name_fa,
                category=spec.category,
                version=spec.version,
                author=spec.author,
                math_definition=spec.math_definition,
                inputs=[inp.model_copy() for inp in spec.inputs],
                warmup_bars=spec.warmup_bars,
                series_inputs=list(spec.series_inputs),
                permissions=list(spec.permissions),
                checksum="",
                source=SOURCE_BUILTIN,
                enabled=spec.id in DEFAULT_ENABLED_BUILT_INS,
            )
            payload = entry.model_dump(mode="json")
            entry.checksum = entry_checksum(payload)
            self._entries[entry.id] = entry

    # -- introspection ------------------------------------------------------
    def installed_ids(self) -> List[str]:
        """All installed ids, sorted for determinism."""
        return sorted(self._entries)

    def is_installed(self, indicator_id: str) -> bool:
        return indicator_id in self._entries

    def is_enabled(self, indicator_id: str) -> Optional[bool]:
        entry = self._entries.get(indicator_id)
        return None if entry is None else entry.enabled

    def get_entry(self, indicator_id: str) -> Optional[PackageEntry]:
        """Return a copy of the installed entry metadata, or ``None``."""
        entry = self._entries.get(indicator_id)
        return None if entry is None else entry.model_copy(deep=True)

    # -- installation -------------------------------------------------------
    def install_package(self, doc: dict, allow_upgrade: bool = False) -> InstallReport:
        """Deep-validate and install an imported package document.

        Policy notes:
        * ``builtin.*`` ids are rejected (``RESERVED_ID``); ids must start with
          ``user.`` (``ID_NAMESPACE``).
        * A duplicate ``user.*`` id is rejected (``DUPLICATE_ID``) unless the
          incoming version is strictly greater AND ``allow_upgrade=True`` —
          the upgrade replaces the installed entry and stays disabled.
        * On success entries are installed with ``enabled=False``; the caller
          must :meth:`enable` them explicitly.
        """
        rejected: List[Rejection] = []

        def _reject(eid: str, code: str, detail: str) -> None:
            rejected.append(Rejection(id=eid, code=code, detail=detail))

        if not isinstance(doc, dict):
            return InstallReport(
                ok=False,
                installed=0,
                rejected=[Rejection(id="", code="SCHEMA_INVALID", detail="document must be a JSON object")],
            )

        # 1. size budget (before schema work — an oversized blob is rejected as-is)
        try:
            size = len(canonical_json(doc).encode("utf-8"))
        except (TypeError, ValueError):
            return InstallReport(
                ok=False,
                installed=0,
                rejected=[Rejection(id="", code="SCHEMA_INVALID", detail="document is not JSON-serializable")],
            )
        if size > BUDGET_PACKAGE_SIZE:
            _reject(
                "",
                "BUDGET_PACKAGE_SIZE",
                f"serialized package is {size} bytes > budget {BUDGET_PACKAGE_SIZE}",
            )
            return InstallReport(ok=False, installed=0, rejected=rejected)

        # 2. forbidden fields at ANY depth (§B4: no code-carrying fields)
        bad_path = scan_forbidden_keys(doc)
        if bad_path is not None:
            _reject("", "FORBIDDEN_FIELD", f"forbidden key at {bad_path}")
            return InstallReport(ok=False, installed=0, rejected=rejected)

        # 3. top-level shape
        if doc.get("package_version") != PACKAGE_VERSION:
            _reject("", "SCHEMA_INVALID", f"package_version must be {PACKAGE_VERSION!r}")
            return InstallReport(ok=False, installed=0, rejected=rejected)
        raw_entries = doc.get("indicators")
        if not isinstance(raw_entries, list):
            _reject("", "SCHEMA_INVALID", "'indicators' must be a list")
            return InstallReport(ok=False, installed=0, rejected=rejected)
        if len(raw_entries) > BUDGET_ENTRIES:
            _reject(
                "",
                "BUDGET_ENTRIES",
                f"package declares {len(raw_entries)} entries > budget {BUDGET_ENTRIES}",
            )
            return InstallReport(ok=False, installed=0, rejected=rejected)

        installed = 0
        for raw in raw_entries:
            if not isinstance(raw, dict):
                _reject("", "SCHEMA_INVALID", "entry must be a JSON object")
                continue
            eid = raw.get("id")
            if not isinstance(eid, str) or not eid:
                _reject("", "SCHEMA_INVALID", "entry is missing a non-empty string 'id'")
                continue

            if eid.startswith(BUILTIN_ID_PREFIX):
                _reject(eid, "RESERVED_ID", "'builtin.*' ids are reserved for the shipped catalog")
                continue
            if not eid.startswith(USER_ID_PREFIX) or len(eid) <= len(USER_ID_PREFIX):
                _reject(eid, "ID_NAMESPACE", f"imported indicator ids must start with '{USER_ID_PREFIX}'")
                continue

            perms = raw.get("permissions", ["series:read"])
            if not isinstance(perms, list) or any(p not in ALLOWED_PERMISSIONS for p in perms):
                _reject(
                    eid,
                    "PERMISSION_NOT_WHITELISTED",
                    f"allowed permissions: {sorted(ALLOWED_PERMISSIONS)}",
                )
                continue

            series = raw.get("series_inputs", [])
            if not isinstance(series, list) or any(s not in ALLOWED_SERIES for s in series):
                _reject(
                    eid,
                    "SERIES_INPUT_UNKNOWN",
                    f"series_inputs must be a subset of {sorted(ALLOWED_SERIES)}",
                )
                continue

            provided = raw.get("checksum")
            expected = entry_checksum(raw)
            if not isinstance(provided, str) or provided != expected:
                _reject(eid, "CHECKSUM_MISMATCH", "recomputed checksum does not match the declared one")
                continue

            staged = dict(raw)
            staged["source"] = SOURCE_IMPORTED
            staged["enabled"] = False
            try:
                entry = PackageEntry.model_validate(staged)
            except ValidationError as exc:
                _reject(eid, "SCHEMA_INVALID", _sanitize_pydantic_error(exc))
                continue

            # Re-stamp the checksum over the normalized (canonical) form so
            # export/import round-trips stay verifiable even where pydantic
            # normalizes value representations (e.g. int -> float coercion).
            # The incoming transport checksum was already verified above.
            entry.checksum = entry_checksum(entry.model_dump(mode="json"))

            existing = self._entries.get(eid)
            if existing is not None:
                cur = parse_semver(existing.version)
                new = parse_semver(entry.version)
                greater = cur is not None and new is not None and new > cur
                if not greater or not allow_upgrade:
                    _reject(
                        eid,
                        "DUPLICATE_ID",
                        (
                            f"id already installed at version {existing.version}; incoming "
                            f"{entry.version}; policy: same/lower versions are always rejected, "
                            "a strictly greater version requires allow_upgrade=True"
                        ),
                    )
                    continue

            self._entries[eid] = entry
            installed += 1

        return InstallReport(ok=len(rejected) == 0, installed=installed, rejected=rejected)

    # -- lifecycle ----------------------------------------------------------
    def enable(
        self, indicator_id: str, available_series: FrozenSet[str] = frozenset()
    ) -> OpResult:
        """Enable an installed indicator (fail-closed on missing series).

        ``available_series`` is the caller's context (e.g. ``frozenset({"open",
        "high", "low", "close", "volume"})``).  Enabling an indicator whose
        ``series_inputs`` are not fully available is rejected with
        ``MISSING_SERIES_INPUT``; the default empty set therefore fails closed.
        """
        entry = self._entries.get(indicator_id)
        if entry is None:
            return OpResult(ok=False, code="UNKNOWN_ID", detail=f"no installed indicator {indicator_id!r}")
        missing = sorted(s for s in entry.series_inputs if s not in available_series)
        if missing:
            return OpResult(
                ok=False,
                code="MISSING_SERIES_INPUT",
                detail=(
                    f"{indicator_id} requires series {sorted(entry.series_inputs)}; "
                    f"missing {missing} (fail-closed)"
                ),
            )
        entry.enabled = True
        return OpResult(ok=True, code="OK", detail=f"{indicator_id} enabled")

    def disable(self, indicator_id: str) -> OpResult:
        """Disable an installed indicator (idempotent)."""
        entry = self._entries.get(indicator_id)
        if entry is None:
            return OpResult(ok=False, code="UNKNOWN_ID", detail=f"no installed indicator {indicator_id!r}")
        entry.enabled = False
        return OpResult(ok=True, code="OK", detail=f"{indicator_id} disabled")

    def remove(self, indicator_id: str) -> OpResult:
        """Remove an installed ``user.*`` entry; built-ins are protected."""
        entry = self._entries.get(indicator_id)
        if entry is None:
            return OpResult(ok=False, code="UNKNOWN_ID", detail=f"no installed indicator {indicator_id!r}")
        if indicator_id.startswith(BUILTIN_ID_PREFIX):
            return OpResult(
                ok=False,
                code="REMOVE_BUILTIN_FORBIDDEN",
                detail="built-in entries are part of the shipped catalog and cannot be removed",
            )
        del self._entries[indicator_id]
        return OpResult(ok=True, code="OK", detail=f"{indicator_id} removed")

    def version_check(self, indicator_id: str, needed: str) -> bool:
        """Compatibility check: major equal AND installed minor >= needed minor.

        Policy (documented): the major version must match exactly (breaking
        changes), the installed minor must be greater than or equal to the
        requested one, and the patch level is ignored.  Unknown ids or
        unparseable versions fail closed to ``False``.
        """
        entry = self._entries.get(indicator_id)
        if entry is None:
            return False
        cur = parse_semver(entry.version)
        req = parse_semver(needed)
        if cur is None or req is None:
            return False
        return cur[0] == req[0] and cur[1] >= req[1]

    # -- templates ----------------------------------------------------------
    def template_compose(self, template: List[str]) -> TemplateValidation:
        """Compose a chart template from installed ids (metadata only).

        Validates: all ids installed, no duplicates, combined permissions
        within the whitelist; the composed warm-up is the MAXIMUM of the
        members' warm-ups (a template is only valid where every member is).
        """
        if not isinstance(template, list) or any(not isinstance(t, str) for t in template):
            return TemplateValidation(ok=False, code="SCHEMA_INVALID", detail="template must be a list of ids")
        seen: set[str] = set()
        for tid in template:
            if tid not in self._entries:
                return TemplateValidation(
                    ok=False,
                    code="UNKNOWN_ID",
                    detail=f"template references unknown indicator {tid!r}",
                )
            if tid in seen:
                return TemplateValidation(
                    ok=False,
                    code="DUPLICATE_ID",
                    detail=f"duplicate id {tid!r} in template",
                )
            seen.add(tid)
        entries = [self._entries[tid] for tid in template]
        combined = sorted({p for e in entries for p in e.permissions})
        bad = [p for p in combined if p not in ALLOWED_PERMISSIONS]
        if bad:
            return TemplateValidation(
                ok=False,
                code="PERMISSION_NOT_WHITELISTED",
                detail=f"combined permissions outside whitelist: {bad}",
            )
        total_warmup = max((e.warmup_bars for e in entries), default=0)
        return TemplateValidation(
            ok=True,
            code="OK",
            detail=f"composed {len(entries)} indicator(s)",
            ids=list(template),
            permissions=combined,
            total_warmup=total_warmup,
            indicators=[
                TemplateEntry(
                    id=e.id,
                    name_en=e.name_en,
                    name_fa=e.name_fa,
                    category=e.category.value,
                    warmup_bars=e.warmup_bars,
                    permissions=list(e.permissions),
                )
                for e in entries
            ],
        )

    # -- export / persistence ----------------------------------------------
    def export_package(self, ids: Iterable[str]) -> dict:
        """Export the given installed ids as a re-validatable package document.

        The exported document is re-validated against :class:`IndicatorPackage`
        before returning (round-trip guard) and carries freshly recomputed
        checksums over exactly the exported payload (context fields ``source``
        / ``enabled`` are intentionally excluded — the importing manager
        re-stamps them).  Unknown ids raise ``ValueError``: exporting a
        non-installed id is a programmer error, not caller-supplied data.
        """
        id_list = list(ids)
        for iid in id_list:
            if iid not in self._entries:
                raise ValueError(f"export_package: unknown indicator id {iid!r}")
        docs: List[dict] = []
        for iid in id_list:
            entry = self._entries[iid]
            payload = {
                k: v
                for k, v in entry.model_dump(mode="json").items()
                if k not in ("checksum", "source", "enabled")
            }
            payload["checksum"] = entry_checksum(payload)
            docs.append(payload)
        package = {"package_version": PACKAGE_VERSION, "indicators": docs}
        IndicatorPackage.model_validate(package)  # internal invariant guard
        return package

    def export_manifest(self) -> dict:
        """Full-state snapshot for caller-managed persistence."""
        entries = [e.model_dump(mode="json") for e in self._sorted_entries()]
        return {
            "manifest_version": MANIFEST_VERSION,
            "catalog_version": catalog_version(),
            "entries": entries,
        }

    def import_manifest(self, doc: dict) -> OpResult:
        """Restore full state from a manifest snapshot (checksums verified)."""
        if not isinstance(doc, dict) or doc.get("manifest_version") != MANIFEST_VERSION:
            return OpResult(
                ok=False,
                code="MANIFEST_VERSION",
                detail=f"manifest_version must be {MANIFEST_VERSION!r}",
            )
        bad_path = scan_forbidden_keys(doc)
        if bad_path is not None:
            return OpResult(ok=False, code="FORBIDDEN_FIELD", detail=f"forbidden key at {bad_path}")
        raw_entries = doc.get("entries")
        if not isinstance(raw_entries, list):
            return OpResult(ok=False, code="SCHEMA_INVALID", detail="'entries' must be a list")
        restored: Dict[str, PackageEntry] = {}
        for raw in raw_entries:
            if not isinstance(raw, dict):
                return OpResult(ok=False, code="SCHEMA_INVALID", detail="entries must be JSON objects")
            eid = raw.get("id", "")
            provided = raw.get("checksum")
            if not isinstance(provided, str) or provided != entry_checksum(raw):
                return OpResult(
                    ok=False,
                    code="CHECKSUM_MISMATCH",
                    detail=f"checksum mismatch for entry {eid!r}",
                )
            try:
                entry = PackageEntry.model_validate(raw)
            except ValidationError as exc:
                return OpResult(ok=False, code="SCHEMA_INVALID", detail=_sanitize_pydantic_error(exc))
            restored[entry.id] = entry
        self._entries = restored
        return OpResult(ok=True, code="OK", detail=f"restored {len(restored)} entries")

    def manifest_digest(self) -> str:
        """SHA-256 over the canonical JSON of the full manager state."""
        state = {
            "manifest_version": MANIFEST_VERSION,
            "catalog_version": catalog_version(),
            "entries": [e.model_dump(mode="json") for e in self._sorted_entries()],
        }
        return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()

    # -- internals -----------------------------------------------------------
    def _sorted_entries(self) -> List[PackageEntry]:
        return [self._entries[k] for k in sorted(self._entries)]
