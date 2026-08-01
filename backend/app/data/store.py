"""ذخیره‌سازی SQLite: اسنپ‌شات‌ها، تحرکات، هشدارها، پورتفو، تنظیمات."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import DATA_DIR

DB_PATH = DATA_DIR / "shekar.db"

_lock = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with _lock:
            conn = sqlite3.connect(str(self.path), timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # --- مهاجرت اسکیما (PRAGMA user_version) ---
    def _run_migrations(self, c) -> None:
        """مهاجرت‌های ترتیبی اسکیما؛ هر نسخه فقط یک‌بار اجرا می‌شود."""
        current = c.execute("PRAGMA user_version").fetchone()[0]
        migrations: list[tuple[int, str]] = [
            (1, "ALTER TABLE symbol_ticks ADD COLUMN flow_score REAL DEFAULT 0"),
        ]
        for version, sql in migrations:
            if current < version:
                try:
                    c.execute(sql)
                except Exception:
                    pass  # ستون از قبل موجود است (دیتابیس جدید)
                c.execute(f"PRAGMA user_version = {version}")

    def backup(self, keep: int = 7) -> Path | None:
        """بکاپ WAL-consistent از دیتابیس به پوشه data/backups — فقط N نسخه آخر."""
        import shutil
        try:
            bak_dir = self.path.parent / "backups"
            bak_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            target = bak_dir / f"shekar-{stamp}.db"
            with self._conn() as c:
                c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            # کپی امن با قفل باز
            with _lock:
                shutil.copy2(str(self.path), str(target))
            # پاک‌سازی نسخه‌های قدیمی
            baks = sorted(bak_dir.glob("shekar-*.db"))
            for old in baks[:-keep]:
                try:
                    old.unlink()
                except Exception:
                    pass
            return target
        except Exception as exc:
            logger = __import__("logging").getLogger("shekar.store")
            logger.warning(f"backup failed: {exc}")
            return None

    def _init_db(self) -> None:
        with self._conn() as c:
            self._run_migrations(c)
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    ts_iso TEXT NOT NULL,
                    source TEXT,
                    symbol_count INTEGER,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots(ts);

                CREATE TABLE IF NOT EXISTS symbol_ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    symbol TEXT NOT NULL,
                    pl REAL, plp REAL, pc REAL, pcp REAL,
                    tvol REAL, tval REAL, tno INTEGER,
                    buy_i_vol REAL, sell_i_vol REAL,
                    buy_count_i INTEGER, sell_count_i INTEGER,
                    buy_n_vol REAL, sell_n_vol REAL,
                    buy_per_capita REAL, sell_per_capita REAL,
                    buy_power REAL,
                    individual_net_value REAL,
                    hot_net REAL,
                    entry_score REAL, exit_score REAL,
                    qd1 REAL, qo1 REAL, pd1 REAL, po1 REAL
                );
                CREATE INDEX IF NOT EXISTS idx_ticks_sym_ts ON symbol_ticks(symbol, ts);
                CREATE INDEX IF NOT EXISTS idx_ticks_ts ON symbol_ticks(ts);

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    ts_iso TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    score REAL,
                    plp REAL,
                    reasons_json TEXT,
                    tags_json TEXT,
                    payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);
                CREATE INDEX IF NOT EXISTS idx_alerts_sym ON alerts(symbol);

                CREATE TABLE IF NOT EXISTS portfolio (
                    symbol TEXT PRIMARY KEY,
                    note TEXT DEFAULT '',
                    added_at TEXT NOT NULL,
                    alert_entry INTEGER DEFAULT 1,
                    alert_exit INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS settings_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS big_moves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    ts_iso TEXT NOT NULL,
                    window_sec INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    industry TEXT,
                    side TEXT,
                    delta_net_value REAL,
                    delta_volume REAL,
                    delta_plp REAL,
                    delta_buy_power REAL,
                    delta_hot_net REAL,
                    score REAL,
                    note TEXT,
                    payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_bm_ts ON big_moves(ts);
                CREATE INDEX IF NOT EXISTS idx_bm_sym ON big_moves(symbol);

                CREATE TABLE IF NOT EXISTS saved_filters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    expr TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notify_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    ts_iso TEXT NOT NULL,
                    channel TEXT,
                    ok INTEGER,
                    payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_notify_ts ON notify_log(ts);

                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    ts_iso TEXT NOT NULL,
                    params_json TEXT,
                    result_json TEXT
                );
                """
            )

    # ---------- settings ----------
    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._conn() as c:
            row = c.execute("SELECT value FROM settings_kv WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def set_setting(self, key: str, value: Any) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO settings_kv(key, value, updated_at) VALUES(?,?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), _utc_now()),
            )

    def get_all_settings(self) -> dict[str, Any]:
        with self._conn() as c:
            rows = c.execute("SELECT key, value FROM settings_kv").fetchall()
        out: dict[str, Any] = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except json.JSONDecodeError:
                out[r["key"]] = r["value"]
        return out

    # ---------- snapshots & ticks ----------
    def save_market_snapshot(
        self,
        source: str,
        symbols_compact: list[dict[str, Any]],
        ticks: list[dict[str, Any]],
        ts: float | None = None,
    ) -> int:
        ts = ts if ts is not None else time.time()
        ts_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO snapshots(ts, ts_iso, source, symbol_count, payload_json)
                VALUES (?,?,?,?,?)
                """,
                (
                    ts,
                    ts_iso,
                    source,
                    len(symbols_compact),
                    json.dumps(symbols_compact, ensure_ascii=False),
                ),
            )
            snap_id = int(cur.lastrowid)
            c.executemany(
                """
                INSERT INTO symbol_ticks(
                    ts, symbol, pl, plp, pc, pcp, tvol, tval, tno,
                    buy_i_vol, sell_i_vol, buy_count_i, sell_count_i,
                    buy_n_vol, sell_n_vol, buy_per_capita, sell_per_capita,
                    buy_power, individual_net_value, hot_net,
                    entry_score, exit_score, qd1, qo1, pd1, po1
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        ts,
                        t["symbol"],
                        t.get("pl"),
                        t.get("plp"),
                        t.get("pc"),
                        t.get("pcp"),
                        t.get("tvol"),
                        t.get("tval"),
                        t.get("tno"),
                        t.get("buy_i_vol"),
                        t.get("sell_i_vol"),
                        t.get("buy_count_i"),
                        t.get("sell_count_i"),
                        t.get("buy_n_vol"),
                        t.get("sell_n_vol"),
                        t.get("buy_per_capita"),
                        t.get("sell_per_capita"),
                        t.get("buy_power"),
                        t.get("individual_net_value"),
                        t.get("hot_net"),
                        t.get("entry_score"),
                        t.get("exit_score"),
                        t.get("qd1"),
                        t.get("qo1"),
                        t.get("pd1"),
                        t.get("po1"),
                    )
                    for t in ticks
                ],
            )
        return snap_id

    def get_ticks_since(self, since_ts: float, symbol: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as c:
            if symbol:
                rows = c.execute(
                    "SELECT * FROM symbol_ticks WHERE ts>=? AND symbol=? ORDER BY ts ASC",
                    (since_ts, symbol),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM symbol_ticks WHERE ts>=? ORDER BY ts ASC",
                    (since_ts,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_ticks_near(self, target_ts: float, tolerance: float = 90.0) -> dict[str, dict[str, Any]]:
        """نزدیک‌ترین تیک هر نماد به target_ts."""
        lo = target_ts - tolerance
        hi = target_ts + tolerance
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT * FROM symbol_ticks
                WHERE ts BETWEEN ? AND ?
                ORDER BY symbol ASC, ABS(ts - ?) ASC
                """,
                (lo, hi, target_ts),
            ).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            sym = r["symbol"]
            if sym not in out:
                out[sym] = dict(r)
        return out

    def prune_old(self, keep_hours: float = 36.0) -> None:
        cutoff = time.time() - keep_hours * 3600
        with self._conn() as c:
            c.execute("DELETE FROM symbol_ticks WHERE ts < ?", (cutoff,))
            c.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))
            c.execute("DELETE FROM big_moves WHERE ts < ?", (cutoff,))
            alert_cut = time.time() - 7 * 24 * 3600
            c.execute("DELETE FROM alerts WHERE ts < ?", (alert_cut,))

    def snapshot_stats(self) -> dict[str, Any]:
        with self._conn() as c:
            n_snap = c.execute("SELECT COUNT(*) AS n FROM snapshots").fetchone()["n"]
            n_ticks = c.execute("SELECT COUNT(*) AS n FROM symbol_ticks").fetchone()["n"]
            n_alerts = c.execute("SELECT COUNT(*) AS n FROM alerts").fetchone()["n"]
            n_bm = c.execute("SELECT COUNT(*) AS n FROM big_moves").fetchone()["n"]
            min_ts = c.execute("SELECT MIN(ts) AS m FROM symbol_ticks").fetchone()["m"]
            max_ts = c.execute("SELECT MAX(ts) AS m FROM symbol_ticks").fetchone()["m"]
        return {
            "snapshots": n_snap,
            "ticks": n_ticks,
            "alerts": n_alerts,
            "big_moves": n_bm,
            "tick_min_ts": min_ts,
            "tick_max_ts": max_ts,
        }

    # ---------- alerts ----------
    def save_alerts(self, alerts: list[dict[str, Any]]) -> int:
        if not alerts:
            return 0
        ts = time.time()
        ts_iso = _utc_now()
        with self._conn() as c:
            c.executemany(
                """
                INSERT INTO alerts(ts, ts_iso, symbol, side, score, plp, reasons_json, tags_json, payload_json)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        ts,
                        ts_iso,
                        a["symbol"],
                        a["side"],
                        a.get("score"),
                        a.get("plp"),
                        json.dumps(a.get("reasons") or [], ensure_ascii=False),
                        json.dumps(a.get("tags") or [], ensure_ascii=False),
                        json.dumps(a.get("payload") or a, ensure_ascii=False),
                    )
                    for a in alerts
                ],
            )
        return len(alerts)

    def list_alerts(
        self,
        side: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = "SELECT * FROM alerts WHERE 1=1"
        params: list[Any] = []
        if side:
            q += " AND side=?"
            params.append(side)
        if symbol:
            q += " AND symbol=?"
            params.append(symbol)
        q += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["reasons"] = json.loads(d.pop("reasons_json") or "[]")
            d["tags"] = json.loads(d.pop("tags_json") or "[]")
            try:
                d["payload"] = json.loads(d.pop("payload_json") or "{}")
            except json.JSONDecodeError:
                d["payload"] = {}
            out.append(d)
        return out

    # ---------- portfolio ----------
    def portfolio_list(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM portfolio ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]

    def portfolio_add(self, symbol: str, note: str = "") -> dict[str, Any]:
        sym = symbol.strip()
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO portfolio(symbol, note, added_at) VALUES(?,?,?)
                ON CONFLICT(symbol) DO UPDATE SET note=excluded.note
                """,
                (sym, note, _utc_now()),
            )
            row = c.execute("SELECT * FROM portfolio WHERE symbol=?", (sym,)).fetchone()
        return dict(row)

    def portfolio_remove(self, symbol: str) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM portfolio WHERE symbol=?", (symbol.strip(),))
            return cur.rowcount > 0

    def portfolio_set_alerts(self, symbol: str, alert_entry: bool, alert_exit: bool) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE portfolio SET alert_entry=?, alert_exit=? WHERE symbol=?",
                (1 if alert_entry else 0, 1 if alert_exit else 0, symbol.strip()),
            )

    # ---------- big moves ----------
    def save_big_moves(self, moves: list[dict[str, Any]], window_sec: int) -> int:
        if not moves:
            return 0
        ts = time.time()
        ts_iso = _utc_now()
        with self._conn() as c:
            c.execute(
                "DELETE FROM big_moves WHERE ts > ? AND window_sec=?",
                (ts - 60, window_sec),
            )
            c.executemany(
                """
                INSERT INTO big_moves(
                    ts, ts_iso, window_sec, symbol, name, industry, side,
                    delta_net_value, delta_volume, delta_plp, delta_buy_power,
                    delta_hot_net, score, note, payload_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        ts,
                        ts_iso,
                        window_sec,
                        m["symbol"],
                        m.get("name"),
                        m.get("industry"),
                        m.get("side"),
                        m.get("delta_net_value"),
                        m.get("delta_volume"),
                        m.get("delta_plp"),
                        m.get("delta_buy_power"),
                        m.get("delta_hot_net"),
                        m.get("score"),
                        m.get("note"),
                        json.dumps(m, ensure_ascii=False),
                    )
                    for m in moves
                ],
            )
        return len(moves)

    def list_big_moves(
        self,
        window_sec: int | None = None,
        limit: int = 100,
        since_ts: float | None = None,
    ) -> list[dict[str, Any]]:
        q = "SELECT * FROM big_moves WHERE 1=1"
        params: list[Any] = []
        if window_sec is not None:
            q += " AND window_sec=?"
            params.append(window_sec)
        if since_ts is not None:
            q += " AND ts>=?"
            params.append(since_ts)
        q += " ORDER BY score DESC, ts DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d.pop("payload_json") or "{}")
            except json.JSONDecodeError:
                d["payload"] = {}
            out.append(d)
        return out

    # ---------- saved filters ----------
    def filters_list(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, name, expr, created_at, updated_at FROM saved_filters ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def filter_save(self, name: str, expr: str, filter_id: int | None = None) -> dict[str, Any]:
        now = _utc_now()
        with self._conn() as c:
            if filter_id:
                c.execute(
                    "UPDATE saved_filters SET name=?, expr=?, updated_at=? WHERE id=?",
                    (name, expr, now, filter_id),
                )
                rid = filter_id
            else:
                cur = c.execute(
                    "INSERT INTO saved_filters(name, expr, created_at, updated_at) VALUES(?,?,?,?)",
                    (name, expr, now, now),
                )
                rid = int(cur.lastrowid)
            row = c.execute(
                "SELECT id, name, expr, created_at, updated_at FROM saved_filters WHERE id=?",
                (rid,),
            ).fetchone()
        return dict(row)

    def filter_delete(self, filter_id: int) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM saved_filters WHERE id=?", (filter_id,))
            return cur.rowcount > 0

    # ---------- notify log ----------
    def save_notify_log(self, payload: dict[str, Any]) -> None:
        import time as _t

        ts = _t.time()
        with self._conn() as c:
            c.execute(
                "INSERT INTO notify_log(ts, ts_iso, channel, ok, payload_json) VALUES(?,?,?,?,?)",
                (
                    ts,
                    _utc_now(),
                    str(payload.get("channel") or ""),
                    1 if payload.get("ok", True) else 0,
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )

    def list_notify_log(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM notify_log ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d.pop("payload_json") or "{}")
            except json.JSONDecodeError:
                d["payload"] = {}
            out.append(d)
        return out

    def save_backtest_run(self, params: dict[str, Any], result: dict[str, Any]) -> int:
        import time as _t

        ts = _t.time()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO backtest_runs(ts, ts_iso, params_json, result_json) VALUES(?,?,?,?)",
                (
                    ts,
                    _utc_now(),
                    json.dumps(params, ensure_ascii=False, default=str),
                    json.dumps(result, ensure_ascii=False, default=str),
                ),
            )
            return int(cur.lastrowid)

    def list_backtest_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, ts, ts_iso, params_json, result_json FROM backtest_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = {"id": r["id"], "ts": r["ts"], "ts_iso": r["ts_iso"]}
            try:
                d["params"] = json.loads(r["params_json"] or "{}")
                d["result_summary"] = {
                    k: json.loads(r["result_json"] or "{}").get(k)
                    for k in (
                        "mode",
                        "trades",
                        "win_rate",
                        "avg_return",
                        "max_drawdown",
                        "profit_factor",
                    )
                }
            except json.JSONDecodeError:
                d["params"] = {}
                d["result_summary"] = {}
            out.append(d)
        return out


store = Store()
