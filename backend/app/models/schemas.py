from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SignalSide(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    WATCH = "watch"
    NEUTRAL = "neutral"


class AlertLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataTrustState(str, Enum):
    """Canonical data-trust states for Iran market data contracts."""

    LIVE = "live"
    MIXED = "mixed"
    MOCK = "mock"
    SYNTHETIC = "synthetic"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class MarketDataProvenance(BaseModel):
    """Provider/source metadata carried by market-intelligence outputs."""

    source: str = "unknown"
    provider: str = "unknown"
    trust_state: DataTrustState = DataTrustState.MIXED
    trust_level: str = "mixed"  # backward-compatible: live | mixed | synthetic
    timestamp: Optional[datetime] = None
    data_source_config: str = "auto"
    is_live: bool = False
    is_generated: bool = False
    warning: str = ""
    quality: dict[str, Any] = Field(default_factory=dict)


class IranInstrument(BaseModel):
    """Stable symbol/instrument representation for the Iran market domain."""

    symbol: str
    name: str = ""
    isin: str = ""
    instrument_id: str = ""
    industry: str = ""
    industry_id: str = ""
    market: str = "TSE"
    source: str = "unknown"
    updated_at: Optional[datetime] = None

    @classmethod
    def from_snapshot(cls, s: "SymbolSnapshot") -> "IranInstrument":
        return cls(
            symbol=s.l18,
            name=s.l30,
            isin=s.isin,
            instrument_id=s.id,
            industry=s.cs,
            industry_id=s.cs_id,
            source=s.source,
            updated_at=s.updated_at,
        )


class MarketSession(BaseModel):
    """Iran market session metadata. Current code does not infer open/closed state."""

    timezone: str = "Asia/Tehran"
    session_date: str = ""
    is_open: Optional[bool] = None
    status: str = "unknown"  # unknown | pre_open | open | closed | holiday


class OHLCVBar(BaseModel):
    """Normalized OHLCV candle contract used by chart/history boundaries."""

    time: int | str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    source: str = "unknown"
    trust_state: DataTrustState = DataTrustState.MIXED


class OrderBookLevel(BaseModel):
    count: int = 0
    volume: int = 0
    price: float = 0.0


class SymbolSnapshot(BaseModel):
    """تابلوی لحظه‌ای یک نماد — نام‌گذاری نزدیک به tsetmc/BrsApi."""

    time: str = ""
    l18: str  # نماد
    l30: str = ""  # نام
    isin: str = ""
    id: str = ""
    cs: str = ""  # صنعت
    cs_id: str = ""
    z: float = 0  # تعداد سهام
    bvol: float = 0  # حجم مبنا
    mv: float = 0  # ارزش بازار
    eps: Optional[float] = None
    pe: Optional[float] = None

    tmin: float = 0
    tmax: float = 0
    pmin: float = 0
    pmax: float = 0
    py: float = 0
    pf: float = 0
    pl: float = 0
    plc: float = 0
    plp: float = 0
    pc: float = 0
    pcc: float = 0
    pcp: float = 0

    tno: int = 0
    tvol: float = 0
    tval: float = 0

    Buy_CountI: int = 0
    Buy_CountN: int = 0
    Sell_CountI: int = 0
    Sell_CountN: int = 0
    Buy_I_Volume: float = 0
    Buy_N_Volume: float = 0
    Sell_I_Volume: float = 0
    Sell_N_Volume: float = 0

    # پنج ردیف تقاضا/عرضه
    zd1: int = 0
    qd1: float = 0
    pd1: float = 0
    zo1: int = 0
    qo1: float = 0
    po1: float = 0
    zd2: int = 0
    qd2: float = 0
    pd2: float = 0
    zo2: int = 0
    qo2: float = 0
    po2: float = 0
    zd3: int = 0
    qd3: float = 0
    pd3: float = 0
    zo3: int = 0
    qo3: float = 0
    po3: float = 0
    zd4: int = 0
    qd4: float = 0
    pd4: float = 0
    zo4: int = 0
    qo4: float = 0
    po4: float = 0
    zd5: int = 0
    qd5: float = 0
    pd5: float = 0
    zo5: int = 0
    qo5: float = 0
    po5: float = 0

    # میانگین حجم تقریبی ماه (از تاریخچه یا شبیه‌سازی)
    avg_vol_30d: float = 0
    avg_val_30d: float = 0

    # متادیتای داخلی
    source: str = "unknown"
    updated_at: Optional[datetime] = None


class DerivedMetrics(BaseModel):
    symbol: str
    # سرانه
    buy_per_capita: float = 0.0  # ارزش تقریبی سرانه خرید حقیقی
    sell_per_capita: float = 0.0
    buy_power: float = 0.0  # سرانه خرید / سرانه فروش
    # جریان پول حقیقی
    individual_net_volume: float = 0.0
    individual_net_value: float = 0.0
    legal_to_individual: float = 0.0  # تقریبی جابجایی
    # حجم
    volume_ratio: float = 0.0  # tvol / avg
    value_ratio: float = 0.0
    is_volume_spike: bool = False
    is_strong_volume_spike: bool = False
    # صف و محدوده
    dist_to_ceiling_pct: float = 0.0
    dist_to_floor_pct: float = 0.0
    near_buy_queue: bool = False
    near_sell_queue: bool = False
    in_buy_queue: bool = False
    in_sell_queue: bool = False
    # پول داغ تقریبی (از سرانه و تعداد)
    hot_buy_score: float = 0.0
    hot_sell_score: float = 0.0
    hot_net: float = 0.0
    # بازی بازار (تقسیم فرضی)
    big_player_bias: float = 0.0  # -1 .. +1
    mid_player_bias: float = 0.0
    retail_bias: float = 0.0
    # بنیادی
    pe_score: float = 0.0
    fundamental_ok: bool = False
    fundamental_note: str = ""
    # امتیاز نهایی
    entry_score: float = 0.0
    exit_score: float = 0.0
    watch_score: float = 0.0
    side: SignalSide = SignalSide.NEUTRAL
    alert_level: AlertLevel = AlertLevel.LOW
    reasons: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SignalCard(BaseModel):
    symbol: str
    name: str
    industry: str
    side: SignalSide
    alert_level: AlertLevel
    entry_score: float
    exit_score: float
    pl: float
    plp: float
    pe: Optional[float]
    buy_power: float
    volume_ratio: float
    individual_net_value: float
    hot_net: float
    near_buy_queue: bool
    reasons: list[str]
    tags: list[str]
    updated_at: Optional[datetime] = None


class HotMoneyRow(BaseModel):
    symbol: str
    name: str
    industry: str
    side: str  # buy | sell
    estimated_value: float
    per_capita: float
    buy_power: float
    plp: float
    volume_ratio: float
    repeat_buy: int = 0
    repeat_sell: int = 0
    hot_net: float = 0
    score: float = 0
    tier: str = "hot"  # hot | plus
    flow_score: float = 0  # نمره ترکیبی جریان هوشمند ۰-۱۰۰


class MarketGameRow(BaseModel):
    symbol: str
    name: str
    industry: str
    big_bias: float
    mid_bias: float
    retail_bias: float
    dominant: str
    plp: float
    volume_ratio: float
    buy_power: float
    note: str = ""
    hunt_champion: bool = False  # قهرمان شکار: ورود پول هوشمند در قیمت منفی


class IndustryFlow(BaseModel):
    industry: str
    symbol_count: int
    avg_plp: float
    total_value: float
    net_individual_value: float
    avg_buy_power: float
    avg_volume_ratio: float
    entry_candidates: int
    score: float


class MarketOverview(BaseModel):
    as_of: datetime
    source: str
    symbol_count: int
    positive_count: int
    negative_count: int
    total_value: float
    entry_alerts: int
    exit_alerts: int
    volume_spikes: int
    hot_money_count: int
    top_industries: list[IndustryFlow] = Field(default_factory=list)
    thermometer: dict = Field(default_factory=dict)  # دماسنج بازار: {state, score, label, parts}


class AnalyzeResponse(BaseModel):
    overview: MarketOverview
    entry_signals: list[SignalCard]
    exit_signals: list[SignalCard]
    watchlist: list[SignalCard]
    hot_money: list[HotMoneyRow]
    hot_money_plus: list[HotMoneyRow]
    market_game: list[MarketGameRow]
    industries: list[IndustryFlow]
    all_metrics: list[DerivedMetrics] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
