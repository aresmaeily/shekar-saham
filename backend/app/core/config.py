from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TrustLevel = Literal["synthetic", "mixed", "live"]
DataTrustState = Literal["live", "mixed", "mock", "synthetic", "stale", "unavailable"]


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "رادار بورس"
    app_name_en: str = "RADAR BOURSE"
    version: str = "3.0.0"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = _env_bool("DEBUG", "0")

    # mock | tsetmc | brsapi | auto
    data_source: str = os.getenv("DATA_SOURCE", "auto")
    # بدون کلید پیش‌فرض — باید از env بیاید
    brsapi_key: str = os.getenv("BRSAPI_KEY", "")
    brsapi_base: str = "https://Api.BrsApi.ir/Tsetmc"
    tsetmc_cdn: str = os.getenv("TSETMC_BASE", "https://cdn.tsetmc.com")
    tsetmc_www: str = "https://cdn.tsetmc.com"

    poll_seconds: int = int(os.getenv("POLL_SECONDS", "30"))
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "12"))
    data_stale_after_sec: float = float(os.getenv("DATA_STALE_AFTER_SEC", "300"))
    data_clock_skew_tolerance_sec: float = float(os.getenv("DATA_CLOCK_SKEW_TOLERANCE_SEC", "0"))

    # --- Thresholds ---
    hot_money_threshold: float = 200_000_000
    hot_money_plus_min: float = 100_000_000
    hot_money_plus_max: float = 200_000_000
    volume_spike_ratio: float = 2.0
    volume_spike_strong: float = 3.5
    buy_power_min: float = 1.5
    buy_power_strong: float = 2.0
    smart_per_capita_min: float = 25_000_000
    near_buy_queue_pct: float = 1.5
    negative_plp_max: float = 0.0
    deep_negative_plp: float = -2.0
    pe_max_attractive: float = 12.0
    pe_max_ok: float = 18.0
    min_market_cap: float = 500_000_000_000
    entry_score_alert: float = 65.0
    entry_score_strong: float = 80.0
    exit_score_alert: float = 60.0

    big_move_window_sec: int = int(os.getenv("BIG_MOVE_WINDOW_SEC", "600"))
    big_move_min_score: float = float(os.getenv("BIG_MOVE_MIN_SCORE", "25"))
    history_keep_hours: float = float(os.getenv("HISTORY_KEEP_HOURS", "36"))
    snapshot_compact: bool = True
    # حداقل پوشش زمانی (ثانیه) برای معتبر دانستن جریان
    flow_min_coverage_sec: float = float(os.getenv("FLOW_MIN_COVERAGE_SEC", "120"))
    # اجازه bootstrap مصنوعی فقط وقتی منبع mock/synthetic است
    allow_history_bootstrap: bool = _env_bool("ALLOW_HISTORY_BOOTSTRAP", "1")

    # اعلان
    notify_enabled: bool = _env_bool("NOTIFY_ENABLED", "0")
    # هشدار روی داده synthetic/mixed فقط اگر صریحاً مجاز باشد
    notify_allow_synthetic: bool = _env_bool("NOTIFY_ALLOW_SYNTHETIC", "0")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    bale_bot_token: str = os.getenv("BALE_BOT_TOKEN", "")
    bale_chat_id: str = os.getenv("BALE_CHAT_ID", "")
    notify_min_entry: float = float(os.getenv("NOTIFY_MIN_ENTRY", "80"))
    notify_min_exit: float = float(os.getenv("NOTIFY_MIN_EXIT", "70"))
    notify_cooldown_sec: int = int(os.getenv("NOTIFY_COOLDOWN_SEC", "900"))
    ws_broadcast_on_refresh: bool = True

    # امنیت - P0-3 Fix: Default CORS سختگیرانه، نه باز
    api_key: str = os.getenv("API_KEY", "")
    # رمز ورود حالت خصوصی (اگر خالی باشد، API_KEY نقش رمز را دارد)
    private_password: str = os.getenv("PRIVATE_PASSWORD", "")
    # حالت خصوصی: همه /api قفل می‌شوند و فقط مالک (با ورود) می‌بیند
    private_mode: bool = _env_bool("PRIVATE_MODE", "0")
    # فقط وقتی پشت پروکسی معکوس مطمئن (Nginx/Caddy) هستید true بگذارید —
    # در غیر این صورت X-Forwarded-For توسط هر کلاینتی قابل جعل است و rate limit دور می‌زند
    trust_proxy: bool = _env_bool("TRUST_PROXY", "0")
    # کوکی نشست فقط روی HTTPS (در استقرار واقعی =1 بگذارید)
    cookie_secure: bool = _env_bool("COOKIE_SECURE", "0")
    # اگر API_KEY ست باشد، مسیرهای حساس نیاز به هدر X-API-Key دارند
    auth_required: bool = _env_bool("AUTH_REQUIRED", "0") or bool(os.getenv("API_KEY", "").strip()) or _env_bool("PRIVATE_MODE", "0")
    # FIX: default CORS = localhost only, نه * . در prod باید از env ست شود
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000")
    # trust level override اختیاری
    trust_level_override: str = os.getenv("TRUST_LEVEL", "")  # synthetic|mixed|live|""

    # AI-2 second-stage analysis (Category A offline scaffold).
    # Real-data AI-2 additionally requires is_verified_live(data_trust) —
    # which cannot be minted in this repository today — plus G2 independent
    # validation and owner acceptance (governance gate, NOT_PASSED).
    ai2_enabled: bool = _env_bool("AI2_ENABLED", "0")

    # Runtime G2 gate (GOV-32 Phase 3C): location of the tracked formal
    # gate-state document. Empty = repository default
    # (docs/active/G2_GATE_STATE.json). The override changes WHERE the state
    # is read from, never the verdict; missing/malformed state denies.
    g2_gate_state_path: str = os.getenv("G2_GATE_STATE_PATH", "")
    # Commit of the running source, injected at build/deploy time for the
    # gate's staleness binding (convened review commit must match). Empty at
    # runtimes that cannot bind their commit — the gate then denies any
    # PASSED state as stale (fail-closed), while the honest NOT_PASSED state
    # denies by verdict regardless.
    runtime_commit: str = os.getenv("RADAR_RUNTIME_COMMIT", "")

    # کش بنیادی (ثانیه)
    fundamental_cache_ttl_sec: int = int(os.getenv("FUND_CACHE_TTL", "300"))

    # P0-3: رمزنگاری توکن‌ها
    fernet_key: str = os.getenv("FERNET_KEY", "")
    
    # P2-10: Rate limit
    rate_limit_enabled: bool = _env_bool("RATE_LIMIT_ENABLED", "1")
    
    # P2-8: Timezone - بورس تهران
    timezone: str = os.getenv("TZ", "Asia/Tehran")
    
    # P1-3: DB settings
    db_backup_enabled: bool = _env_bool("DB_BACKUP", "1")

    cache_path: Path = DATA_DIR / "market_cache.json"
    history_path: Path = DATA_DIR / "history_snapshots.jsonl"
    db_path: Path = DATA_DIR / "shekar.db"

    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "*").strip()
        if raw == "*":
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_verified_live(data_trust: dict[str, Any] | None) -> bool:
    """Independent LIVE gate. All three flags must be explicitly true.

    `live_verified` is never inferred from source label or freshness.
    """
    if not isinstance(data_trust, dict):
        return False
    return (
        str(data_trust.get("state") or "").lower() == "live"
        and data_trust.get("is_live") is True
        and data_trust.get("live_verified") is True
    )


