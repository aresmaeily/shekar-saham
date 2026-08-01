"""آستانه‌های قابل‌تغییر در runtime (از UI) روی Settings پایه."""

from __future__ import annotations

import threading
from typing import Any

from app.core.config import Settings, get_settings
from app.data.store import store

EDITABLE_KEYS = [
    "hot_money_threshold",
    "hot_money_plus_min",
    "hot_money_plus_max",
    "volume_spike_ratio",
    "volume_spike_strong",
    "buy_power_min",
    "buy_power_strong",
    "smart_per_capita_min",
    "near_buy_queue_pct",
    "negative_plp_max",
    "deep_negative_plp",
    "pe_max_attractive",
    "pe_max_ok",
    "entry_score_alert",
    "entry_score_strong",
    "exit_score_alert",
    "poll_seconds",
    "big_move_window_sec",
    "big_move_min_score",
]

_lock = threading.RLock()
_overrides: dict[str, Any] = {}
_loaded = False


def _load_once() -> None:
    global _loaded, _overrides
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        saved = store.get_setting("thresholds", {}) or {}
        if isinstance(saved, dict):
            _overrides = {k: v for k, v in saved.items() if k in EDITABLE_KEYS}
        _loaded = True


def get_effective_settings() -> Settings:
    _load_once()
    base = get_settings()
    with _lock:
        if not _overrides:
            return base
        return base.model_copy(update=_overrides)


def get_thresholds_public() -> dict[str, Any]:
    cfg = get_effective_settings()
    out: dict[str, Any] = {}
    for k in EDITABLE_KEYS:
        if hasattr(cfg, k):
            out[k] = getattr(cfg, k)
    out["data_source"] = get_settings().data_source
    return out


def update_thresholds(payload: dict[str, Any]) -> dict[str, Any]:
    _load_once()
    cleaned: dict[str, Any] = {}
    for k, v in payload.items():
        if k not in EDITABLE_KEYS:
            continue
        if v is None or v == "":
            continue
        try:
            if k in {"poll_seconds", "big_move_window_sec"}:
                cleaned[k] = int(float(v))
            else:
                cleaned[k] = float(v)
        except (TypeError, ValueError):
            continue
    with _lock:
        _overrides.update(cleaned)
        merged = dict(_overrides)
    store.set_setting("thresholds", merged)
    return get_thresholds_public()


def reset_thresholds() -> dict[str, Any]:
    global _overrides
    _load_once()
    with _lock:
        _overrides = {}
    store.set_setting("thresholds", {})
    return get_thresholds_public()
