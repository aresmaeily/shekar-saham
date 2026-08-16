"""لایه دریافت داده از TSETMC / BrsApi با fallback به mock - v0.6.0 Hardened"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.data.mock_market import generate_mock_market
from app.models.schemas import SymbolSnapshot

logger = logging.getLogger("shekar.providers")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _headers() -> dict[str, str]:
    return {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    }


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except (TypeError, ValueError):
        return default


def brsapi_row_to_snapshot(row: dict[str, Any]) -> SymbolSnapshot:
    return SymbolSnapshot(
        time=str(row.get("time") or ""),
        l18=str(row.get("l18") or "").strip(),
        l30=str(row.get("l30") or "").strip(),
        isin=str(row.get("isin") or ""),
        id=str(row.get("id") or ""),
        cs=str(row.get("cs") or ""),
        cs_id=str(row.get("cs_id") or ""),
        z=_safe_float(row.get("z")),
        bvol=_safe_float(row.get("bvol")),
        mv=_safe_float(row.get("mv")),
        eps=_safe_float(row.get("eps")) or None,
        pe=_safe_float(row.get("pe")) or None,
        tmin=_safe_float(row.get("tmin")),
        tmax=_safe_float(row.get("tmax")),
        pmin=_safe_float(row.get("pmin")),
        pmax=_safe_float(row.get("pmax")),
        py=_safe_float(row.get("py")),
        pf=_safe_float(row.get("pf")),
        pl=_safe_float(row.get("pl")),
        plc=_safe_float(row.get("plc")),
        plp=_safe_float(row.get("plp")),
        pc=_safe_float(row.get("pc")),
        pcc=_safe_float(row.get("pcc")),
        pcp=_safe_float(row.get("pcp")),
        tno=_safe_int(row.get("tno")),
        tvol=_safe_float(row.get("tvol")),
        tval=_safe_float(row.get("tval")),
        Buy_CountI=_safe_int(row.get("Buy_CountI")),
        Buy_CountN=_safe_int(row.get("Buy_CountN")),
        Sell_CountI=_safe_int(row.get("Sell_CountI")),
        Sell_CountN=_safe_int(row.get("Sell_CountN")),
        Buy_I_Volume=_safe_float(row.get("Buy_I_Volume")),
        Buy_N_Volume=_safe_float(row.get("Buy_N_Volume")),
        Sell_I_Volume=_safe_float(row.get("Sell_I_Volume")),
        Sell_N_Volume=_safe_float(row.get("Sell_N_Volume")),
        zd1=_safe_int(row.get("zd1")),
        qd1=_safe_float(row.get("qd1")),
        pd1=_safe_float(row.get("pd1")),
        zo1=_safe_int(row.get("zo1")),
        qo1=_safe_float(row.get("qo1")),
        po1=_safe_float(row.get("po1")),
        zd2=_safe_int(row.get("zd2")),
        qd2=_safe_float(row.get("qd2")),
        pd2=_safe_float(row.get("pd2")),
        zo2=_safe_int(row.get("zo2")),
        qo2=_safe_float(row.get("qo2")),
        po2=_safe_float(row.get("po2")),
        zd3=_safe_int(row.get("zd3")),
        qd3=_safe_float(row.get("qd3")),
        pd3=_safe_float(row.get("pd3")),
        zo3=_safe_int(row.get("zo3")),
        qo3=_safe_float(row.get("qo3")),
        po3=_safe_float(row.get("po3")),
        zd4=_safe_int(row.get("zd4")),
        qd4=_safe_float(row.get("qd4")),
        pd4=_safe_float(row.get("pd4")),
        zo4=_safe_int(row.get("zo4")),
        qo4=_safe_float(row.get("qo4")),
        po4=_safe_float(row.get("po4")),
        zd5=_safe_int(row.get("zd5")),
        qd5=_safe_float(row.get("qd5")),
        pd5=_safe_float(row.get("pd5")),
        zo5=_safe_int(row.get("zo5")),
        qo5=_safe_float(row.get("qo5")),
        po5=_safe_float(row.get("po5")),
        avg_vol_30d=_safe_float(row.get("avg_vol_30d")),
        avg_val_30d=_safe_float(row.get("avg_val_30d")),
        source="brsapi",
        updated_at=datetime.now(timezone.utc),
    )


def tsetmc_mw_to_snapshot(item: dict[str, Any]) -> Optional[SymbolSnapshot]:
    try:
        # CDN GetMarketWatch uses compressed keys: lva=نماد (lVal18), lvc=نام (lVal30).
        # Older payloads used lval18AFC / l18 / symbol. Empty ticker is rejected.
        l18 = str(
            item.get("lva")
            or item.get("lval18AFC")
            or item.get("l18")
            or item.get("symbol")
            or ""
        ).strip()
        if not l18:
            return None
        pl = _safe_float(item.get("pl") or item.get("last") or item.get("pDrCotVal"))
        pc = _safe_float(item.get("pc") or item.get("pClosing"))
        py = _safe_float(item.get("py") or item.get("priceYesterday") or item.get("yval"))
        if py <= 0:
            py = pc or pl
        plp = _safe_float(item.get("plp"))
        if not plp and py:
            plp = round((pl - py) / py * 100, 2) if pl else 0
        pcp = _safe_float(item.get("pcp"))
        if not pcp and py and pc:
            pcp = round((pc - py) / py * 100, 2)

        tvol = _safe_float(item.get("tvol") or item.get("qTotTran5J"))
        tval = _safe_float(item.get("tval") or item.get("qTotCap"))
        tno = _safe_int(item.get("tno") or item.get("zTotTran"))

        return SymbolSnapshot(
            time=str(item.get("hEven") or item.get("time") or ""),
            l18=l18,
            l30=str(item.get("lvc") or item.get("lVal30") or item.get("l30") or l18),
            isin=str(item.get("isin") or ""),
            id=str(item.get("insCode") or item.get("insID") or item.get("id") or ""),
            cs=str(item.get("lSecVal") or item.get("cs") or ""),
            cs_id=str(item.get("cgrValCot") or item.get("cs_id") or ""),
            z=_safe_float(item.get("z") or item.get("zTitad")),
            bvol=_safe_float(item.get("bvol") or item.get("baseVol") or item.get("bv")),
            mv=_safe_float(item.get("mv")),
            eps=_safe_float(item.get("eps")) or None,
            pe=_safe_float(item.get("pe") or item.get("peh")) or None,
            tmin=_safe_float(item.get("tmin") or item.get("priceMinThr")),
            tmax=_safe_float(item.get("tmax") or item.get("priceMaxThr")),
            pmin=_safe_float(item.get("pmin") or item.get("priceMin") or item.get("pMin") or item.get("pmn")),
            pmax=_safe_float(item.get("pmax") or item.get("priceMax") or item.get("pMax") or item.get("pmx")),
            py=py,
            pf=_safe_float(item.get("pf") or item.get("priceFirst")),
            pl=pl,
            plc=_safe_float(item.get("plc") or (pl - py if py else 0)),
            plp=plp,
            pc=pc,
            pcc=_safe_float(item.get("pcc") or (pc - py if py else 0)),
            pcp=pcp,
            tno=tno,
            tvol=tvol,
            tval=tval,
            Buy_CountI=_safe_int(item.get("Buy_CountI") or item.get("buy_I_Count")),
            Buy_CountN=_safe_int(item.get("Buy_CountN") or item.get("buy_N_Count")),
            Sell_CountI=_safe_int(item.get("Sell_CountI") or item.get("sell_I_Count")),
            Sell_CountN=_safe_int(item.get("Sell_CountN") or item.get("sell_N_Count")),
            Buy_I_Volume=_safe_float(item.get("Buy_I_Volume") or item.get("buy_I_Volume")),
            Buy_N_Volume=_safe_float(item.get("Buy_N_Volume") or item.get("buy_N_Volume")),
            Sell_I_Volume=_safe_float(item.get("Sell_I_Volume") or item.get("sell_I_Volume")),
            Sell_N_Volume=_safe_float(item.get("Sell_N_Volume") or item.get("sell_N_Volume")),
            zd1=_safe_int(item.get("zd1") or item.get("bestBuyDelivery")),
            qd1=_safe_float(item.get("qd1") or item.get("qTitMeDem")),
            pd1=_safe_float(item.get("pd1") or item.get("pMeDem")),
            zo1=_safe_int(item.get("zo1") or item.get("bestSellDelivery")),
            qo1=_safe_float(item.get("qo1") or item.get("qTitMeOf")),
            po1=_safe_float(item.get("po1") or item.get("pMeOf")),
            avg_vol_30d=_safe_float(item.get("avg_vol_30d") or item.get("avgVol") or 0.0),
            source="tsetmc",
            updated_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        logger.debug(f"tsetmc parse fail: {exc}")
        return None


class CircuitBreaker:
    """P1-4 Fix: جلوگیری از hammering منبع خراب - Meta pattern"""

    def __init__(self, fail_threshold: int = 3, reset_seconds: int = 120):
        self.fail_count = 0
        self.last_fail_ts = 0.0
        self.fail_threshold = fail_threshold
        self.reset_seconds = reset_seconds

    def should_skip(self) -> bool:
        if self.fail_count >= self.fail_threshold:
            if time.time() - self.last_fail_ts < self.reset_seconds:
                return True
            self.fail_count = 0
        return False

    def record_success(self):
        self.fail_count = 0

    def record_failure(self):
        self.fail_count += 1
        self.last_fail_ts = time.time()


class MarketDataProvider:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.last_source: str = "none"
        self.last_error: str = ""
        self._cache: list[SymbolSnapshot] = []
        self._cb_tsetmc = CircuitBreaker(fail_threshold=3, reset_seconds=180)
        self._cb_brsapi = CircuitBreaker(fail_threshold=2, reset_seconds=120)
        self._total_fetches = 0
        self._failed_fetches = 0
        self._uptime_metrics = {
            "tsetmc_success": 0,
            "tsetmc_fail": 0,
            "brsapi_success": 0,
            "brsapi_fail": 0,
            "mock_fallback": 0,
        }

    async def fetch(self) -> list[SymbolSnapshot]:
        mode = (self.settings.data_source or "auto").lower()
        self._total_fetches += 1

        if mode == "mock":
            return self._from_mock()
        if mode == "brsapi":
            if self._cb_brsapi.should_skip():
                logger.info("brsapi circuit breaker open, using mock fallback")
                self._uptime_metrics["mock_fallback"] += 1
                return self._from_mock(fallback=True)
            data = await self._from_brsapi()
            if data:
                self._cb_brsapi.record_success()
                self._uptime_metrics["brsapi_success"] += 1
                return data
            self._cb_brsapi.record_failure()
            self._uptime_metrics["brsapi_fail"] += 1
            self._failed_fetches += 1
            return self._from_mock(fallback=True)
        if mode == "tsetmc":
            if self._cb_tsetmc.should_skip():
                logger.info("tsetmc circuit breaker open, using mock fallback")
                self._uptime_metrics["mock_fallback"] += 1
                return self._from_mock(fallback=True)
            data = await self._from_tsetmc()
            if data:
                self._cb_tsetmc.record_success()
                self._uptime_metrics["tsetmc_success"] += 1
                return data
            self._cb_tsetmc.record_failure()
            self._uptime_metrics["tsetmc_fail"] += 1
            self._failed_fetches += 1
            return self._from_mock(fallback=True)

        # auto mode
        if not self._cb_tsetmc.should_skip():
            data = await self._from_tsetmc()
            if data:
                self._cb_tsetmc.record_success()
                self._uptime_metrics["tsetmc_success"] += 1
                return data
            self._cb_tsetmc.record_failure()
            self._uptime_metrics["tsetmc_fail"] += 1
        else:
            logger.debug("Skipping tsetmc due to circuit breaker")

        if not self._cb_brsapi.should_skip():
            data = await self._from_brsapi()
            if data:
                self._cb_brsapi.record_success()
                self._uptime_metrics["brsapi_success"] += 1
                return data
            self._cb_brsapi.record_failure()
            self._uptime_metrics["brsapi_fail"] += 1
        else:
            logger.debug("Skipping brsapi due to circuit breaker")

        self._failed_fetches += 1
        self._uptime_metrics["mock_fallback"] += 1
        return self._from_mock(fallback=True)

    def get_uptime_metrics(self) -> dict[str, Any]:
        total = self._total_fetches or 1
        return {
            **self._uptime_metrics,
            "total_fetches": self._total_fetches,
            "failed_fetches": self._failed_fetches,
            "success_rate": round((1 - self._failed_fetches / total) * 100, 2),
            "tsetmc_cb_open": self._cb_tsetmc.should_skip(),
            "brsapi_cb_open": self._cb_brsapi.should_skip(),
        }

    def _from_mock(self, fallback: bool = False) -> list[SymbolSnapshot]:
        rows = generate_mock_market()
        self.last_source = "mock_fallback" if fallback else "mock"
        if fallback and not self.last_error:
            self.last_error = "live sources unavailable"
        self._cache = rows
        self._persist_cache(rows)
        return rows

    async def _from_brsapi(self) -> list[SymbolSnapshot]:
        s = self.settings
        if not s.brsapi_key:
            self.last_error = "brsapi: no API key configured"
            logger.debug(self.last_error)
            return []
        url = f"{s.brsapi_base}/AllSymbols.php"
        params = {"key": s.brsapi_key, "type": "1"}
        # P1-4: Retry 2 times
        payload = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=s.request_timeout, headers=_headers()) as client:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    payload = resp.json()
                    break
            except Exception as exc:
                if attempt == 1:
                    self.last_error = f"brsapi: {exc} (after 2 attempts)"
                    logger.warning(self.last_error)
                    return []
                logger.debug(f"brsapi attempt {attempt+1} failed: {exc}, retrying...")
                await asyncio.sleep(1 + attempt)

        raw_list: list[dict]
        if isinstance(payload, list):
            raw_list = payload
        elif isinstance(payload, dict):
            raw_list = (
                payload.get("data")
                or payload.get("symbols")
                or payload.get("result")
                or []
            )
            if not raw_list and all(isinstance(v, dict) for v in payload.values()):
                raw_list = list(payload.values())
        else:
            raw_list = []

        rows: list[SymbolSnapshot] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            try:
                snap = brsapi_row_to_snapshot(item)
                if snap.l18 and snap.pl > 0:
                    rows.append(snap)
            except Exception:
                continue

        if rows:
            self.last_source = "brsapi"
            self.last_error = ""
            self._cache = rows
            self._persist_cache(rows)
        else:
            self.last_error = "brsapi: empty payload"
        return rows

    async def _from_tsetmc(self) -> list[SymbolSnapshot]:
        s = self.settings
        urls = [
            f"{s.tsetmc_cdn}/api/ClosingPrice/GetMarketWatch",
            "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch",
            "https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0",
        ]
        params_list = [
            {
                "market": "0",
                "industrialGroup": "",
                "paperTypes[0]": "1",
                "paperTypes[1]": "2",
                "paperTypes[2]": "8",
                "showTraded": "false",
                "withBestLimits": "true",
                "hEven": "0",
                "RefID": "0",
            },
            None,
            None,
        ]

        async with httpx.AsyncClient(timeout=s.request_timeout, headers=_headers(), follow_redirects=True) as client:
            for url, params in zip(urls, params_list):
                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code != 200:
                        continue
                    ctype = resp.headers.get("content-type", "")
                    text = resp.text
                    if "json" in ctype or text.strip().startswith("{") or text.strip().startswith("["):
                        payload = resp.json()
                        rows = self._parse_tsetmc_json(payload)
                        if rows:
                            self.last_source = "tsetmc"
                            self.last_error = ""
                            self._cache = rows
                            self._persist_cache(rows)
                            return rows
                    rows = self._parse_tsetmc_legacy(text)
                    if rows:
                        self.last_source = "tsetmc_legacy"
                        self.last_error = ""
                        self._cache = rows
                        self._persist_cache(rows)
                        return rows
                except Exception as exc:
                    self.last_error = f"tsetmc: {exc}"
                    logger.debug(self.last_error)
                    continue
        return []

    def _parse_tsetmc_json(self, payload: Any) -> list[SymbolSnapshot]:
        items: list[dict] = []
        if isinstance(payload, list):
            items = [x for x in payload if isinstance(x, dict)]
        elif isinstance(payload, dict):
            for key in ("marketwatch", "marketWatch", "instrumentList", "data", "bline", "rows"):
                val = payload.get(key)
                if isinstance(val, list):
                    items = [x for x in val if isinstance(x, dict)]
                    break
            if not items and "instrumentState" in payload:
                mw = payload.get("marketwatch") or payload.get("closingPriceList") or []
                if isinstance(mw, list):
                    items = [x for x in mw if isinstance(x, dict)]

        rows: list[SymbolSnapshot] = []
        for it in items:
            snap = tsetmc_mw_to_snapshot(it)
            if snap and snap.l18:
                rows.append(snap)
        return rows

    def _parse_tsetmc_legacy(self, text: str) -> list[SymbolSnapshot]:
        if not text or len(text) < 50:
            return []
        rows: list[SymbolSnapshot] = []
        parts = text.split("@")
        body = parts[1] if len(parts) > 1 else parts[0]
        for line in body.split(";"):
            cols = line.split(",")
            if len(cols) < 10:
                continue
            try:
                ins = cols[0]
                l18 = cols[2] if len(cols) > 2 else cols[1]
                l30 = cols[3] if len(cols) > 3 else l18
                pl = _safe_float(cols[7] if len(cols) > 7 else 0)
                pc = _safe_float(cols[6] if len(cols) > 6 else pl)
                py = _safe_float(cols[5] if len(cols) > 5 else pc)
                tvol = _safe_float(cols[9] if len(cols) > 9 else 0)
                if not l18 or pl <= 0:
                    continue
                plp = round((pl - py) / py * 100, 2) if py else 0
                rows.append(
                    SymbolSnapshot(
                        l18=l18.strip(),
                        l30=l30.strip(),
                        id=str(ins),
                        pl=pl,
                        pc=pc,
                        py=py,
                        plp=plp,
                        tvol=tvol,
                        avg_vol_30d=0.0,
                        source="tsetmc_legacy",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            except Exception:
                continue
        return rows

    def _persist_cache(self, rows: list[SymbolSnapshot]) -> None:
        path: Path = self.settings.cache_path
        try:
            payload = {
                "source": self.last_source,
                "as_of": datetime.now(timezone.utc).isoformat(),
                "count": len(rows),
                "symbols": [r.model_dump(mode="json") for r in rows],
            }
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.debug(f"cache write failed: {exc}")

    def load_cache(self) -> list[SymbolSnapshot]:
        path = self.settings.cache_path
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = [SymbolSnapshot.model_validate(x) for x in payload.get("symbols", [])]
            self.last_source = payload.get("source", "cache")
            return rows
        except Exception:
            return []