def classify_data_trust_state(source: str, settings: Settings | None = None) -> DataTrustState:
    """Canonical source-state classification for product UX.

    This function classifies the source/provenance label only. Freshness
    overrides such as `stale` and missing-data overrides such as `unavailable`
    are applied by `build_data_trust_context`, where timestamps and provider
    errors are available.

    Configuration is not market evidence: TRUST_LEVEL=live cannot force a
    live classification. Downgrade overrides (mixed/synthetic) remain allowed.
    """
    s = settings or get_settings()
    override = (s.trust_level_override or "").strip().lower()
    if override == "live":
        # Configuration ≠ market evidence. Ignore live override.
        override = ""
    if override == "mixed":
        return "mixed"
    if override == "synthetic":
        return "synthetic"

    src = (source or "").strip().lower()
    if src in {"tsetmc", "brsapi", "tsetmc_legacy"}:
        return "live"
    if "mock" in src:
        return "mock"
    if "synthetic" in src or "bootstrap" in src or "demo" in src:
        return "synthetic"
    if src in {"unavailable", "no_data", "none_no_data"}:
        return "unavailable"
    if src in {"cache", "auto", "unknown", "none", ""}:
        return "mixed"
    return "mixed"


def _legacy_trust_level_from_state(state: DataTrustState) -> str:
    if state == "live":
        return "live"
    if state in {"mixed", "stale", "unavailable"}:
        return "mixed"
    return "synthetic"


