"""Filter Intelligence and Self-Optimization service.

P3.41 implementation reuses the existing safe Filter DSL, Strategy adapter,
Backtest/Walk-Forward/Forward-Test primitives, P3.40 market regime context and
Store settings_kv persistence. It deliberately produces proposals and review
contracts only; it never mutates active production filters without human review.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any

from app.core.config import build_data_trust_context, get_settings
from app.data.store import Store, store
from app.domain.filter_intelligence import (
    FilterAnalysisResult,
    FilterComparison,
    FilterDecaySignal,
    FilterRegistryItem,
    FilterVersion,
    OptimizationProposal,
    PerformanceRecord,
    ProposalReview,
)
from app.engines.backtest import backtest_from_market
from app.engines.filter_dsl import PRESETS, FilterError, validate_filter

REGISTRY_KEY = "filter_intelligence.registry.v1"
PERFORMANCE_KEY = "filter_intelligence.performance.v1"
PROPOSALS_KEY = "filter_intelligence.proposals.v1"
REVIEWS_KEY = "filter_intelligence.reviews.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _as_float(value: Any) -> float | None:
    try:
        if isinstance(value, str):
            return None
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _trust_live(data_trust: dict[str, Any]) -> bool:
    return data_trust.get("state") == "live" and data_trust.get("is_live") is True


class FilterIntelligenceService:
    def __init__(self, persistence: Store | None = None) -> None:
        self.store = persistence or store

    # ---------- persistence ----------
    def _load_registry(self) -> dict[str, Any]:
        data = self.store.get_setting(REGISTRY_KEY, None)
        if not data:
            data = self._default_registry_payload()
            self.store.set_setting(REGISTRY_KEY, data)
        return data

    def _save_registry(self, data: dict[str, Any]) -> None:
        self.store.set_setting(REGISTRY_KEY, data)

    def _load_performance(self) -> list[dict[str, Any]]:
        return list(self.store.get_setting(PERFORMANCE_KEY, []) or [])

    def _save_performance(self, rows: list[dict[str, Any]]) -> None:
        self.store.set_setting(PERFORMANCE_KEY, rows[-500:])

    def _load_proposals(self) -> list[dict[str, Any]]:
        return list(self.store.get_setting(PROPOSALS_KEY, []) or [])

    def _save_proposals(self, rows: list[dict[str, Any]]) -> None:
        self.store.set_setting(PROPOSALS_KEY, rows[-250:])

    def _load_reviews(self) -> list[dict[str, Any]]:
        return list(self.store.get_setting(REVIEWS_KEY, []) or [])

    def _save_reviews(self, rows: list[dict[str, Any]]) -> None:
        self.store.set_setting(REVIEWS_KEY, rows[-250:])

    def _default_registry_payload(self) -> dict[str, Any]:
        now = _utc_now()
        items: dict[str, Any] = {}
        for preset in PRESETS:
            filter_id = str(preset["id"])
            version = FilterVersion(
                filter_id=filter_id,
                name=preset["name"],
                version="v1",
                description=f"Preset filter migrated into P3.41 registry from safe Filter DSL preset {filter_id}.",
                market="iran",
                status="ACTIVE",
                conditions=preset["expr"],
                created_at=now,
                updated_at=now,
                owner="radar-bourse",
                tags=["preset", "iran", "p3.41"],
                validation=validate_filter(preset["expr"]),
            )
            item = FilterRegistryItem(
                filter_id=filter_id,
                name=preset["name"],
                market="iran",
                status="ACTIVE",
                active_version="v1",
                latest_version="v1",
                description=version.description,
                owner="radar-bourse",
                tags=version.tags,
                created_at=now,
                updated_at=now,
                versions=[version],
            )
            items[filter_id] = item.model_dump(mode="json")
        return {"schema": 1, "updated_at": now, "items": items}

    # ---------- registry/versioning ----------
    def list_filters(self) -> list[FilterRegistryItem]:
        data = self._load_registry()
        return [FilterRegistryItem(**x) for x in data.get("items", {}).values()]

    def get_filter(self, filter_id: str) -> FilterRegistryItem | None:
        item = self._load_registry().get("items", {}).get(filter_id)
        return FilterRegistryItem(**item) if item else None

    def get_version(self, filter_id: str, version: str | None = None) -> FilterVersion | None:
        item = self.get_filter(filter_id)
        if not item:
            return None
        target = version or item.active_version or item.latest_version
        for v in item.versions:
            if v.version == target:
                return v
        return None

    def create_version(self, filter_id: str, conditions: str, *, description: str = "", owner: str = "ai-proposal", tags: list[str] | None = None) -> FilterVersion:
        validation = validate_filter(conditions)
        data = self._load_registry()
        raw = data.get("items", {}).get(filter_id)
        if not raw:
            raise KeyError(filter_id)
        item = FilterRegistryItem(**raw)
        nums = [int(v.version[1:]) for v in item.versions if re.fullmatch(r"v\d+", v.version)] or [0]
        new_version = f"v{max(nums) + 1}"
        now = _utc_now()
        version = FilterVersion(
            filter_id=filter_id,
            name=item.name,
            version=new_version,
            description=description or item.description,
            market=item.market,
            status="DRAFT",
            conditions=conditions,
            created_at=now,
            updated_at=now,
            owner=owner,
            tags=tags or item.tags,
            parent_version=item.latest_version,
            change_summary="New immutable version. Previous versions are preserved.",
            validation=validation,
        )
        item.versions.append(version)
        item.latest_version = new_version
        item.updated_at = now
        data["items"][filter_id] = item.model_dump(mode="json")
        data["updated_at"] = now
        self._save_registry(data)
        return version

    # ---------- performance/evaluation ----------
    def _classification(self, record: PerformanceRecord, *, live_required: bool = False) -> tuple[str, list[str]]:
        reasons: list[str] = list(record.reason_codes)
        if live_required and not _trust_live(record.data_trust):
            reasons.append("DATA_TRUST_BLOCK")
            return "INSUFFICIENT_DATA", reasons
        if record.signal_count < 5 or record.sample_size < 3:
            reasons.append("SAMPLE_SIZE_TOO_SMALL")
            return "INSUFFICIENT_DATA", reasons
        win = _as_float(record.win_rate) or 0.0
        avg_ret = _as_float(record.average_return) or 0.0
        pf = _as_float(record.profit_factor) or 0.0
        dd = _as_float(record.max_drawdown) or 0.0
        stability = _as_float(record.stability_score) or 0.0
        if dd >= 35 or pf < 0.8 or win < 35:
            reasons.append("RISK_OR_EDGE_WEAK")
            return "WEAK", reasons
        if win >= 60 and pf >= 1.4 and dd <= 15 and stability >= 65:
            reasons.append("MULTI_METRIC_STRONG")
            return "EXCELLENT", reasons
        if win >= 52 and pf >= 1.15 and dd <= 25 and avg_ret >= 0:
            reasons.append("EDGE_POSITIVE")
            return "GOOD", reasons
        reasons.append("EDGE_STABLE_OR_MIXED")
        return "STABLE", reasons

    def _record_from_result(self, filter_version: FilterVersion, result: dict[str, Any], mode: str, regime: str, period: str) -> PerformanceRecord:
        metrics = result.get("metrics") or {}
        data_trust = result.get("data_trust") or build_data_trust_context("unknown")
        signal_count = int(result.get("trades") or metrics.get("number_of_trades") or result.get("summary", {}).get("total_oos_trades") or 0)
        sample_size = int(result.get("symbols_tested") or result.get("path_symbols") or len(result.get("windows") or []) or 0)
        stability: float | str = "NOT_AVAILABLE"
        if result.get("mode") == "walk_forward" or mode == "WALK_FORWARD":
            returns = [float(((w.get("result") or {}).get("metrics") or {}).get("total_return") or 0) for w in result.get("windows", [])]
            if len(returns) >= 2:
                sd = pstdev(returns)
                stability = round(max(0.0, min(100.0, 100.0 - sd * 10.0)), 2)
            elif returns:
                stability = 50.0
        elif signal_count >= 2:
            stability = 60.0
        record = PerformanceRecord(
            record_id=_record_id("perf"),
            filter_id=filter_version.filter_id,
            version=filter_version.version,
            evaluation_mode=mode,  # type: ignore[arg-type]
            evaluation_period=period,
            market=filter_version.market,
            sample_size=sample_size,
            signal_count=signal_count,
            win_rate=metrics.get("win_rate", "NOT_AVAILABLE"),
            average_return=metrics.get("average_return", metrics.get("avg_window_total_return", "NOT_AVAILABLE")),
            median_return=metrics.get("median_return", "NOT_AVAILABLE"),
            profit_factor=metrics.get("profit_factor", "NOT_AVAILABLE"),
            max_drawdown=metrics.get("maximum_drawdown", result.get("max_drawdown", "NOT_AVAILABLE")),
            sharpe=metrics.get("sharpe_ratio", "NOT_AVAILABLE"),
            precision="NOT_AVAILABLE",
            false_positive_rate="NOT_AVAILABLE",
            stability_score=stability,
            regime=regime,
            regime_performance={regime: {"win_rate": metrics.get("win_rate", "NOT_AVAILABLE"), "signal_count": signal_count}},
            data_trust=data_trust,
            timestamp=_utc_now(),
            warnings=list(result.get("warnings") or []),
            raw_result=result,
        )
        cls, reasons = self._classification(record)
        record.classification = cls  # type: ignore[assignment]
        record.reason_codes = list(dict.fromkeys(reasons))
        if not _trust_live(data_trust):
            record.warnings.append("Non-live data trust: record must not be presented as live performance.")
        return record

    async def evaluate_filter(self, market_service: Any, filter_id: str, version: str | None = None, *, persist: bool = True, bars: int = 80) -> dict[str, Any]:
        fv = self.get_version(filter_id, version)
        if not fv:
            raise KeyError(filter_id)
        await market_service.get_analysis(force=False)
        symbols = list(getattr(market_service, "_last_symbols", []) or [])
        if not symbols:
            # Keep the response truthful instead of inventing a market dataset.
            trust = market_service.data_trust_context() if hasattr(market_service, "data_trust_context") else build_data_trust_context("none")
            rec = PerformanceRecord(
                record_id=_record_id("perf"),
                filter_id=fv.filter_id,
                version=fv.version,
                evaluation_mode="MONITORING",
                evaluation_period="no_market_symbols_available",
                sample_size=0,
                signal_count=0,
                data_trust=trust,
                timestamp=_utc_now(),
                classification="INSUFFICIENT_DATA",
                reason_codes=["NO_MARKET_SYMBOLS"],
                warnings=["Market service has no symbol cache; backtest/walk-forward/forward-test were NOT EXECUTED."],
            )
            return {"filter": fv.model_dump(mode="json"), "records": [rec.model_dump(mode="json")], "analysis": self.analyze_records(fv.filter_id, fv.version, [rec]).model_dump(mode="json")}

        regime = "INSUFFICIENT_DATA"
        try:
            from app.services.market_intelligence_service import market_intelligence_service
            mi = await market_intelligence_service.run_market_monitoring_cycle(market_service, limit=20, persist=False)
            regime = mi.snapshot.market_regime
        except Exception:
            regime = "INSUFFICIENT_DATA"

        common = {"strategy_filter": fv.conditions, "bars": bars, "use_synthetic_if_needed": True}
        backtest = backtest_from_market(symbols, self.store, get_settings(), walk_forward=False, forward_test=False, **common)
        walk = backtest_from_market(symbols, self.store, get_settings(), walk_forward=True, forward_test=False, **common)
        forward = backtest_from_market(symbols, self.store, get_settings(), walk_forward=False, forward_test=True, **common)
        records = [
            self._record_from_result(fv, backtest, "BACKTEST", regime, f"last_{bars}_bars_or_synthetic"),
            self._record_from_result(fv, walk, "WALK_FORWARD", regime, f"rolling_oos_last_{bars}_bars_or_synthetic"),
            self._record_from_result(fv, forward, "FORWARD_TEST", regime, "forward_oos_last_third_or_since_boundary"),
        ]
        if persist:
            rows = self._load_performance()
            rows.extend([r.model_dump(mode="json") for r in records])
            self._save_performance(rows)
        analysis = self.analyze_records(fv.filter_id, fv.version, records)
        return {"filter": fv.model_dump(mode="json"), "records": [r.model_dump(mode="json") for r in records], "analysis": analysis.model_dump(mode="json")}

    def list_performance(self, filter_id: str | None = None, version: str | None = None, limit: int = 100) -> list[PerformanceRecord]:
        rows = self._load_performance()
        out = []
        for r in rows:
            if filter_id and r.get("filter_id") != filter_id:
                continue
            if version and r.get("version") != version:
                continue
            out.append(PerformanceRecord(**r))
        return out[-limit:]

    def detect_decay(self, filter_id: str, version: str, records: list[PerformanceRecord] | None = None) -> FilterDecaySignal:
        records = records or self.list_performance(filter_id, version, limit=50)
        if len(records) < 3:
            return FilterDecaySignal(filter_id=filter_id, version=version, status="INSUFFICIENT_DATA", reason_codes=["NEEDS_BACKTEST_WALK_FORWARD_FORWARD_RECORDS"])
        historical = next((r for r in records if r.evaluation_mode == "BACKTEST"), None)
        forward = next((r for r in reversed(records) if r.evaluation_mode == "FORWARD_TEST"), None)
        recent = records[-1]
        if not historical or not forward:
            return FilterDecaySignal(filter_id=filter_id, version=version, status="INSUFFICIENT_DATA", reason_codes=["MISSING_BASELINE_OR_FORWARD"])
        h_win = _as_float(historical.win_rate)
        f_win = _as_float(forward.win_rate)
        r_win = _as_float(recent.win_rate)
        if h_win is None or f_win is None or r_win is None or min(historical.signal_count, forward.signal_count) < 5:
            return FilterDecaySignal(filter_id=filter_id, version=version, status="INSUFFICIENT_DATA", reason_codes=["METRICS_OR_SAMPLE_NOT_ENOUGH"])
        drop = h_win - min(f_win, r_win)
        evidence = [{"historical_win_rate": h_win, "recent_win_rate": r_win, "forward_win_rate": f_win, "drop_points": round(drop, 2), "forward_signals": forward.signal_count, "regime": forward.regime}]
        if drop >= 18 and f_win < 50:
            return FilterDecaySignal(filter_id=filter_id, version=version, status="PERFORMANCE_DECAY", severity="high" if drop >= 25 else "medium", evidence=evidence, reason_codes=["PERFORMANCE_DECAY", "WIN_RATE_DROP_WITH_FORWARD_CONFIRMATION"])
        return FilterDecaySignal(filter_id=filter_id, version=version, status="NO_DECAY", evidence=evidence, reason_codes=["NO_CONFIRMED_DECAY"])

    def analyze_records(self, filter_id: str, version: str, records: list[PerformanceRecord] | None = None) -> FilterAnalysisResult:
        records = records or self.list_performance(filter_id, version, limit=50)
        decay = self.detect_decay(filter_id, version, records)
        latest = records[-1] if records else None
        if not latest:
            return FilterAnalysisResult(filter_id=filter_id, version=version, decay=decay, reason_codes=["NO_PERFORMANCE_RECORDS"])
        classifications = [r.classification for r in records]
        if decay.status == "PERFORMANCE_DECAY":
            classification = "DEGRADING"
            action = "REVIEW"
            recommendation = "REVIEW_OR_PAUSE_AFTER_HUMAN_VALIDATION"
        elif "WEAK" in classifications:
            classification = "WEAK"
            action = "PAUSE"
            recommendation = "PAUSE_OR_DEPRECATE_PROPOSAL_ONLY"
        elif "EXCELLENT" in classifications and "GOOD" in classifications:
            classification = "EXCELLENT"
            action = "KEEP"
            recommendation = "KEEP_ACTIVE_WITH_MONITORING"
        elif "GOOD" in classifications:
            classification = "GOOD"
            action = "KEEP"
            recommendation = "KEEP_AND_MONITOR"
        else:
            classification = latest.classification
            action = "REVIEW"
            recommendation = "REVIEW"
        live_records = sum(1 for r in records if _trust_live(r.data_trust))
        confidence = min(0.85, 0.2 + len(records) * 0.1 + live_records * 0.15)
        if live_records == 0:
            confidence = min(confidence, 0.35)
        evidence = [{"mode": r.evaluation_mode, "classification": r.classification, "signals": r.signal_count, "win_rate": r.win_rate, "data_trust_state": r.data_trust.get("state")} for r in records]
        return FilterAnalysisResult(
            filter_id=filter_id,
            version=version,
            classification=classification,  # type: ignore[arg-type]
            action=action,  # type: ignore[arg-type]
            confidence=round(confidence, 3),
            current_regime=latest.regime,
            historical=next((r.model_dump(mode="json") for r in records if r.evaluation_mode == "BACKTEST"), {}),
            walk_forward=next((r.model_dump(mode="json") for r in records if r.evaluation_mode == "WALK_FORWARD"), {}),
            forward=next((r.model_dump(mode="json") for r in records if r.evaluation_mode == "FORWARD_TEST"), {}),
            decay=decay,
            evidence=evidence,
            recommendation=recommendation,
            reason_codes=list(dict.fromkeys([code for r in records for code in r.reason_codes] + decay.reason_codes)),
            data_trust=latest.data_trust,
            safety={"ai_can_modify_production": False, "requires_human_approval": True, "no_autonomous_trading": True, "production_mutation": False},
        )

    # ---------- proposals / approval ----------
    def _threshold_variant(self, expr: str) -> tuple[str, list[dict[str, Any]], str]:
        match = re.search(r"(volume_ratio\s*>=\s*)(\d+(?:\.\d+)?)", expr)
        if match:
            old = float(match.group(2))
            new = round(max(1.0, old * 0.85), 2)
            proposed = expr[: match.start(2)] + str(new) + expr[match.end(2) :]
            return proposed, [{"field": "volume_ratio", "from": old, "to": new, "type": "threshold_adjustment"}], "Lower volume threshold to recover signal frequency; validation chain required before activation."
        match = re.search(r"(entry_score\s*>=\s*)(\d+(?:\.\d+)?)", expr)
        if match:
            old = float(match.group(2))
            new = round(max(40.0, old - 5.0), 2)
            proposed = expr[: match.start(2)] + str(new) + expr[match.end(2) :]
            return proposed, [{"field": "entry_score", "from": old, "to": new, "type": "threshold_adjustment"}], "Lower entry threshold slightly; validation chain required before activation."
        proposed = f"({expr}) and entry_score >= 50"
        return proposed, [{"field": "entry_score", "from": "implicit", "to": 50, "type": "risk_guard_added"}], "Add minimum entry-score risk guard; validation chain required before activation."

    def create_proposal(self, filter_id: str, version: str | None = None, *, reasoning: str = "") -> OptimizationProposal:
        fv = self.get_version(filter_id, version)
        if not fv:
            raise KeyError(filter_id)
        proposed_conditions, changes, default_reason = self._threshold_variant(fv.conditions)
        validate_filter(proposed_conditions)
        nums = [int(v.version[1:]) for v in (self.get_filter(filter_id).versions if self.get_filter(filter_id) else []) if re.fullmatch(r"v\d+", v.version)] or [0]
        proposed_version = f"v{max(nums) + 1}"
        records = self.list_performance(filter_id, fv.version, limit=20)
        analysis = self.analyze_records(filter_id, fv.version, records) if records else None
        now = _utc_now()
        proposal = OptimizationProposal(
            proposal_id=_record_id("prop"),
            filter_id=filter_id,
            current_version=fv.version,
            proposed_version=proposed_version,
            changes=changes,
            reasoning=reasoning or default_reason,
            expected_effect="Potential signal-frequency/stability improvement; not approved until backtest, walk-forward, forward-test and human review complete.",
            evidence=analysis.evidence if analysis else [{"status": "NO_PERFORMANCE_HISTORY", "note": "Proposal requires validation before any use."}],
            confidence=analysis.confidence if analysis else 0.2,
            risk="MEDIUM" if not analysis or analysis.confidence < 0.55 else "LOW",
            status="PROPOSED",
            created_at=now,
            updated_at=now,
        )
        rows = self._load_proposals()
        rows.append(proposal.model_dump(mode="json"))
        self._save_proposals(rows)
        return proposal

    def list_proposals(self, filter_id: str | None = None) -> list[OptimizationProposal]:
        rows = self._load_proposals()
        return [OptimizationProposal(**r) for r in rows if not filter_id or r.get("filter_id") == filter_id]

    def review_proposal(self, proposal_id: str, reviewer: str, decision: str, reason: str = "") -> ProposalReview:
        if decision not in {"APPROVE", "REJECT", "REQUEST_RETEST"}:
            raise ValueError("invalid review decision")
        proposals = self._load_proposals()
        found = None
        for p in proposals:
            if p.get("proposal_id") == proposal_id:
                found = p
                break
        if not found:
            raise KeyError(proposal_id)
        resulting = "APPROVED" if decision == "APPROVE" else "REJECTED" if decision == "REJECT" else "PROPOSED"
        found["status"] = resulting
        found["updated_at"] = _utc_now()
        self._save_proposals(proposals)
        review = ProposalReview(
            proposal_id=proposal_id,
            reviewer=reviewer,
            decision=decision,  # type: ignore[arg-type]
            timestamp=_utc_now(),
            reason=reason,
            resulting_status=resulting,  # type: ignore[arg-type]
            safety={"approval_does_not_auto_activate": True, "activation_requires_explicit_version_creation": True, "ai_can_modify_production": False},
        )
        reviews = self._load_reviews()
        reviews.append(review.model_dump(mode="json"))
        self._save_reviews(reviews)
        return review

    # ---------- comparison ----------
    def build_ai_filter_context(self, filter_expr: str | None = None, *, filter_id: str | None = None, version: str | None = None) -> dict[str, Any]:
        """Build controlled P3.41 filter-intelligence context for AIIntelligenceCore.

        This method is intentionally read-only. It does not run optimization,
        create proposals, activate versions, or mutate production filters. If no
        historical performance exists, it returns an explicit
        INSUFFICIENT_DATA classification instead of inventing metrics.
        """
        matched_version: FilterVersion | None = None
        match_source = "none"
        if filter_id:
            matched_version = self.get_version(filter_id, version)
            match_source = "registry_filter_id"
        elif filter_expr:
            validation = validate_filter(filter_expr)
            normalized_expr = " ".join(filter_expr.strip().split())
            for item in self.list_filters():
                for candidate in item.versions:
                    if " ".join(candidate.conditions.strip().split()) == normalized_expr:
                        matched_version = candidate
                        match_source = "registry_conditions"
                        break
                if matched_version:
                    break
            if not matched_version:
                return {
                    "classification": "INSUFFICIENT_DATA",
                    "source": "ad_hoc_filter_expr",
                    "validation": validation,
                    "reason_codes": ["AD_HOC_FILTER_NOT_IN_REGISTRY", "NO_PERFORMANCE_HISTORY"],
                    "safety": {"ai_can_modify_production": False, "requires_human_approval": True},
                }
        if not matched_version:
            return {
                "classification": "INSUFFICIENT_DATA",
                "source": match_source,
                "reason_codes": ["NO_FILTER_CONTEXT"],
                "safety": {"ai_can_modify_production": False, "requires_human_approval": True},
            }
        records = self.list_performance(matched_version.filter_id, matched_version.version, limit=50)
        if records:
            analysis = self.analyze_records(matched_version.filter_id, matched_version.version, records)
            return {
                "classification": analysis.classification,
                "source": match_source,
                "filter_id": matched_version.filter_id,
                "version": matched_version.version,
                "analysis": analysis.model_dump(mode="json"),
                "records_count": len(records),
                "reason_codes": analysis.reason_codes,
                "safety": analysis.safety,
            }
        return {
            "classification": "INSUFFICIENT_DATA",
            "source": match_source,
            "filter_id": matched_version.filter_id,
            "version": matched_version.version,
            "records_count": 0,
            "reason_codes": ["NO_PERFORMANCE_HISTORY"],
            "safety": {"ai_can_modify_production": False, "requires_human_approval": True},
        }

    def compare_versions(self, filter_id: str, left_version: str, right_version: str) -> FilterComparison:
        left = self.list_performance(filter_id, left_version, limit=20)
        right = self.list_performance(filter_id, right_version, limit=20)
        metrics: dict[str, dict[str, Any]] = {}
        for key in ["win_rate", "average_return", "profit_factor", "max_drawdown", "sharpe", "signal_count", "stability_score"]:
            lvals = [_as_float(getattr(r, key)) for r in left]
            rvals = [_as_float(getattr(r, key)) for r in right]
            lnums = [x for x in lvals if x is not None]
            rnums = [x for x in rvals if x is not None]
            metrics[key] = {"left": round(mean(lnums), 3) if lnums else "NOT_AVAILABLE", "right": round(mean(rnums), 3) if rnums else "NOT_AVAILABLE"}
        conclusion = "INSUFFICIENT_DATA" if not left or not right else "COMPARISON_READY_FOR_AI_REVIEW"
        return FilterComparison(
            filter_id=filter_id,
            left_version=left_version,
            right_version=right_version,
            metrics=metrics,
            regime_performance={"left": [r.regime_performance for r in left], "right": [r.regime_performance for r in right]},
            forward_performance={"left": [r.model_dump(mode="json") for r in left if r.evaluation_mode == "FORWARD_TEST"], "right": [r.model_dump(mode="json") for r in right if r.evaluation_mode == "FORWARD_TEST"]},
            conclusion=conclusion,
            evidence=[{"left_records": len(left), "right_records": len(right), "human_review_required": True}],
            data_trust=(right[-1].data_trust if right else left[-1].data_trust if left else build_data_trust_context("none")),
        )

    async def filter_intelligence_summary(self, market_service: Any, *, persist: bool = False, limit: int = 5) -> dict[str, Any]:
        filters = self.list_filters()[:limit]
        evaluations = []
        for item in filters:
            if item.active_version:
                try:
                    evaluations.append(await self.evaluate_filter(market_service, item.filter_id, item.active_version, persist=persist, bars=80))
                except (FilterError, KeyError, ValueError) as exc:
                    evaluations.append({"filter_id": item.filter_id, "error": str(exc), "classification": "INVALID"})
        return {
            "ok": True,
            "filters_evaluated": len(evaluations),
            "evaluations": evaluations,
            "proposals": [p.model_dump(mode="json") for p in self.list_proposals()],
            "safety": {"ai_can_modify_production": False, "requires_human_approval": True, "scheduler_enabled": False},
        }


filter_intelligence_service = FilterIntelligenceService()
