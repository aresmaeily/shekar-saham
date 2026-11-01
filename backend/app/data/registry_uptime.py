"""SourceRegistry ↔ provider-uptime folding adapter (coverage honesty).

P0/P1 scope (02_EXECUTION_ROADMAP_CURRENT_2026-10-02.md lines 133, 156, 168-169):
source registry + coverage/limitations report; coverage gaps and inaccessible
sources must be reported; source coverage, freshness, failure and
unresolved-conflict reporting. This module folds the runtime uptime counters
exposed by app/data/providers.py `MarketDataProvider.get_uptime_metrics()`
into source_registry.SourceDescriptor copies and produces an honest
source_registry.CoverageReport.

get_uptime_metrics() exact shape (providers.py:312-321) — cumulative integer
counters and booleans, NO timestamps:
{
  "tsetmc_success": int, "tsetmc_fail": int, "brsapi_success": int,
  "brsapi_fail": int, "mock_fallback": int,
  "total_fetches": int, "failed_fetches": int, "success_rate": float,
  "tsetmc_cb_open": bool, "brsapi_cb_open": bool,
}

Adapter key contract per descriptor source_id S:
- "{S}_success" / "{S}_fail"  → cumulative counters (int, non-negative)
- "{S}_cb_open"               → circuit-breaker flag (bool); an open breaker
  is the provider's own consecutive-failure signal and takes precedence
- "{S}_last_success_utc"      → OPTIONAL extension (datetime or ISO-8601
  string). get_uptime_metrics() carries no timestamps, so this adapter never
  fabricates one: last_success_utc moves only when the caller explicitly
  supplies the instant; otherwise it is carried through untouched.

Status vocabulary is source_registry's closed set (CONFIGURED / ACTIVE /
INACCESSIBLE / RETIRED) — honored exactly. There is NO 'live' concept in that
vocabulary and none is introduced here; nothing is ever marked live or
verified. Success is never invented: a source without a success signal keeps
its status (failures without an open breaker do not degrade it); RETIRED is
terminal and is never resurrected. last_failure_utc is never touched (no
failure instants exist in the metrics shape).

Contract/domain only: pure functions, no network, no provider calls, no clock
reads — now_utc is always injected.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from app.domain.evidence import ensure_utc
from app.domain.source_registry import CoverageReport, SourceDescriptor

__all__ = [
    "fold_uptime_into_descriptors",
    "coverage_report_from",
]

_SUCCESS_SUFFIX = "_success"
_FAIL_SUFFIX = "_fail"
_CB_SUFFIX = "_cb_open"
_LAST_SUCCESS_SUFFIX = "_last_success_utc"


def _counter(uptime_metrics: Mapping[str, Any], key: str) -> int:
    if key not in uptime_metrics:
        return 0
    value = uptime_metrics[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("uptime_counter_must_be_int")
    if value < 0:
        raise ValueError("uptime_counter_must_not_be_negative")
    return value


def _cb_flag(uptime_metrics: Mapping[str, Any], key: str) -> bool:
    if key not in uptime_metrics:
        return False
    value = uptime_metrics[key]
    if not isinstance(value, bool):
        raise ValueError("uptime_cb_flag_must_be_bool")
    return value


def _explicit_last_success(
    uptime_metrics: Mapping[str, Any], key: str, now_utc: datetime
) -> datetime | None:
    if key not in uptime_metrics:
        return None
    raw = uptime_metrics[key]
    if isinstance(raw, str):
        try:
            raw = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("uptime_last_success_must_be_timestamp") from exc
    if not isinstance(raw, datetime):
        raise ValueError("uptime_last_success_must_be_timestamp")
    stamp = ensure_utc(raw)
    if stamp > now_utc:
        raise ValueError("uptime_last_success_must_not_be_in_future")
    return stamp


def _validate_inputs(
    descriptors: Sequence[Any], uptime_metrics: Mapping[str, Any], now_utc: datetime
) -> None:
    if not isinstance(uptime_metrics, Mapping):
        raise ValueError("uptime_metrics_must_be_mapping")
    ensure_utc(now_utc)
    seen: set[str] = set()
    for descriptor in descriptors:
        if not isinstance(descriptor, SourceDescriptor):
            raise ValueError("descriptor_must_be_source_descriptor")
        if descriptor.source_id in seen:
            raise ValueError(f"duplicate_descriptor_source_id: {descriptor.source_id}")
        seen.add(descriptor.source_id)


def fold_uptime_into_descriptors(
    descriptors: Sequence[SourceDescriptor],
    uptime_metrics: Mapping[str, Any],
    *,
    now_utc: datetime,
) -> tuple[SourceDescriptor, ...]:
    """Fold provider uptime metrics into NEW frozen descriptors.

    Never mutates inputs: every changed source returns a fresh
    SourceDescriptor (model_copy); unchanged sources are returned as-is.
    Transitions (source_registry's closed vocabulary only):
    - "{S}_cb_open" true                → INACCESSIBLE (degraded state)
    - success counter > 0, breaker shut → ACTIVE (healthy)
    - otherwise                         → status carried through unchanged
    - RETIRED sources are terminal: returned untouched, never resurrected
    - a source with no metric keys at all is returned untouched: success is
      never invented from absence of evidence
    """
    _validate_inputs(descriptors, uptime_metrics, now_utc)
    now = ensure_utc(now_utc)
    folded: list[SourceDescriptor] = []
    for descriptor in descriptors:
        if descriptor.status == "RETIRED":
            folded.append(descriptor)
            continue
        source_id = descriptor.source_id
        success_key = f"{source_id}{_SUCCESS_SUFFIX}"
        has_any_key = any(
            f"{source_id}{suffix}" in uptime_metrics
            for suffix in (_SUCCESS_SUFFIX, _FAIL_SUFFIX, _CB_SUFFIX, _LAST_SUCCESS_SUFFIX)
        )
        if not has_any_key:
            folded.append(descriptor)
            continue
        success = _counter(uptime_metrics, success_key)
        cb_open = _cb_flag(uptime_metrics, f"{source_id}{_CB_SUFFIX}")
        last_success = _explicit_last_success(
            uptime_metrics, f"{source_id}{_LAST_SUCCESS_SUFFIX}", now
        )
        if cb_open:
            new_status = "INACCESSIBLE"
        elif success > 0:
            new_status = "ACTIVE"
        else:
            new_status = descriptor.status  # no success signal: never invent one
        update: dict[str, Any] = {}
        if new_status != descriptor.status:
            update["status"] = new_status
        if last_success is not None and last_success != descriptor.last_success_utc:
            update["last_success_utc"] = last_success
        folded.append(descriptor.model_copy(update=update) if update else descriptor)
    return tuple(folded)


def coverage_report_from(
    descriptors: Sequence[SourceDescriptor],
    uptime_metrics: Mapping[str, Any],
    *,
    now_utc: datetime,
    registry_version: int = 1,
    known_gaps: tuple[str, ...] = (),
) -> CoverageReport:
    """Build the honest CoverageReport (source_registry.CoverageReport verbatim).

    The fold runs first, so inaccessible / stale reflect the folded state.
    never_retrieved lists sources with NO retrieval evidence at all: no
    recorded last-success instant AND a zero success counter — a source whose
    counter proves successes but whose success instant is unknown is reported
    neither as never-retrieved nor as stale (nothing is claimed beyond the
    evidence). Staleness mirrors SourceRegistry.coverage_report: a source is
    stale when its last success is older than its declared freshness target.
    `universal_coverage_claimed` stays structurally False.
    `registry_version` must be supplied by registry-aware callers; the default
    1 marks the unversioned descriptor-only baseline.
    """
    now = ensure_utc(now_utc)
    folded = fold_uptime_into_descriptors(descriptors, uptime_metrics, now_utc=now)
    never: list[str] = []
    stale: list[str] = []
    for descriptor in folded:
        if descriptor.last_success_utc is not None:
            if (
                descriptor.freshness_target is not None
                and now - descriptor.last_success_utc > descriptor.freshness_target
            ):
                stale.append(descriptor.source_id)
            continue
        # No last-success timestamp is recorded. The success counter is the
        # only other retrieval evidence: a source whose counter proves at
        # least one success HAS been retrieved (its instant is merely
        # unknown, so no staleness claim is made either way); a source with
        # zero success signal is honestly never_retrieved.
        success = _counter(uptime_metrics, f"{descriptor.source_id}{_SUCCESS_SUFFIX}")
        if success == 0:
            never.append(descriptor.source_id)
    return CoverageReport(
        as_of_utc=now,
        registry_version=registry_version,
        total_configured=len(folded),
        active=len(tuple(d for d in folded if d.status == "ACTIVE")),
        inaccessible=tuple(d.source_id for d in folded if d.status == "INACCESSIBLE"),
        stale_sources=tuple(stale),
        never_retrieved=tuple(never),
        uncovered_source_classes=(),
        known_gaps=tuple(known_gaps),
    )