def resolve_trust_level(source: str, settings: Settings | None = None) -> str:
    """Backward-compatible trust level: synthetic | mixed | live."""
    return _legacy_trust_level_from_state(classify_data_trust_state(source, settings))


def _coerce_ts(value: float | int | str | None) -> float | None:
    if value is None:
        return None
    try:
        ts = float(value)
        return ts if ts > 0 else None
    except (TypeError, ValueError):
        return None


def build_data_trust_context(
    source: str,
    *,
    timestamp: float | int | str | None = None,
    provider: str | None = None,
    quality: dict[str, Any] | None = None,
    settings: Settings | None = None,
    checked_at: float | int | str | None = None,
    stale_after_sec: float | int | None = None,
    fallback_source: str | None = None,
    error_code: str | None = None,
    warning: str | None = None,
    live_verified: bool = False,
) -> dict[str, Any]:
    """Canonical market-data trust context for API/service responses.

    `timestamp` is the best available source/fetch timestamp. It is never
    fabricated. `checked_at` is the local time at which the trust check runs.
    `trust_level` remains backward-compatible while `state` carries the richer
    P3.31 taxonomy.

    `live_verified` is accepted only as an unused compatibility argument.
    No caller — including tests — can mint verified LIVE through this function.
    Independent live verification requires a future provider-verification
    boundary that does not exist in this environment.
    """
    import time

    s = settings or get_settings()
    checked = _coerce_ts(checked_at) or time.time()
    ts = _coerce_ts(timestamp)
    stale_after = float(stale_after_sec if stale_after_sec is not None else getattr(s, "data_stale_after_sec", 300))
    base_state = classify_data_trust_state(source, s)
    src = (source or "").strip() or "unknown"
    provider_name = provider or source or "unknown"
    age_sec = round(checked - ts, 3) if ts is not None else None
    stale = bool(age_sec is not None and age_sec > stale_after)
    future_timestamp = bool(age_sec is not None and age_sec < -float(getattr(s, "data_clock_skew_tolerance_sec", 0)))

    state: DataTrustState = base_state
    # Missing data with no usable timestamp is unavailable unless it is an
    # explicit mock/synthetic fallback source. A live-labelled source without
    # a usable timestamp is downgraded to mixed because freshness cannot be
    # proven.
    if base_state == "mixed" and src.lower() in {"none", "unknown", "", "unavailable", "no_data"} and ts is None:
        state = "unavailable"
    elif base_state == "live" and ts is None:
        state = "mixed"
    elif base_state in {"live", "mixed"} and future_timestamp:
        state = "mixed"
    elif base_state in {"live", "mixed"} and stale:
        state = "stale"

    # Independent verification is never inferred from source label, freshness,
    # TRUST_LEVEL, fetch success, or an arbitrary live_verified=True argument.
    # This environment has no live-verification boundary.
    verified = False
    trust_level = _legacy_trust_level_from_state(state)
    if state == "live" and not verified:
        trust_level = "mixed"
    is_live = verified
    is_generated = state in {"mock", "synthetic"}

    msg = warning or ""
    if not msg:
        if verified:
            msg = "LIVE data: provider data is independently verified and within freshness threshold."
        elif state == "live":
            msg = "LIVE-CLASS source is not independently verified; not validated live market data."
        elif state == "mock":
            msg = "MOCK data: development/demo fallback, not validated live market data."
        elif state == "synthetic":
            msg = "SYNTHETIC data: generated/simulated, not validated live market data."
        elif state == "stale":
            msg = f"STALE data: last trusted timestamp is older than {int(stale_after)} seconds."
        elif state == "unavailable":
            msg = "UNAVAILABLE data: no usable provider data is currently available."
        else:
            msg = "MIXED data: provider trust is partial, cached, or not fully validated."
    if future_timestamp:
        msg = f"{msg} Timestamp is in the future and cannot be treated as verified live data."
    if fallback_source and state in {"mock", "synthetic", "mixed", "unavailable"}:
        msg = f"{msg} Fallback source: {fallback_source}."
    if error_code and state != "live":
        msg = f"{msg} Provider status: {error_code}."

    return {
        "state": state,
        "trust_level": trust_level,
        "source": src,
        "provider": provider_name,
        "timestamp": ts,
        "checked_at": checked,
        "age_sec": age_sec,
        "stale_after_sec": stale_after,
        "stale": stale,
        "future_timestamp": future_timestamp,
        "fallback_source": fallback_source or "",
        "error_code": error_code or "",
        "data_source_config": s.data_source,
        "is_live": is_live,
        "live_verified": verified,
        "is_generated": is_generated,
        "quality": quality or {},
        "warning": msg,
    }
