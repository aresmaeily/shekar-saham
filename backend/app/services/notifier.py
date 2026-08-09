"""ارسال هشدار به تلگرام و بله — v0.6.0 Secure with encryption"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.core.crypto import decrypt_token, encrypt_token, is_encrypted
from app.data.store import store

logger = logging.getLogger("shekar.notify")


class Notifier:
    def __init__(self) -> None:
        self.last_error: str = ""
        self.sent_count = 0
        self._dedupe: dict[str, float] = {}
        self._last_no_channel_log = 0.0

    def _get_decrypted_token(self, key: str) -> str:
        """Get token from settings with decryption support for v0.6"""
        saved = store.get_setting("notifier", {}) or {}
        raw = saved.get(key)
        if raw:
            # If stored encrypted, decrypt
            if isinstance(raw, str) and is_encrypted(raw):
                try:
                    return decrypt_token(raw)
                except Exception:
                    return ""
            # If looks like encrypted but not marked, try decrypt
            if isinstance(raw, str) and len(raw) > 20:
                # Try decrypt, if fails return raw (migration)
                try:
                    dec = decrypt_token(raw)
                    if dec:
                        return dec
                except Exception:
                    pass
                return raw
            return str(raw) if raw else ""
        
        # Fallback to env
        env_map = {
            "telegram_token": "TELEGRAM_BOT_TOKEN",
            "bale_token": "BALE_BOT_TOKEN",
        }
        env_key = env_map.get(key)
        if env_key:
            return os.getenv(env_key, getattr(get_settings(), f"{key.replace('_token','_bot_token')}" if 'telegram' in key else f"{key.replace('_token','_bot_token')}", "") if hasattr(get_settings(), key) else os.getenv(env_key, ""))
        return ""

    def _cfg(self) -> dict[str, Any]:
        saved = store.get_setting("notifier", {}) or {}
        s = get_settings()
        
        # Decrypt tokens properly
        tg_token = ""
        bale_token = ""
        try:
            # Try encrypted storage first
            tg_raw = saved.get("telegram_token") or s.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
            if tg_raw and is_encrypted(tg_raw):
                tg_token = decrypt_token(tg_raw)
            else:
                tg_token = tg_raw or os.getenv("TELEGRAM_BOT_TOKEN", s.telegram_bot_token)
        except Exception:
            tg_token = saved.get("telegram_token") or ""
        
        try:
            bale_raw = saved.get("bale_token") or s.bale_bot_token or os.getenv("BALE_BOT_TOKEN", "")
            if bale_raw and is_encrypted(bale_raw):
                bale_token = decrypt_token(bale_raw)
            else:
                bale_token = bale_raw or os.getenv("BALE_BOT_TOKEN", s.bale_bot_token)
        except Exception:
            bale_token = saved.get("bale_token") or ""

        return {
            "enabled": bool(
                saved.get("enabled")
                if "enabled" in saved
                else getattr(s, "notify_enabled", False)
            ),
            "telegram_token": tg_token,
            "telegram_chat_id": str(
                saved.get("telegram_chat_id")
                or os.getenv("TELEGRAM_CHAT_ID", getattr(s, "telegram_chat_id", ""))
            ),
            "bale_token": bale_token,
            "bale_chat_id": str(
                saved.get("bale_chat_id")
                or os.getenv("BALE_CHAT_ID", getattr(s, "bale_chat_id", ""))
            ),
            "min_entry_score": float(saved.get("min_entry_score", getattr(s, "notify_min_entry", 80))),
            "min_exit_score": float(saved.get("min_exit_score", getattr(s, "notify_min_exit", 70))),
            "min_combo_buy": float(saved.get("min_combo_buy", 70)),
            "min_combo_sell": float(saved.get("min_combo_sell", 65)),
            "cooldown_sec": int(saved.get("cooldown_sec", getattr(s, "notify_cooldown_sec", 900))),
            "portfolio_only": bool(saved.get("portfolio_only", False)),
            "confluence_enabled": bool(saved.get("confluence_enabled", True)),
            "legacy_tablo_alerts": bool(saved.get("legacy_tablo_alerts", False)),
            "allow_synthetic": bool(
                saved.get(
                    "allow_synthetic",
                    getattr(get_settings(), "notify_allow_synthetic", False),
                )
            ),
        }

    def get_public_config(self) -> dict[str, Any]:
        c = self._cfg()
        # Never return actual token
        return {
            "enabled": c["enabled"],
            "telegram_configured": bool(c["telegram_token"] and c["telegram_chat_id"]),
            "bale_configured": bool(c["bale_token"] and c["bale_chat_id"]),
            "telegram_chat_id": c["telegram_chat_id"],
            "bale_chat_id": c["bale_chat_id"],
            "min_entry_score": c["min_entry_score"],
            "min_exit_score": c["min_exit_score"],
            "min_combo_buy": c["min_combo_buy"],
            "min_combo_sell": c["min_combo_sell"],
            "cooldown_sec": c["cooldown_sec"],
            "portfolio_only": c["portfolio_only"],
            "confluence_enabled": c["confluence_enabled"],
            "legacy_tablo_alerts": c["legacy_tablo_alerts"],
            "allow_synthetic": c.get("allow_synthetic", False),
            "sent_count": self.sent_count,
            "last_error": self.last_error,
            "telegram_token_set": bool(c["telegram_token"]),
            "bale_token_set": bool(c["bale_token"]),
            "security": "encrypted_at_rest" if c["telegram_token"] or c["bale_token"] else "none",
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        cur = store.get_setting("notifier", {}) or {}
        if not isinstance(cur, dict):
            cur = {}
        allowed = {
            "enabled",
            "telegram_token",
            "telegram_chat_id",
            "bale_token",
            "bale_chat_id",
            "min_entry_score",
            "min_exit_score",
            "min_combo_buy",
            "min_combo_sell",
            "min_value_score",
            "cooldown_sec",
            "portfolio_only",
            "confluence_enabled",
            "legacy_tablo_alerts",
            "allow_synthetic",
        }
        for k, v in payload.items():
            if k in allowed and v is not None:
                if k in {"telegram_token", "bale_token"} and str(v).strip() == "":
                    continue
                # P0-3: Encrypt tokens at rest
                if k in {"telegram_token", "bale_token"} and str(v).strip():
                    try:
                        # Only encrypt if not already encrypted
                        if not is_encrypted(str(v)):
                            cur[k] = encrypt_token(str(v).strip())
                        else:
                            cur[k] = str(v).strip()
                    except Exception as exc:
                        logger.warning(f"Failed to encrypt token {k}: {exc}")
                        cur[k] = encrypt_token(str(v).strip())
                else:
                    cur[k] = v
        store.set_setting("notifier", cur)
        logger.info("notifier config updated - tokens encrypted at rest")
        return self.get_public_config()

    def _allow(self, key: str, cooldown: int) -> bool:
        now = time.time()
        last = self._dedupe.get(key, 0)
        if now - last < cooldown:
            return False
        self._dedupe[key] = now
        if len(self._dedupe) > 2000:
            cut = now - cooldown * 2
            self._dedupe = {k: t for k, t in self._dedupe.items() if t >= cut}
        return True

    async def _post_telegram(self, token: str, chat_id: str, text: str) -> bool:
        if not token or not chat_id:
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                r = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                if r.status_code >= 400:
                    self.last_error = f"telegram {r.status_code}: {r.text[:200]}"
                    logger.warning(self.last_error)
                    return False
                return True
        except Exception as exc:
            err_id = uuid.uuid4().hex[:6]
            self.last_error = f"telegram error [{err_id}]: {exc}"
            logger.warning(self.last_error)
            return False

    async def _post_bale(self, token: str, chat_id: str, text: str) -> bool:
        if not token or not chat_id:
            return False
        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                r = await client.post(url, json={"chat_id": chat_id, "text": text})
                if r.status_code >= 400:
                    self.last_error = f"bale {r.status_code}: {r.text[:200]}"
                    logger.warning(self.last_error)
                    return False
                return True
        except Exception as exc:
            err_id = uuid.uuid4().hex[:6]
            self.last_error = f"bale error [{err_id}]: {exc}"
            logger.warning(self.last_error)
            return False

    def format_alert(self, alert: dict[str, Any]) -> str:
        side = alert.get("side") or alert.get("action")
        if side in {"buy", "entry"}:
            emoji, title = "🟢", "هشدار خرید"
            if alert.get("action") == "buy" or side == "buy":
                title = "هشدار خرید ترکیبی"
        elif side in {"sell", "exit"}:
            emoji, title = "🔴", "هشدار فروش"
            if alert.get("action") == "sell" or side == "sell":
                title = "هشدار فروش ترکیبی"
        else:
            emoji, title = "⚪", "هشدار"

        sym = alert.get("symbol", "")
        name = alert.get("name") or ""
        score = alert.get("score", "")
        plp = alert.get("plp", "")
        pe = alert.get("pe")
        value_score = alert.get("value_score")
        flow_score = alert.get("flow_score")
        flow_side = alert.get("flow_side")
        reasons = alert.get("reasons") or []
        tags = alert.get("tags") or []
        trust = alert.get("trust_level") or ""

        # P0-1: Add trust level prominently
        trust_prefix = ""
        if trust == "synthetic":
            trust_prefix = "⚠️ [DEMO/SYNTHETIC] - داده آزمایشی\n"
        elif trust == "mixed":
            trust_prefix = "⚠️ [MIXED] - بخشی از داده آزمایشی است\n"

        lines = [
            f"{trust_prefix}{emoji} <b>{title}</b>",
            f"نماد: <b>{sym}</b>" + (f" — {name}" if name else ""),
            f"امتیاز ترکیبی: <b>{score}</b> | درصد: {plp}",
        ]
        if pe is not None:
            lines.append(f"P/E: {pe}" + (f" | بنیادی: {value_score}" if value_score is not None else ""))
        elif value_score is not None:
            lines.append(f"بنیادی/ارزندگی: {value_score}")
        if flow_score is not None:
            fs = "ورود پول" if flow_side == "inflow" else "خروج پول" if flow_side == "outflow" else "جریان"
            lines.append(f"جریان ۱۰دقیقه: {fs} ({flow_score})")
        if alert.get("entry_score") is not None and side in {"buy", "entry"}:
            lines.append(f"امتیاز ورود تابلو: {alert.get('entry_score')}")
        if alert.get("exit_score") is not None and side in {"sell", "exit"}:
            lines.append(f"امتیاز خروج تابلو: {alert.get('exit_score')}")
        if tags:
            lines.append("تگ: " + " · ".join(map(str, tags[:8])))
        if reasons:
            lines.append("دلایل:")
            for r in reasons[:5]:
                lines.append(f"• {r}")
        lines.append("— رادار بورس | جمع‌بندی تابلو+بنیادی+جریان")
        if trust != "live":
            lines.append("⚠️ هشدار: این پیام مبتنی بر داده آزمایشی است، مبنای معامله قرار ندهید.")
        return "\n".join(lines)

    async def send_text(self, text: str, channels: Optional[list[str]] = None) -> dict[str, Any]:
        c = self._cfg()
        channels = channels or ["telegram", "bale"]
        result: dict[str, Any] = {"telegram": None, "bale": None}
        if "telegram" in channels and c["telegram_token"] and c["telegram_chat_id"]:
            ok = await self._post_telegram(c["telegram_token"], c["telegram_chat_id"], text)
            result["telegram"] = ok
            if ok:
                self.sent_count += 1
        if "bale" in channels and c["bale_token"] and c["bale_chat_id"]:
            ok = await self._post_bale(c["bale_token"], c["bale_chat_id"], text)
            result["bale"] = ok
            if ok:
                self.sent_count += 1
        
        # P1-5 Fix: No dry-run spam if enabled but no channel
        if result["telegram"] is None and result["bale"] is None:
            now = time.time()
            # Only log dry-run once per 5 min to avoid spam
            if now - self._last_no_channel_log > 300:
                store.save_notify_log({"channel": "dry-run", "text": text[:800], "ok": True})
                logger.info(f"notify dry-run: {text[:140].replace(chr(10), ' | ')}")
                self._last_no_channel_log = now
            result["dry_run"] = True
        else:
            store.save_notify_log(
                {"channel": "multi", "text": text[:800], "ok": True, "result": result}
            )
        return result

    async def process_alerts(
        self,
        entry_cards: list[Any],
        exit_cards: list[Any],
        portfolio_symbols: Optional[set[str]] = None,
        confluence_alerts: Optional[list[dict[str, Any]]] = None,
        trust_level: str = "mixed",
    ) -> int:
        c = self._cfg()
        if not c["enabled"]:
            return 0
        
        has_channel = bool(
            (c.get("telegram_token") and c.get("telegram_chat_id"))
            or (c.get("bale_token") and c.get("bale_chat_id"))
        )
        settings = get_settings()
        allow_synth = bool(c.get("allow_synthetic") or getattr(settings, "notify_allow_synthetic", False))
        
        # P0-1: Block synthetic unless explicitly allowed
        if trust_level == "synthetic" and not allow_synth:
            logger.info("notify skipped: trust_level=synthetic and NOTIFY_ALLOW_SYNTHETIC=0")
            store.save_notify_log(
                {
                    "channel": "blocked",
                    "text": "blocked synthetic alerts",
                    "ok": False,
                    "trust_level": trust_level,
                }
            )
            return 0
        
        if not has_channel and not allow_synth:
            key = "no-channel"
            if self._allow(key, max(c["cooldown_sec"], 300)):
                logger.warning("notify enabled but no telegram/bale channel configured - suppressing spam")
            return 0

        portfolio_symbols = portfolio_symbols or set()
        sent = 0
        demo_prefix_needed = trust_level != "live"

        if c.get("confluence_enabled", True) and confluence_alerts:
            for alert in confluence_alerts:
                sym = alert.get("symbol", "")
                if c["portfolio_only"] and sym not in portfolio_symbols:
                    continue
                side = alert.get("action") or alert.get("side") or "buy"
                score = float(alert.get("score") or 0)
                if side == "buy" and score < c["min_combo_buy"]:
                    continue
                if side == "sell" and score < c["min_combo_sell"]:
                    continue
                key = f"combo:{side}:{sym}"
                if not self._allow(key, c["cooldown_sec"]):
                    continue
                
                # Add trust level to alert for formatting
                alert_with_trust = {**alert, "trust_level": trust_level}
                text = self.format_alert({**alert_with_trust, "side": side, "action": side})
                await self.send_text(text)
                try:
                    store.save_alerts(
                        [
                            {
                                "symbol": sym,
                                "side": f"combo_{side}",
                                "score": score,
                                "plp": alert.get("plp"),
                                "reasons": alert.get("reasons") or [],
                                "tags": (alert.get("tags") or []) + (["DEMO"] if demo_prefix_needed else []),
                                "payload": {**alert, "trust_level": trust_level},
                            }
                        ]
                    )
                except Exception:
                    pass
                sent += 1

        if not c.get("legacy_tablo_alerts", False):
            return sent

        def _iter(cards, side: str, min_score: float):
            for card in cards:
                if hasattr(card, "model_dump"):
                    d = card.model_dump()
                elif isinstance(card, dict):
                    d = card
                else:
                    continue
                score = d.get("entry_score") if side == "entry" else d.get("exit_score")
                score = d.get("score", score)
                if score is None or float(score) < min_score:
                    continue
                sym = d.get("symbol", "")
                if c["portfolio_only"] and sym not in portfolio_symbols:
                    continue
                yield {
                    "symbol": sym,
                    "side": side,
                    "score": score,
                    "plp": d.get("plp"),
                    "reasons": d.get("reasons") or [],
                    "tags": d.get("tags") or [],
                    "trust_level": trust_level,
                }

        for alert in list(_iter(entry_cards, "entry", c["min_entry_score"])) + list(
            _iter(exit_cards, "exit", c["min_exit_score"])
        ):
            key = f"{alert['side']}:{alert['symbol']}"
            if not self._allow(key, c["cooldown_sec"]):
                continue
            text = self.format_alert(alert)
            await self.send_text(text)
            sent += 1
        return sent


notifier = Notifier()
