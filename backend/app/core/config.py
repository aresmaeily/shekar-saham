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
DataTrustState = Literal["live", "mixed", "mock", "synthetic"]


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "شکار سهام"
    app_name_en: str = "Shekar Saham"
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


def classify_data_trust_state(source: str, settings: Settings | None = None) -> DataTrustState:
    """LIVE / MIXED / MOCK / SYNTHETIC source classification for product UX.

    This is intentionally more granular than the legacy `trust_level` contract.
    Existing API clients still receive `trust_level` as live|mixed|synthetic,
    while `data_trust.state` can distinguish mock from synthetic.
    """
    s = settings or get_settings()
    override = (s.trust_level_override or "").strip().lower()
    if override == "live":
        return "live"
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
    if src in {"cache", "auto", "unknown", "none", ""}:
        return "mixed"
    return "mixed"


def resolve_trust_level(source: str, settings: Settings | None = None) -> str:
    """Backward-compatible trust level: synthetic | mixed | live."""
    state = classify_data_trust_state(source, settings)
    if state == "live":
        return "live"
    if state == "mixed":
        return "mixed"
    return "synthetic"


def build_data_trust_context(
    source: str,
    *,
    timestamp: float | None = None,
    provider: str | None = None,
    quality: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Canonical market-data trust context for API/service responses.

    The context separates the current product state from provider claims:
    mock/synthetic data can never be presented as live.
    """
    s = settings or get_settings()
    state = classify_data_trust_state(source, s)
    trust_level = resolve_trust_level(source, s)
    is_live = state == "live"
    is_generated = state in {"mock", "synthetic"}
    warning = ""
    if state == "mock":
        warning = "MOCK data: development/demo fallback, not validated live market data."
    elif state == "synthetic":
        warning = "SYNTHETIC data: generated/simulated, not validated live market data."
    elif state == "mixed":
        warning = "MIXED data: provider trust is partial, cached, or not fully validated."
    return {
        "state": state,
        "trust_level": trust_level,
        "source": source or "unknown",
        "provider": provider or source or "unknown",
        "timestamp": timestamp,
        "data_source_config": s.data_source,
        "is_live": is_live,
        "is_generated": is_generated,
        "quality": quality or {},
        "warning": warning,
    }
