"""سرویس بازار — v0.6.0 - Production Hardened - Meta Standard
P1-1 Fix: کاهش lock contention - heavy I/O و CPU خارج از lock
P1-2 Fix: کش fundamental با LRU و TTL
P0-1/P0-2: Trust level و flow coverage بهبود یافته
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

from app.core.config import build_data_trust_context, get_settings, resolve_trust_level
from app.core.runtime_settings import get_effective_settings
from app.data.providers import MarketDataProvider
from app.data.store import store
from app.engines.backtest import backtest_from_market
from app.engines.big_moves import compute_big_moves, ensure_flow_history, flow_coverage_sec
from app.engines.confluence import build_confluence_board, pick_notify_alerts
from app.engines.filter_dsl import FilterError, fields_help, run_filter, validate_filter
from app.engines.fundamental import (
    build_deep_fundamental,
)
from app.engines.market_map import build_market_map
from app.engines.metrics import compute_metrics
from app.engines.options import build_chain_for_symbol, price_custom, recommend_strategies
from app.engines.screener import analyze_market
from app.engines.tablocastic import compute_tablocastic, rank_tablocastic
from app.engines.trade_detail import (
    build_intraday_series,
    build_ohlcv_from_ticks,
    get_trade_hot_money,
)
from app.domain.market_session import infer_iran_market_session
from app.models.schemas import AnalyzeResponse, SignalSide, SymbolSnapshot
from app.services.notifier import notifier
from app.services.ws_hub import ws_hub

logger = logging.getLogger("shekar.service")


class MarketService:
    def __init__(self) -> None:
        self.provider = MarketDataProvider()
        self.settings = get_settings()
        self._lock = asyncio.Lock()
        self._last_analysis: Optional[AnalyzeResponse] = None
        self._last_symbols: list[SymbolSnapshot] = []
        self._last_fetch_ts: float = 0.0
        self._last_big_moves: list[dict[str, Any]] = []
        self._last_tablocastic: list[dict[str, Any]] = []
        self._last_confluence: dict[str, Any] = {}
        self._row_cache: list[dict[str, Any]] = []
        self._bg_task: Optional[asyncio.Task] = None
        self._seen_alert_keys: set[str] = set()
        self._trust_level: str = "mixed"
        self._source: str = "none"
        self._flow_meta: dict[str, Any] = {}
        # WS-1 false-fresh guard: a refresh cycle that fell back to recycled
        # symbols after a provider.fetch() exception must NOT re-stamp them
        # as freshly fetched (one-cycle flag; see refresh()).
        self._fetch_degraded: bool = False
        # P1-2: کش fundamental با LRU + TTL + size limit
        self._fund_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._fund_cache_max = 200
        self._last_prune_ts = 0.0
        self._prune_interval = 3600  # 1 hour - P1-3 fix

    def cfg(self):
        return get_effective_settings()

    def trust_level(self) -> str:
        return self._trust_level

    def data_trust_context(self) -> dict[str, Any]:
        """Canonical Data Trust context for market-intelligence outputs."""
        source = self._source or self.provider.last_source or "unknown"
        fallback_source = "mock" if "mock" in (source or "").lower() else ""
        return build_data_trust_context(
            source,
            timestamp=self._last_fetch_ts or None,
            provider=self.provider.last_source or self._source or "unknown",
            fallback_source=fallback_source,
            error_code=self.provider.last_error or "",
            stale_after_sec=getattr(get_settings(), "data_stale_after_sec", 300),
        )

    @staticmethod
    def _mark_synthetic_fundamental(payload: dict[str, Any]) -> dict[str, Any]:
        """Current fundamental engine generates synthetic statements."""
        payload.setdefault("fundamental_source", "synthetic")
        payload.setdefault("is_synthetic", True)
        payload.setdefault("warning", "Fundamental statements are synthetic/demo data, not verified Codal financial statements.")
        return payload

    async def start_background(self) -> None:
        if self._bg_task and not self._bg_task.done():
            return
        self._bg_task = asyncio.create_task(self._poll_loop())

    async def stop_background(self) -> None:
        if self._bg_task:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        while True:
            cfg = self.cfg()
            await asyncio.sleep(max(10, int(getattr(cfg, "poll_seconds", 30) or 30)))
            try:
                await self.refresh(force=True)
            except Exception as exc:
                err_id = uuid.uuid4().hex[:8]
                logger.exception(f"[{err_id}] poll error: {exc}")

    def _build_tick(self, s: SymbolSnapshot) -> dict[str, Any]:
        cfg = self.cfg()
        m = compute_metrics(s, cfg)
        return {
            "symbol": s.l18,
            "pl": s.pl,
            "plp": s.plp,
            "pc": s.pc,
            "pcp": s.pcp,
            "tvol": s.tvol,
            "tval": s.tval,
            "tno": s.tno,
            "buy_i_vol": s.Buy_I_Volume,
            "sell_i_vol": s.Sell_I_Volume,
            "buy_count_i": s.Buy_CountI,
            "sell_count_i": s.Sell_CountI,
            "buy_n_vol": s.Buy_N_Volume,
            "sell_n_vol": s.Sell_N_Volume,
            "buy_per_capita": m.buy_per_capita,
            "sell_per_capita": m.sell_per_capita,
            "buy_power": m.buy_power,
            "individual_net_value": m.individual_net_value,
            "hot_net": m.hot_net,
            "entry_score": m.entry_score,
            "exit_score": m.exit_score,
            "qd1": s.qd1,
            "qo1": s.qo1,
            "pd1": s.pd1,
            "po1": s.po1,
        }

    def _get_fund_cached(self, s: SymbolSnapshot) -> Any:
        """P1-2: LRU cache with TTL and size limit"""
        ttl = int(getattr(get_settings(), "fundamental_cache_ttl_sec", 300) or 300)
        now = time.time()
        hit = self._fund_cache.get(s.l18)
        if hit and now - hit[0] < ttl:
            class _F:
                def __init__(self, d):
                    self._d = d
                    for k, v in d.items():
                        if k != "deep":
                            setattr(self, k, v)
                def to_dict(self):
                    return self._d
            return _F(hit[1])
        
        d = build_deep_fundamental(s, self.cfg())
        
        # LRU eviction if over limit
        if len(self._fund_cache) >= self._fund_cache_max:
            # remove oldest 20%
            sorted_items = sorted(self._fund_cache.items(), key=lambda x: x[1][0])
            for k, _ in sorted_items[: self._fund_cache_max // 5]:
                self._fund_cache.pop(k, None)
        
        self._fund_cache[s.l18] = (now, d)

        class _F2:
            def __init__(self, dd):
                self._d = dd
                for k, v in dd.items():
                    if k != "deep":
                        setattr(self, k, v)
            def to_dict(self):
                return self._d
        return _F2(d)

    def _build_filter_row(self, s: SymbolSnapshot) -> dict[str, Any]:
        cfg = self.cfg()
        m = compute_metrics(s, cfg)
        tc = compute_tablocastic(s, cfg)
        fund = self._get_fund_cached(s)
        side = m.side.value if isinstance(m.side, SignalSide) else str(m.side)
        return {
            "symbol": s.l18,
            "name": s.l30,
            "industry": s.cs,
            "pl": s.pl,
            "plp": s.plp,
            "pc": s.pc,
            "pcp": s.pcp,
            "tvol": s.tvol,
            "tval": s.tval,
            "tno": s.tno,
            "pe": s.pe,
            "eps": s.eps,
            "mv": s.mv,
            "bvol": s.bvol,
            "py": s.py,
            "tmax": s.tmax,
            "tmin": s.tmin,
            "qd1": s.qd1,
            "qo1": s.qo1,
            "pd1": s.pd1,
            "po1": s.po1,
            "Buy_I_Volume": s.Buy_I_Volume,
            "Sell_I_Volume": s.Sell_I_Volume,
            "Buy_N_Volume": s.Buy_N_Volume,
            "Sell_N_Volume": s.Sell_N_Volume,
            "Buy_CountI": s.Buy_CountI,
            "Sell_CountI": s.Sell_CountI,
            "buy_power": m.buy_power,
            "buy_per_capita": m.buy_per_capita,
            "sell_per_capita": m.sell_per_capita,
            "volume_ratio": m.volume_ratio,
            "value_ratio": m.value_ratio,
            "individual_net_value": m.individual_net_value,
            "individual_net_volume": m.individual_net_volume,
            "legal_to_individual": m.legal_to_individual,
            "hot_net": m.hot_net,
            "hot_buy_score": m.hot_buy_score,
            "hot_sell_score": m.hot_sell_score,
            "entry_score": m.entry_score,
            "exit_score": m.exit_score,
            "watch_score": m.watch_score,
            "big_player_bias": m.big_player_bias,
            "mid_player_bias": m.mid_player_bias,
            "retail_bias": m.retail_bias,
            "pe_score": m.pe_score,
            "dist_to_ceiling_pct": m.dist_to_ceiling_pct,
            "dist_to_floor_pct": m.dist_to_floor_pct,
            "is_volume_spike": m.is_volume_spike,
            "is_strong_volume_spike": m.is_strong_volume_spike,
            "near_buy_queue": m.near_buy_queue or m.in_buy_queue,
            "near_sell_queue": m.near_sell_queue or m.in_sell_queue,
            "in_buy_queue": m.in_buy_queue,
            "in_sell_queue": m.in_sell_queue,
            "fundamental_ok": m.fundamental_ok,
            "d_plus": tc.d_plus,
            "m_plus": tc.m_plus,
            "m_over_d": tc.m_over_d,
            "golden_number": tc.golden_number,
            "quality_score": tc.quality_score,
            "queue_power": tc.queue_power,
            "demand_pressure": tc.demand_pressure,
            "supply_pressure": tc.supply_pressure,
            "smart_flow": tc.smart_flow,
            "hour_pattern": tc.hour_pattern,
            "grade": tc.grade,
            "side": side,
            "fund_score": getattr(fund, "fund_score", 0),
            "roe": getattr(fund, "roe", 0),
            "roa": getattr(fund, "roa", 0),
            "profit_growth": getattr(fund, "profit_growth", 0),
            "revenue_growth": getattr(fund, "revenue_growth", 0),
            "debt_ratio": getattr(fund, "debt_ratio", 0),
            "tags": m.tags,
            "reasons": m.reasons,
            "fund_grade": getattr(fund, "grade", ""),
            "value_score": getattr(fund, "value_score", getattr(fund, "fund_score", 0)),
        }

    def _rebuild_row_cache(self, symbols: list[SymbolSnapshot]) -> list[dict[str, Any]]:
        return [self._build_filter_row(s) for s in symbols]

    def _persist_snapshot(self, symbols: list[SymbolSnapshot], analysis: AnalyzeResponse) -> None:
        compact = [
            {"l18": s.l18, "pl": s.pl, "plp": s.plp, "tvol": s.tvol, "tval": s.tval, "pe": s.pe}
            for s in symbols
        ]
        ticks = [self._build_tick(s) for s in symbols]
        store.save_market_snapshot(analysis.overview.source, compact, ticks)

        bucket = int(time.time() // 900)
        alerts: list[dict[str, Any]] = []
        for card in analysis.entry_signals[:30]:
            key = f"entry:{card.symbol}:{bucket}"
            if key in self._seen_alert_keys:
                continue
            self._seen_alert_keys.add(key)
            alerts.append(
                {
                    "symbol": card.symbol,
                    "side": "entry",
                    "score": card.entry_score,
                    "plp": card.plp,
                    "reasons": card.reasons,
                    "tags": card.tags,
                    "payload": card.model_dump(mode="json"),
                }
            )
        for card in analysis.exit_signals[:30]:
            key = f"exit:{card.symbol}:{bucket}"
            if key in self._seen_alert_keys:
                continue
            self._seen_alert_keys.add(key)
            alerts.append(
                {
                    "symbol": card.symbol,
                    "side": "exit",
                    "score": card.exit_score,
                    "plp": card.plp,
                    "reasons": card.reasons,
                    "tags": card.tags,
                    "payload": card.model_dump(mode="json"),
                }
            )
        if alerts:
            store.save_alerts(alerts)
        if len(self._seen_alert_keys) > 5000:
            self._seen_alert_keys = set(list(self._seen_alert_keys)[-2000:])
        # P1-3 Fix: prune only hourly, not every refresh
        try:
            now = time.time()
            if now - self._last_prune_ts > self._prune_interval:
                store.prune_old(self.cfg().history_keep_hours)
                self._last_prune_ts = now
                logger.info(f"pruned old data - keep_hours={self.cfg().history_keep_hours}")
        except Exception as exc:
            logger.debug(f"prune failed: {exc} - err_id={uuid.uuid4().hex[:6]}")

    def _update_big_moves(self, symbols: list[SymbolSnapshot], source: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        cfg = self.cfg()
        base = get_settings()
        window = int(getattr(cfg, "big_move_window_sec", 600) or 600)
        min_score = float(getattr(cfg, "big_move_min_score", 25) or 25)
        allow_bs = bool(getattr(base, "allow_history_bootstrap", True)) and resolve_trust_level(source, base) != "live"
        flow_meta = ensure_flow_history(
            store,
            symbols,
            self._build_tick,
            window_sec=window,
            allow_bootstrap=allow_bs,
            source_hint=source if "mock" in source else ("mock" if allow_bs else source),
        )
        moves = compute_big_moves(store, symbols, window_sec=window, cfg=cfg, min_score=min_score)
        try:
            store.save_big_moves(moves[:100], window_sec=window)
        except Exception as exc:
            logger.warning(f"save_big_moves failed: {exc}")
        return moves, flow_meta

    async def refresh(self, force: bool = False) -> AnalyzeResponse:
        """
        P1-1 Fix: Lock only for short critical sections
        - Phase 0: Quick check should-we-refresh under lock
        - Phase 1: Network fetch OUTSIDE lock
        - Phase 2: Heavy CPU OUTSIDE lock
        - Phase 3: Quick state update under lock
        - Phase 4: I/O outside lock
        """
        # Phase 0: fast check
        async with self._lock:
            now = time.time()
            cfg = self.cfg()
            poll = int(getattr(cfg, "poll_seconds", 30) or 30)
            if not force and self._last_analysis and now - self._last_fetch_ts < poll:
                return self._last_analysis

        # Phase 1: Network I/O OUTSIDE lock (biggest win)
        self.provider.settings = get_settings()
        # Q-1 hardening (MASTER-WAVE 2026-11-02): the degraded marker is a
        # PER-CYCLE local token, not the shared instance attribute. Two
        # concurrent refresh cycles each carry their own outcome, so a fresh
        # cycle completing inside this cycle's Phase-1→Phase-3 span can never
        # clobber this cycle's degraded state (reproduction:
        # tests/test_refresh_degraded_token_concurrency.py). The attribute
        # below is retained only as an observability mirror with identical
        # sequential semantics.
        cycle_degraded = False
        cycle_source: str = "unknown"  # per-cycle capture (W2-DATA F-2)
        try:
            symbols = await self.provider.fetch()
            # F-2 hardening: capture the cycle's source label SYNCHRONOUSLY,
            # before the lock acquisition below can suspend this task — a
            # concurrent cycle's fetch completing during that suspension can
            # overwrite the SHARED provider.last_source, so the old post-lock
            # read could commit another cycle's label (incl. an upward
            # mislabel). The per-cycle local is immutable for the rest of the
            # cycle; sequential (single-cycle) value is byte-identical.
            cycle_source = self.provider.last_source
            async with self._lock:
                self._fetch_degraded = False  # fresh fetch succeeded (mirror)
        except Exception as exc:
            err_id = uuid.uuid4().hex[:8]
            logger.error(f"[{err_id}] provider fetch failed: {exc}", exc_info=False)
            # Degraded path: capture the shared label SYNCHRONOUSLY at the
            # top of the except — exception propagation runs without yielding,
            # so this read cannot interleave with another cycle's fetch. The
            # lock acquisition below CAN suspend, so the capture must precede
            # it (same reasoning as the success path above).
            cycle_source = self.provider.last_source
            # Fallback to last known symbols if available
            async with self._lock:
                if self._last_symbols:
                    symbols = self._last_symbols
                    # P2 data-trust honesty (WS-1 audit finding): recycled
                    # data from a failed fetch must not be re-stamped as
                    # fresh in Phase 3 — flag the cycle as degraded so the
                    # previous fetch timestamp is preserved and the trust
                    # context reports the true age (stale/unavailable).
                    cycle_degraded = True  # per-cycle token (Q-1 hardening)
                    self._fetch_degraded = True  # observability mirror
                else:
                    raise
        source = cycle_source  # per-cycle label — immune to cross-cycle overwrite
        # Legacy source classification only. Display/WS/notify must use
        # data_trust_context() which never mints verified LIVE from a label.
        trust_level = resolve_trust_level(source, get_settings())

        # Phase 2: Heavy CPU OUTSIDE lock
        try:
            analysis = analyze_market(
                symbols, cfg=self.cfg(), source=source, include_all_metrics=False
            )
        except Exception as exc:
            err_id = uuid.uuid4().hex[:8]
            logger.exception(f"[{err_id}] analyze_market failed: {exc}")
            raise

        # Phase 2b: big moves + flow + tablocastic + row_cache + confluence OUTSIDE lock
        try:
            moves, flow_meta = self._update_big_moves(symbols, source)
        except Exception as exc:
            err_id = uuid.uuid4().hex[:8]
            logger.exception(f"[{err_id}] big_moves failed: {exc}")
            moves, flow_meta = [], {"coverage_sec": 0, "sufficient": False}

        try:
            tablocastic = rank_tablocastic(symbols, cfg=self.cfg(), limit=100)
        except Exception as exc:
            logger.warning(f"tablocastic failed: {exc}")
            tablocastic = []

        try:
            row_cache = self._rebuild_row_cache(symbols)
        except Exception as exc:
            logger.warning(f"row_cache failed: {exc}")
            row_cache = []

        # confluence needs moves + symbols
        try:
            # Build confluence board using fresh data
            from app.engines.confluence import build_confluence_board
            window = int(getattr(self.cfg(), "big_move_window_sec", 600) or 600)
            ncfg = store.get_setting("notifier", {}) or {}
            board = build_confluence_board(
                symbols,
                moves,
                cfg=self.cfg(),
                min_value_score=float(ncfg.get("min_value_score", 55)),
                min_combo_buy=float(ncfg.get("min_combo_buy", 70)),
                min_combo_sell=float(ncfg.get("min_combo_sell", 65)),
                flow_window_sec=window,
                limit=80,
            )
            board["trust_level"] = trust_level
            board["source"] = source
            board["flow_meta"] = {
                **(flow_meta or {}),
                "coverage_sec": flow_coverage_sec(store),
            }
            cov = float((board["flow_meta"] or {}).get("coverage_sec") or 0)
            min_cov = float(getattr(get_settings(), "flow_min_coverage_sec", 120) or 120)
            if cov < min_cov:
                for r in board.get("buy_alerts") or []:
                    r["alert"] = False
                    r["action"] = "watch_buy"
                    r.setdefault("reasons", []).insert(0, f"پوشش جریان ناکافی ({int(cov)}s < {int(min_cov)}s)")
                board["buy_alerts"] = []
                board["watchlist"] = (board.get("watchlist") or []) + [
                    r for r in (board.get("board") or []) if r.get("action") == "watch_buy"
                ]
                if board.get("summary"):
                    board["summary"]["buy_alerts"] = 0
                    board["summary"]["flow_insufficient"] = True
        except Exception as exc:
            err_id = uuid.uuid4().hex[:8]
            logger.exception(f"[{err_id}] confluence build failed: {exc}")
            board = {}

        # Phase 3: Quick state update UNDER lock
        async with self._lock:
            self._last_symbols = symbols
            self._last_analysis = analysis
            if cycle_degraded:  # per-cycle token — immune to cross-cycle clobber
                # False-fresh guard: keep the PREVIOUS fetch timestamp so the
                # trust context reflects the real data age instead of masking
                # the failure with a fresh stamp. One-cycle flag.
                self._last_fetch_ts = self._last_fetch_ts or time.time()
                self._fetch_degraded = False  # consume the mirror
            else:
                self._last_fetch_ts = time.time()
            self._source = source
            self._trust_level = trust_level
            self._last_big_moves = moves
            self._flow_meta = flow_meta
            self._last_tablocastic = tablocastic
            self._row_cache = row_cache
            self._last_confluence = board

            # Snapshot persist (store has own lock, but do under our lock to keep consistency)
            try:
                self._persist_snapshot(symbols, analysis)
            except Exception as exc:
                err_id = uuid.uuid4().hex[:8]
                logger.exception(f"[{err_id}] persist failed: {exc}")

            analysis_ref = analysis
            conf_ref = dict(board or {})
            trust_ctx = self.data_trust_context()
            trust_ref = trust_ctx.get("trust_level") or "mixed"
            # Persist the canonical (never-verified-from-label) level for API/WS consumers.
            self._trust_level = trust_ref
            if board:
                board["trust_level"] = trust_ref
                board["data_trust"] = trust_ctx
                self._last_confluence = board
                conf_ref = dict(board)

        # Phase 4: Broadcast + Notifier OUTSIDE lock
        try:
            await self._broadcast_live(analysis_ref, conf_ref, trust_ref)
        except Exception as exc:
            logger.debug(f"ws broadcast failed: {exc}")

        try:
            pf = {p["symbol"] for p in store.portfolio_list()}
            ncfg = notifier.get_public_config()
            combo = pick_notify_alerts(
                conf_ref,
                min_combo_buy=float(ncfg.get("min_combo_buy") or 70),
                min_combo_sell=float(ncfg.get("min_combo_sell") or 65),
            )
            n = await notifier.process_alerts(
                analysis_ref.entry_signals[:20],
                analysis_ref.exit_signals[:20],
                portfolio_symbols=pf,
                confluence_alerts=combo,
                trust_level=trust_ref,
                data_trust=self.data_trust_context(),
            )
            if n:
                logger.info(f"notifier sent {n} alerts (combo={len(combo)} trust={trust_ref})")
        except Exception as exc:
            err_id = uuid.uuid4().hex[:8]
            logger.debug(f"[{err_id}] notifier failed: {exc}")

        logger.info(
            f"refreshed {len(symbols)} via {source} trust={trust_level} | entry={analysis_ref.overview.entry_alerts} exit={analysis_ref.overview.exit_alerts} | moves={len(moves)} | flow_cov={flow_meta.get('coverage_sec')} | combo_buy={(conf_ref.get('summary') or {}).get('buy_alerts', 0)} | ws={ws_hub.count}"
        )
        return analysis_ref

    def _build_confluence(self, cfg=None) -> dict[str, Any]:
        cfg = cfg or self.cfg()
        window = int(getattr(cfg, "big_move_window_sec", 600) or 600)
        ncfg = store.get_setting("notifier", {}) or {}
        board = build_confluence_board(
            self._last_symbols,
            self._last_big_moves,
            cfg=cfg,
            min_value_score=float(ncfg.get("min_value_score", 55)),
            min_combo_buy=float(ncfg.get("min_combo_buy", 70)),
            min_combo_sell=float(ncfg.get("min_combo_sell", 65)),
            flow_window_sec=window,
            limit=80,
        )
        trust_ctx = self.data_trust_context()
        board["trust_level"] = trust_ctx.get("trust_level") or "mixed"
        board["data_trust"] = trust_ctx
        board["source"] = self._source
        board["flow_meta"] = {
            **(self._flow_meta or {}),
            "coverage_sec": flow_coverage_sec(store),
        }
        cov = float((board["flow_meta"] or {}).get("coverage_sec") or 0)
        min_cov = float(getattr(get_settings(), "flow_min_coverage_sec", 120) or 120)
        if cov < min_cov:
            for r in board.get("buy_alerts") or []:
                r["alert"] = False
                r["action"] = "watch_buy"
                r.setdefault("reasons", []).insert(0, f"پوشش جریان ناکافی ({int(cov)}s < {int(min_cov)}s)")
            board["buy_alerts"] = []
            board["watchlist"] = (board.get("watchlist") or []) + [
                r for r in (board.get("board") or []) if r.get("action") == "watch_buy"
            ]
            if board.get("summary"):
                board["summary"]["buy_alerts"] = 0
                board["summary"]["flow_insufficient"] = True
        return board

    async def _broadcast_live(
        self,
        analysis: AnalyzeResponse,
        conf: Optional[dict[str, Any]] = None,
        trust: Optional[str] = None,
    ) -> None:
        if not get_settings().ws_broadcast_on_refresh:
            return
        if ws_hub.count <= 0:
            return
        conf = conf if conf is not None else self._last_confluence
        payload = {
            "type": "market_update",
            "source": analysis.overview.source,
            "trust_level": trust or self._trust_level,
            "data_trust": self.data_trust_context(),
            "overview": {
                "symbol_count": analysis.overview.symbol_count,
                "positive_count": analysis.overview.positive_count,
                "negative_count": analysis.overview.negative_count,
                "entry_alerts": analysis.overview.entry_alerts,
                "exit_alerts": analysis.overview.exit_alerts,
                "volume_spikes": analysis.overview.volume_spikes,
                "hot_money_count": analysis.overview.hot_money_count,
                "total_value": analysis.overview.total_value,
                "as_of": analysis.overview.as_of.isoformat()
                if hasattr(analysis.overview.as_of, "isoformat")
                else str(analysis.overview.as_of),
            },
            "entry_signals": [c.model_dump(mode="json") for c in analysis.entry_signals[:15]],
            "exit_signals": [c.model_dump(mode="json") for c in analysis.exit_signals[:15]],
            "big_moves": self._last_big_moves[:10],
            "confluence": {
                "summary": (conf or {}).get("summary"),
                "buy_alerts": (conf or {}).get("buy_alerts", [])[:10],
                "sell_alerts": (conf or {}).get("sell_alerts", [])[:10],
                "flow_meta": (conf or {}).get("flow_meta"),
                "trust_level": trust or self._trust_level,
            },
        }
        await ws_hub.broadcast(payload)

    async def get_analysis(self, force: bool = False) -> AnalyzeResponse:
        if force or not self._last_analysis:
            return await self.refresh(force=True)
        return self._last_analysis

    def get_snapshot(self, l18: str) -> Optional[SymbolSnapshot]:
        target = (l18 or "").strip()
        for s in self._last_symbols:
            if s.l18 == target:
                return s
        return None

    def get_symbol(self, l18: str) -> Optional[dict[str, Any]]:
        cfg = self.cfg()
        s = self.get_snapshot(l18)
        if not s:
            return None
        m = compute_metrics(s, cfg)
        tc = compute_tablocastic(s, cfg)
        fund = self._get_fund_cached(s)
        since = time.time() - 6 * 3600
        hist = store.get_ticks_since(since, symbol=s.l18)
        ohlcv = build_ohlcv_from_ticks(hist, s)
        intraday = build_intraday_series(hist, s)
        fundamental_payload = self._mark_synthetic_fundamental(fund.to_dict())
        return {
            "snapshot": s.model_dump(mode="json"),
            "metrics": m.model_dump(mode="json"),
            "tablocastic": tc.to_dict(),
            "fundamental": fundamental_payload,
            "history": hist[-120:],
            "ohlcv": ohlcv,
            "intraday": intraday,
            "trust_level": self._trust_level,
            "source": self._source,
            "data_trust": self.data_trust_context(),
            "instrument": {
                "symbol": s.l18,
                "name": s.l30,
                "isin": s.isin,
                "instrument_id": s.id,
                "industry": s.cs,
                "industry_id": s.cs_id,
                "market": "TSE",
            },
            "orderbook": {
                "bids": [
                    {"price": s.pd1, "volume": s.qd1, "count": s.zd1},
                    {"price": s.pd2, "volume": s.qd2, "count": s.zd2},
                    {"price": s.pd3, "volume": s.qd3, "count": s.zd3},
                    {"price": s.pd4, "volume": s.qd4, "count": s.zd4},
                    {"price": s.pd5, "volume": s.qd5, "count": s.zd5},
                ],
                "asks": [
                    {"price": s.po1, "volume": s.qo1, "count": s.zo1},
                    {"price": s.po2, "volume": s.qo2, "count": s.zo2},
                    {"price": s.po3, "volume": s.qo3, "count": s.zo3},
                    {"price": s.po4, "volume": s.qo4, "count": s.zo4},
                    {"price": s.po5, "volume": s.qo5, "count": s.zo5},
                ],
            },
            "chart": {
                "tv_symbol": f"TSETMC:{s.l18}",
                "title": f"{s.l18} — {s.l30}",
                "currency": "IRR",
            },
            "in_portfolio": any(p["symbol"] == s.l18 for p in store.portfolio_list()),
        }

    def get_big_moves(self, window_sec: int | None = None, limit: int = 80) -> list[dict[str, Any]]:
        cfg = self.cfg()
        w = window_sec or int(getattr(cfg, "big_move_window_sec", 600) or 600)
        if self._last_big_moves and (window_sec is None or window_sec == w):
            return self._last_big_moves[:limit]
        rows = store.list_big_moves(window_sec=w, limit=limit, since_ts=time.time() - 3600)
        if rows:
            return rows
        if self._last_symbols:
            return compute_big_moves(store, self._last_symbols, window_sec=w, cfg=cfg)[:limit]
        return []

    def get_tablocastic(self, limit: int = 80, min_quality: float = 0) -> list[dict[str, Any]]:
        rows = self._last_tablocastic or rank_tablocastic(self._last_symbols, cfg=self.cfg(), limit=200)
        return [r for r in rows if r.get("quality_score", 0) >= min_quality][:limit]

    def portfolio_enriched(self) -> list[dict[str, Any]]:
        cfg = self.cfg()
        items = store.portfolio_list()
        snap_map = {s.l18: s for s in self._last_symbols}
        out = []
        for p in items:
            sym = p["symbol"]
            s = snap_map.get(sym)
            row: dict[str, Any] = {**p}
            if s:
                m = compute_metrics(s, cfg)
                tc = compute_tablocastic(s, cfg)
                fund = self._get_fund_cached(s)
                row.update(
                    {
                        "name": s.l30,
                        "industry": s.cs,
                        "pl": s.pl,
                        "plp": s.plp,
                        "pe": s.pe,
                        "entry_score": round(m.entry_score, 1),
                        "exit_score": round(m.exit_score, 1),
                        "buy_power": round(m.buy_power, 2),
                        "volume_ratio": round(m.volume_ratio, 2),
                        "hot_net": round(m.hot_net, 1),
                        "side": m.side.value if isinstance(m.side, SignalSide) else m.side,
                        "golden_number": tc.golden_number,
                        "d_plus": tc.d_plus,
                        "m_plus": tc.m_plus,
                        "grade": tc.grade,
                        "fund_score": getattr(fund, "fund_score", None),
                        "value_score": getattr(fund, "value_score", None),
                        "fund_grade": getattr(fund, "grade", None),
                        "tags": m.tags,
                        "reasons": m.reasons,
                    }
                )
            else:
                row.update({"name": "", "pl": None, "plp": None, "entry_score": None})
            out.append(row)
        out.sort(key=lambda r: (r.get("exit_score") or 0, r.get("entry_score") or 0), reverse=True)
        return out

    def get_market_map(self, size_by: str = "tval", color_by: str = "plp", min_tval: float = 0) -> dict[str, Any]:
        return build_market_map(self._last_symbols, cfg=self.cfg(), size_by=size_by, color_by=color_by, min_tval=min_tval)

    def get_fundamentals(self, limit: int = 80, min_score: float = 0) -> list[dict[str, Any]]:
        from app.engines.fundamental import rank_fundamentals
        return rank_fundamentals(self._last_symbols, cfg=self.cfg(), limit=limit, min_score=min_score)

    def get_value_stocks(
        self,
        limit: int = 50,
        max_pe: float = 18.0,
        min_value_score: float = 55.0,
    ) -> list[dict[str, Any]]:
        from app.engines.fundamental import rank_value_stocks
        return rank_value_stocks(
            self._last_symbols,
            cfg=self.cfg(),
            limit=limit,
            max_pe=max_pe,
            min_value_score=min_value_score,
        )

    def get_deep_fundamental(self, l18: str) -> Optional[dict[str, Any]]:
        s = self.get_snapshot(l18)
        if not s:
            return None
        d = self._mark_synthetic_fundamental(self._get_fund_cached(s).to_dict())
        d["trust_level"] = self._trust_level
        d["data_trust"] = self.data_trust_context()
        return d

    def run_user_filter(self, expr: str, limit: int = 100) -> dict[str, Any]:
        if not self._row_cache and self._last_symbols:
            try:
                self._row_cache = self._rebuild_row_cache(self._last_symbols)
            except Exception as exc:
                logger.warning(f"row cache rebuild failed: {exc}")
        try:
            validation = validate_filter(expr)
            matched = run_filter(expr, self._row_cache)
        except FilterError as exc:
            return {"ok": False, "error": str(exc), "count": 0, "rows": [], "fields": fields_help()}
        matched = sorted(matched, key=lambda r: r.get("entry_score") or 0, reverse=True)
        slim = []
        for r in matched[:limit]:
            slim.append(
                {
                    "symbol": r.get("symbol"),
                    "name": r.get("name"),
                    "industry": r.get("industry"),
                    "pl": r.get("pl"),
                    "plp": r.get("plp"),
                    "pe": r.get("pe"),
                    "buy_power": round(float(r.get("buy_power") or 0), 2),
                    "volume_ratio": round(float(r.get("volume_ratio") or 0), 2),
                    "entry_score": round(float(r.get("entry_score") or 0), 1),
                    "exit_score": round(float(r.get("exit_score") or 0), 1),
                    "hot_net": round(float(r.get("hot_net") or 0), 1),
                    "individual_net_value": r.get("individual_net_value"),
                    "golden_number": r.get("golden_number"),
                    "quality_score": r.get("quality_score"),
                    "fund_score": r.get("fund_score"),
                    "value_score": r.get("value_score"),
                    "grade": r.get("grade"),
                    "side": r.get("side"),
                    "tags": r.get("tags") or [],
                    "reasons": r.get("reasons") or [],
                }
            )
        return {
            "ok": True,
            "error": None,
            "count": len(matched),
            "rows": slim,
            "expr": expr,
            "normalized_expr": validation.get("normalized"),
            "used_fields": validation.get("fields") or [],
            "used_functions": validation.get("functions") or [],
            "fields": fields_help(),
            "trust_level": self._trust_level,
            "data_trust": self.data_trust_context(),
        }

    async def get_trade_hot(self, l18: str) -> Optional[dict[str, Any]]:
        s = self.get_snapshot(l18)
        if not s:
            return None
        data = await get_trade_hot_money(s, self.cfg())
        data["trust_level"] = self._trust_level
        data["data_trust"] = self.data_trust_context()
        return data

    def search_symbols(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        query = (q or "").strip()
        if not query:
            return []
        out = []
        for s in self._last_symbols:
            if query in s.l18 or query in (s.l30 or ""):
                out.append({"symbol": s.l18, "name": s.l30, "industry": s.cs, "plp": s.plp, "pl": s.pl})
            if len(out) >= limit:
                break
        return out

    def run_backtest(self, **params: Any) -> dict[str, Any]:
        result = backtest_from_market(
            self._last_symbols,
            store,
            cfg=self.cfg(),
            **params,
        )
        result["trust_level"] = self._trust_level
        result["data_trust"] = self.data_trust_context()
        result["demo_disclaimer"] = "بک‌تست روی تاریخچه محدود/مصنوعی است و عملکرد آینده را تضمین نمی‌کند. این یک ابزار آموزشی است، نه تضمین سود."
        result["educational"] = True
        result["warning"] = "⚠️ توجه: این بک‌تست صف خرید/فروش و کارمزد واقعی بورس ایران را شبیه‌سازی نمی‌کند."
        try:
            store.save_backtest_run(result.get("params") or params, result)
        except Exception:
            pass
        return result

    def get_options_chain(self, l18: str) -> Optional[dict[str, Any]]:
        s = self.get_snapshot(l18)
        if not s:
            return None
        chain = build_chain_for_symbol(s)
        m = compute_metrics(s, self.cfg())
        chain["strategies"] = recommend_strategies(
            s,
            entry_score=m.entry_score,
            exit_score=m.exit_score,
            vol=float(chain.get("vol") or 0.35),
        )
        chain["entry_score"] = m.entry_score
        chain["exit_score"] = m.exit_score
        chain["trust_level"] = self._trust_level
        chain["data_trust"] = self.data_trust_context()
        chain["educational"] = True
        chain["risk_warning"] = "⚠️ اختیار معامله ریسک بالایی دارد. این ماشین‌حساب آموزشی است و قیمت بازار واقعی اختیار بورس تهران را نشان نمی‌دهد."
        return chain

    def options_price(self, **kwargs: Any) -> dict[str, Any]:
        out = price_custom(**kwargs)
        out["educational"] = True
        out["risk_warning"] = "قیمت تئوریک است. بازار واقعی اختیار دارای وجه تضمین و ریسک کال مارجین است."
        return out

    def get_confluence(self, force_rebuild: bool = False) -> dict[str, Any]:
        if force_rebuild or not self._last_confluence:
            try:
                self._last_confluence = self._build_confluence()
            except Exception as exc:
                err_id = uuid.uuid4().hex[:8]
                logger.exception(f"[{err_id}] confluence rebuild: {exc}")
                return {
                    "summary": {},
                    "board": [],
                    "buy_alerts": [],
                    "sell_alerts": [],
                    "error": str(exc),
                    "error_id": err_id,
                    "trust_level": self._trust_level,
                    "data_trust": self.data_trust_context(),
                }
        return self._last_confluence

    def status(self) -> dict[str, Any]:
        cfg = self.cfg()
        conf_sum = (self._last_confluence or {}).get("summary") or {}
        return {
            "source": self._source or self.provider.last_source,
            "trust_level": self._trust_level,
            "data_trust": self.data_trust_context(),
            "last_error": self.provider.last_error,
            "symbol_count": len(self._last_symbols),
            "last_fetch_ts": self._last_fetch_ts,
            "has_analysis": self._last_analysis is not None,
            "data_source_config": get_settings().data_source,
            "poll_seconds": getattr(cfg, "poll_seconds", 30),
            "version": get_settings().version,
            "store": store.snapshot_stats(),
            "flow_meta": {
                **(self._flow_meta or {}),
                "coverage_sec": flow_coverage_sec(store),
            },
            "big_moves_count": len(self._last_big_moves),
            "tablocastic_count": len(self._last_tablocastic),
            "portfolio_count": len(store.portfolio_list()),
            "confluence": conf_sum,
            "ws": ws_hub.status(),
            "notifier": notifier.get_public_config(),
            "auth_required": get_settings().auth_required,
            "market_session": infer_iran_market_session().model_dump(mode="json"),
            "phase": 9,
            "security": {
                "rate_limit": get_settings().rate_limit_enabled,
                "auth_required": get_settings().auth_required,
                "cors": get_settings().cors_origins[:50] + "..." if len(get_settings().cors_origins) > 50 else get_settings().cors_origins,
                "crypto_available": False,  # will be checked elsewhere
            }
        }


market_service = MarketService()
