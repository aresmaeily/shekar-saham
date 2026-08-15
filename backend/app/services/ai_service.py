"""Controlled AI service layer for RADAR BOURSE.

P3.28 implements a safe, deterministic fallback AI layer. It does not call an
external LLM unless a future provider is explicitly wired through environment
configuration. No credentials are accepted from clients and no trading action is
ever performed here.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import is_verified_live
from app.domain.ai_intelligence import AIIntelligenceCore
from app.engines.filter_dsl import FilterError, validate_filter

AIProviderMode = Literal["fallback", "external_not_configured"]
AITaskType = Literal["assistant", "analyst", "optimizer"]


class AIRequest(BaseModel):
    question: str = ""
    symbol: str | None = None
    filter_expr: str | None = None
    backtest_result: dict[str, Any] | None = None
    language: str = "fa"


class AIContext(BaseModel):
    task: AITaskType
    question: str = ""
    symbol: str | None = None
    data_trust: dict[str, Any] = Field(default_factory=dict)
    market: dict[str, Any] = Field(default_factory=dict)
    symbol_context: dict[str, Any] = Field(default_factory=dict)
    filter_context: dict[str, Any] = Field(default_factory=dict)
    backtest_context: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class AIResult(BaseModel):
    ok: bool = True
    task: AITaskType
    provider: AIProviderMode = "fallback"
    provider_label: str = "deterministic-rule-based-fallback"
    title: str = ""
    summary: str = ""
    answer: str = ""
    market_context: dict[str, Any] = Field(default_factory=dict)
    symbol_context: dict[str, Any] = Field(default_factory=dict)
    data_trust: dict[str, Any] = Field(default_factory=dict)
    key_observations: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    safety: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def _fmt_num(v: Any, digits: int = 2) -> str:
    try:
        return f"{float(v):,.{digits}f}"
    except Exception:
        return "—"


def _trust_warnings(data_trust: dict[str, Any]) -> list[str]:
    if is_verified_live(data_trust):
        return []
    state = (data_trust.get("state") or "mixed")
    out = []
    if state == "live":
        out.append("منبع زنده‌نما تأیید مستقل نشده است؛ نتیجه مبنای معامله نیست.")
    elif state in {"mock", "synthetic"}:
        out.append("داده مورد استفاده زنده نیست؛ نتیجه فقط برای تحلیل/آموزش معتبر است.")
    elif state == "stale":
        out.append("داده مورد استفاده قدیمی است؛ تحلیل نباید به‌عنوان وضعیت زنده بازار تفسیر شود.")
    elif state == "unavailable":
        out.append("داده قابل اتکا در دسترس نیست؛ نتیجه فقط وضعیت نبود داده را توضیح می‌دهد.")
    else:
        out.append("اعتماد داده mixed است؛ بخشی از داده یا منبع کاملاً اعتبارسنجی نشده است.")
    return out


def _trust_confidence(data_trust: dict[str, Any], *, has_context: bool = True) -> float:
    if not has_context:
        return 0.20
    if is_verified_live(data_trust):
        return 0.60
    state = data_trust.get("state") or "mixed"
    if state == "live":
        return 0.35
    if state == "mixed":
        return 0.42
    if state in {"mock", "synthetic"}:
        return 0.35
    if state == "stale":
        return 0.28
    if state == "unavailable":
        return 0.15
    return 0.25


class AIContextBuilder:
    """Builds controlled context from existing services, never raw providers."""

    async def build(self, request: AIRequest, task: AITaskType, market_service: Any) -> AIContext:
        await market_service.get_analysis(force=False)
        status = market_service.status()
        data_trust = market_service.data_trust_context()
        warnings = _trust_warnings(data_trust)
        market = {
            "source": status.get("source"),
            "trust_level": status.get("trust_level"),
            "symbol_count": status.get("symbol_count"),
            "flow_meta": status.get("flow_meta"),
            "confluence": status.get("confluence"),
        }
        symbol_context: dict[str, Any] = {}
        if request.symbol:
            symbol_context = market_service.get_symbol(request.symbol) or {}
            if not symbol_context:
                warnings.append(f"Insufficient Data: نماد {request.symbol} در داده فعلی پیدا نشد.")
        filter_context: dict[str, Any] = {}
        if request.filter_expr:
            try:
                validation = validate_filter(request.filter_expr)
                sample = market_service.run_user_filter(request.filter_expr, limit=10)
                filter_context = {"validation": validation, "sample": sample}
                try:
                    from app.services.filter_intelligence_service import filter_intelligence_service

                    filter_context["filter_intelligence"] = filter_intelligence_service.build_ai_filter_context(request.filter_expr)
                except Exception as exc:
                    warnings.append(f"Filter Intelligence context unavailable: {type(exc).__name__}")
            except FilterError as exc:
                filter_context = {"ok": False, "error": str(exc), "expr": request.filter_expr}
                warnings.append(f"Filter validation failed: {exc}")
        backtest_context = request.backtest_result or {}
        return AIContext(
            task=task,
            question=request.question,
            symbol=request.symbol,
            data_trust=data_trust,
            market=market,
            symbol_context=symbol_context,
            filter_context=filter_context,
            backtest_context=backtest_context,
            warnings=warnings,
        )


class FallbackAIProvider:
    """Safe deterministic AI provider used when no external LLM is configured."""

    mode: AIProviderMode = "fallback"

    def assistant(self, ctx: AIContext) -> AIResult:
        observations = []
        evidence = []
        if ctx.market:
            observations.append(
                f"بازار فعلی با منبع {ctx.market.get('source', 'unknown')} و سطح اعتماد {ctx.market.get('trust_level', 'mixed')} دیده می‌شود."
            )
            evidence.append({"type": "market_status", "value": ctx.market})
        if ctx.symbol_context:
            snap = ctx.symbol_context.get("snapshot") or {}
            metrics = ctx.symbol_context.get("metrics") or {}
            observations.append(
                f"نماد {snap.get('l18', ctx.symbol)}: قیمت {_fmt_num(snap.get('pl'), 0)}، تغییر { _fmt_num(snap.get('plp')) }٪، قدرت خریدار {_fmt_num(metrics.get('buy_power'))}."
            )
            evidence.append({"type": "symbol", "symbol": snap.get("l18"), "price": snap.get("pl"), "buy_power": metrics.get("buy_power")})
        if ctx.filter_context:
            if ctx.filter_context.get("error"):
                observations.append("فیلتر ارائه‌شده معتبر نیست و قبل از استفاده باید اصلاح شود.")
            else:
                sample = ctx.filter_context.get("sample") or {}
                observations.append(f"فیلتر معتبر است و در نمونه فعلی {sample.get('count', 0)} ردیف منطبق پیدا کرده است.")
                evidence.append({"type": "filter", "fields": (ctx.filter_context.get("validation") or {}).get("fields"), "count": sample.get("count")})
                fi = ctx.filter_context.get("filter_intelligence") or {}
                if fi:
                    observations.append(f"Filter Intelligence classification: {fi.get('classification', 'INSUFFICIENT_DATA')}؛ تغییر production نیازمند تأیید انسانی است.")
                    evidence.append({"type": "filter_intelligence", "classification": fi.get("classification"), "filter_id": fi.get("filter_id"), "version": fi.get("version"), "reason_codes": fi.get("reason_codes")})
        if not observations:
            observations.append("Insufficient Data: برای پاسخ دقیق، نماد، فیلتر یا نتیجه بک‌تست بیشتری لازم است.")
        warnings = ctx.warnings + ["این پاسخ fallback/rule-based است و LLM زنده استفاده نشده است."]
        return AIResult(
            task="assistant",
            title="AI Assistant — پاسخ کنترل‌شده",
            summary=" ".join(observations[:3]),
            answer="\n".join(observations),
            market_context=ctx.market,
            symbol_context=ctx.symbol_context,
            data_trust=ctx.data_trust,
            key_observations=observations,
            risk_flags=_trust_warnings(ctx.data_trust),
            uncertainty=["بدون داده live/validated یا LLM خارجی، نتیجه قطعی نیست."],
            evidence=evidence,
            confidence=_trust_confidence(ctx.data_trust),
            safety=self._safety(),
            warnings=warnings,
        )

    def analyst(self, ctx: AIContext) -> AIResult:
        observations: list[str] = []
        risks: list[str] = _trust_warnings(ctx.data_trust)
        evidence: list[dict[str, Any]] = []
        conclusion = "Insufficient Data"
        if ctx.symbol_context:
            snap = ctx.symbol_context.get("snapshot") or {}
            metrics = ctx.symbol_context.get("metrics") or {}
            tablo = ctx.symbol_context.get("tablocastic") or {}
            entry = float(metrics.get("entry_score") or 0)
            exit_s = float(metrics.get("exit_score") or 0)
            buy_power = float(metrics.get("buy_power") or 0)
            observations.extend([
                f"Entry Score: {_fmt_num(entry, 1)}",
                f"Exit Score: {_fmt_num(exit_s, 1)}",
                f"Buy Power: {_fmt_num(buy_power, 2)}",
                f"Tablocastic Grade: {tablo.get('grade', '—')}",
            ])
            evidence.append({"type": "scores", "entry_score": entry, "exit_score": exit_s, "buy_power": buy_power, "grade": tablo.get("grade")})
            if entry >= 70 and buy_power >= 1.5:
                conclusion = "شرایط تابلوخوانی مثبت است، اما نیاز به مدیریت ریسک و بررسی اعتماد داده دارد."
            elif exit_s >= 60:
                conclusion = "ریسک خروج/ضعف تقاضا قابل توجه است."
            else:
                conclusion = "سیگنال قطعی دیده نمی‌شود؛ وضعیت بیشتر در محدوده رصد است."
            if not is_verified_live(ctx.data_trust):
                risks.append("تحلیل بر اساس داده live تأییدشده نیست.")
            if snap.get("plp") is not None and abs(float(snap.get("plp") or 0)) > 4:
                risks.append("نوسان قیمت بالا است؛ ریسک هیجانی وجود دارد.")
        else:
            observations.append("برای تحلیل نماد، symbol معتبر لازم است.")
        return AIResult(
            task="analyst",
            title="AI Analyst — تحلیل ساختاریافته",
            summary=conclusion,
            answer=conclusion,
            market_context=ctx.market,
            symbol_context=ctx.symbol_context,
            data_trust=ctx.data_trust,
            key_observations=observations,
            risk_flags=risks,
            uncertainty=["این تحلیل تضمین سود یا پیش‌بینی قطعی قیمت نیست."],
            evidence=evidence,
            confidence=_trust_confidence(ctx.data_trust, has_context=bool(ctx.symbol_context)),
            safety=self._safety(),
            warnings=ctx.warnings + ["تحلیل rule-based/fallback است."],
        )

    def optimizer(self, ctx: AIContext) -> AIResult:
        suggestions: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        if ctx.filter_context and not ctx.filter_context.get("error"):
            sample = ctx.filter_context.get("sample") or {}
            count = int(sample.get("count") or 0)
            evidence.append({"type": "filter_sample", "count": count})
            if count == 0:
                suggestions.append({"type": "filter", "action": "relax", "reason": "فیلتر هیچ خروجی ندارد؛ آستانه‌ها را کمی کاهش دهید یا شرط‌ها را کمتر کنید."})
            elif count > 50:
                suggestions.append({"type": "filter", "action": "tighten", "reason": "فیلتر خروجی زیاد دارد؛ برای کاهش نویز آستانه volume_ratio یا entry_score را افزایش دهید."})
            else:
                suggestions.append({"type": "filter", "action": "backtest", "reason": "فیلتر خروجی قابل مدیریت دارد؛ پیشنهاد می‌شود بک‌تست سناریویی اجرا شود."})
        if ctx.backtest_context:
            metrics = ctx.backtest_context.get("metrics") or ctx.backtest_context
            pf = float(metrics.get("profit_factor") or 0)
            dd = float(metrics.get("maximum_drawdown") or metrics.get("max_drawdown") or 0)
            evidence.append({"type": "backtest_metrics", "profit_factor": pf, "drawdown": dd})
            if pf and pf < 1:
                suggestions.append({"type": "parameter", "action": "improve_exit", "reason": "Profit Factor کمتر از ۱ است؛ خروج/حدضرر یا فیلتر ورود نیاز به سخت‌گیری دارد."})
            if dd > 15:
                suggestions.append({"type": "risk", "action": "reduce_position", "reason": "Drawdown بالا است؛ position_size یا max_hold را کاهش دهید."})
        if not suggestions:
            suggestions.append({"type": "insufficient_data", "action": "provide_filter_or_backtest", "reason": "برای پیشنهاد بهینه‌سازی، فیلتر یا نتیجه بک‌تست لازم است."})
        return AIResult(
            task="optimizer",
            title="AI Optimizer — پیشنهاد کنترل‌شده",
            summary="پیشنهادها فقط برای بررسی و اجرای دستی هستند؛ هیچ تغییر خودکاری انجام نمی‌شود.",
            answer="هیچ Strategy یا Repository به‌صورت خودکار تغییر نکرد.",
            market_context=ctx.market,
            symbol_context=ctx.symbol_context,
            data_trust=ctx.data_trust,
            key_observations=[s["reason"] for s in suggestions],
            risk_flags=_trust_warnings(ctx.data_trust),
            uncertainty=["پیشنهادها قطعی نیستند و باید با بک‌تست/Forward Test مستقل بررسی شوند."],
            evidence=evidence,
            suggestions=suggestions,
            confidence=min(0.50 if evidence else 0.25, _trust_confidence(ctx.data_trust)),
            safety=self._safety(),
            warnings=ctx.warnings + ["Optimizer هیچ تغییری را خودکار اعمال نمی‌کند."],
        )

    @staticmethod
    def _safety() -> dict[str, Any]:
        return {
            "no_guaranteed_profit": True,
            "no_price_prediction_guarantee": True,
            "no_auto_trading": True,
            "no_broker_connection": True,
            "no_repository_changes": True,
            "requires_user_confirmation_for_actions": True,
        }


class AIService:
    def __init__(self) -> None:
        self.context_builder = AIContextBuilder()
        self.provider = FallbackAIProvider()
        self.intelligence_core = AIIntelligenceCore()

    async def intelligence(self, request: AIRequest, market_service: Any) -> dict[str, Any]:
        ctx = await self.context_builder.build(request, "analyst", market_service)
        result = self.intelligence_core.evaluate(
            symbol_context=ctx.symbol_context,
            market_context=ctx.market,
            filter_context=ctx.filter_context,
            backtest_context=ctx.backtest_context,
            data_trust=ctx.data_trust,
        ).model_dump(mode="json")
        result["provider"] = self.provider.mode
        result["warnings"] = list(dict.fromkeys((result.get("warnings") or []) + ctx.warnings))
        return result

    async def assistant(self, request: AIRequest, market_service: Any) -> dict[str, Any]:
        ctx = await self.context_builder.build(request, "assistant", market_service)
        return self.provider.assistant(ctx).model_dump(mode="json")

    async def analyst(self, request: AIRequest, market_service: Any) -> dict[str, Any]:
        ctx = await self.context_builder.build(request, "analyst", market_service)
        return self.provider.analyst(ctx).model_dump(mode="json")

    async def optimizer(self, request: AIRequest, market_service: Any) -> dict[str, Any]:
        ctx = await self.context_builder.build(request, "optimizer", market_service)
        return self.provider.optimizer(ctx).model_dump(mode="json")


ai_service = AIService()
