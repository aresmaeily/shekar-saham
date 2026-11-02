"""T7 P5/P6 integration audit — delivery-surface gaps.

The governed P5/P6 lifecycle (D-AI-30) delivers through the IN-PRODUCT
INBOX only. Two legacy delivery surfaces exist in the runtime but had ZERO
test coverage before this audit:

1. ``app/services/ws_hub.py`` — the WebSocket ConnectionManager (connected
   producer: ``market_service._broadcast_live`` / ``main.ws_live``; it has
   NO governed-alert edge). Covers connect/hello, broadcast fan-out,
   dead-client pruning, disconnect and status counters.
2. ``app/services/notifier.py::send_text`` — the Telegram/Bale credential-
   gated delivery seam (OWNER-GATED: needs stored token + chat id). The
   existing hardening tests only cover the *blocking* paths of
   ``process_alerts``; the actual transport seam was never exercised.
   Fake transports are injected — no network, no credentials.

Plus a structural no-edge proof: no P5/P6 module references notifier/ws_hub
(delivery channel is closed in the type system to IN_PRODUCT_INBOX).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.services.notifier import Notifier
from app.services.ws_hub import ConnectionManager


# --- ws_hub (zero prior coverage) ---------------------------------------------


class _FakeWS:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[str] = []
        self.accepted = False
        self._fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        if self._fail:
            raise RuntimeError("client gone (synthetic)")
        self.sent.append(text)


def test_ws_hub_connect_accepts_sends_hello_and_tracks() -> None:
    async def run() -> None:
        hub = ConnectionManager()
        ws = _FakeWS()
        await hub.connect(ws)
        assert ws.accepted is True
        assert hub.count == 1
        hello = json.loads(ws.sent[0])
        assert hello["type"] == "hello"
        assert hello["clients"] == 1
        assert hub.total_connections == 1

    asyncio.run(run())


def test_ws_hub_broadcast_fanout_and_status_counters() -> None:
    async def run() -> None:
        hub = ConnectionManager()
        a, b = _FakeWS(), _FakeWS()
        await hub.connect(a)
        await hub.connect(b)
        sent = await hub.broadcast({"type": "market_update", "symbol": "فولاد"})
        assert sent == 2
        assert json.loads(a.sent[-1])["type"] == "market_update"
        assert json.loads(b.sent[-1])["symbol"] == "فولاد"
        st = hub.status()
        assert st["clients"] == 2 and st["messages_sent"] == 4  # 2 hello + 2 broadcast
        assert st["last_broadcast_ts"] > 0

    asyncio.run(run())


def test_ws_hub_broadcast_prunes_dead_clients() -> None:
    async def run() -> None:
        hub = ConnectionManager()
        alive, dead = _FakeWS(), _FakeWS(fail=True)
        await hub.connect(alive)
        await hub.connect(dead)
        sent = await hub.broadcast({"type": "market_update"})
        assert sent == 1  # only the live client
        assert hub.count == 1  # dead client pruned
        st = hub.status()
        assert st["clients"] == 1 and st["total_connections"] == 2

    asyncio.run(run())


def test_ws_hub_disconnect_removes_client() -> None:
    async def run() -> None:
        hub = ConnectionManager()
        ws = _FakeWS()
        await hub.connect(ws)
        await hub.disconnect(ws)
        assert hub.count == 0
        sent = await hub.broadcast({"type": "market_update"})
        assert sent == 0

    asyncio.run(run())


# --- notifier delivery seam (OWNER-GATED; fake transports, no network) --------


class _FakeStore:
    """In-memory stand-in for app.data.store (never touches the runtime DB)."""

    def __init__(self, settings: dict | None = None) -> None:
        self._settings = settings or {}
        self.notify_logs: list[dict] = []
        self.saved_alerts: list[list[dict]] = []

    def get_setting(self, key: str, default: object = None) -> object:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: object) -> None:
        self._settings[key] = value

    def save_notify_log(self, entry: dict) -> None:
        self.notify_logs.append(entry)

    def save_alerts(self, alerts: list[dict]) -> None:
        self.saved_alerts.append(alerts)


def _recording_transport(results: list[bool]):
    calls: list[tuple[str, str, str]] = []

    async def transport(token: str, chat_id: str, text: str) -> bool:
        calls.append((token, chat_id, text))
        return results[len(calls) - 1] if len(calls) <= len(results) else False

    return transport, calls


def test_notifier_send_text_delivers_via_owner_configured_channels(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.notifier as notifier_mod

    fake_store = _FakeStore(
        {
            "notifier": {
                "enabled": True,
                "telegram_token": "tok-telegram",
                "telegram_chat_id": "chat-telegram",
                "bale_token": "tok-bale",
                "bale_chat_id": "chat-bale",
            }
        }
    )
    monkeypatch.setattr(notifier_mod, "store", fake_store)
    n = Notifier()
    tg, tg_calls = _recording_transport([True])
    bale, bale_calls = _recording_transport([True])
    monkeypatch.setattr(n, "_post_telegram", tg)
    monkeypatch.setattr(n, "_post_bale", bale)

    result = asyncio.run(n.send_text("هشدار آزمایشی"))

    assert tg_calls == [("tok-telegram", "chat-telegram", "هشدار آزمایشی")]
    assert bale_calls == [("tok-bale", "chat-bale", "هشدار آزمایشی")]
    assert result == {"telegram": True, "bale": True}
    assert n.sent_count == 2
    # delivery is logged (channel "multi" since both channels fired)
    assert fake_store.notify_logs and fake_store.notify_logs[-1]["channel"] == "multi"


def test_notifier_send_text_owner_gated_partial_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only Telegram configured → Bale transport never called, per-channel
    credential gating honored (missing token/chat ⇒ no Bale egress)."""
    import app.services.notifier as notifier_mod

    fake_store = _FakeStore(
        {
            "notifier": {
                "enabled": True,
                "telegram_token": "tok-telegram",
                "telegram_chat_id": "chat-telegram",
            }
        }
    )
    monkeypatch.setattr(notifier_mod, "store", fake_store)
    n = Notifier()
    tg, tg_calls = _recording_transport([True])
    bale, bale_calls = _recording_transport([])
    monkeypatch.setattr(n, "_post_telegram", tg)
    monkeypatch.setattr(n, "_post_bale", bale)

    result = asyncio.run(n.send_text("partial", channels=["telegram", "bale"]))

    assert len(tg_calls) == 1
    assert bale_calls == []  # credential-gated: no Bale config ⇒ no call
    assert result == {"telegram": True, "bale": None}
    assert n.sent_count == 1


def test_notifier_send_text_without_credentials_is_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """No tokens configured ⇒ zero transport calls, dry-run result, and the
    no-channel log is emitted at most once per 5 minutes (anti-spam)."""
    import app.services.notifier as notifier_mod

    fake_store = _FakeStore({"notifier": {"enabled": True}})
    monkeypatch.setattr(notifier_mod, "store", fake_store)
    n = Notifier()
    tg, tg_calls = _recording_transport([])
    bale, bale_calls = _recording_transport([])
    monkeypatch.setattr(n, "_post_telegram", tg)
    monkeypatch.setattr(n, "_post_bale", bale)

    first = asyncio.run(n.send_text("dry 1"))
    second = asyncio.run(n.send_text("dry 2"))

    assert tg_calls == [] and bale_calls == []
    assert first["telegram"] is None and first["bale"] is None and first["dry_run"] is True
    assert second.get("dry_run") is True
    dry_logs = [e for e in fake_store.notify_logs if e.get("channel") == "dry-run"]
    assert len(dry_logs) == 1  # spam-suppressed second log within the window


def test_governed_alert_lifecycle_has_no_edge_to_legacy_delivery_surfaces() -> None:
    """Structural no-edge proof (P5/P6 audit): the governed alert lifecycle
    (contract + decisions + store + service + API) never IMPORTS the legacy
    notifier or ws_hub delivery surfaces (or any telegram/bale transport
    module) — the only delivery channel is the type-closed IN_PRODUCT_INBOX,
    so no governed alert can reach Telegram/Bale/WebSocket fan-out by
    construction. AST-based: docstring/comment mentions of the banned names
    (e.g. the closed-channel documentation) are not edges."""
    import ast

    import app.api.alert_ops
    import app.data.alert_ops_store
    import app.domain.alert_operations
    import app.domain.governed_alerts
    import app.services.alert_operations

    banned_roots = ("app.services.notifier", "app.services.ws_hub", "telegram", "bale")
    for mod in (
        app.domain.governed_alerts,
        app.domain.alert_operations,
        app.data.alert_ops_store,
        app.services.alert_operations,
        app.api.alert_ops,
    ):
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(banned_roots), (mod.__name__, alias.name)
            elif isinstance(node, ast.ImportFrom):
                root = node.module or ""
                assert not root.startswith(banned_roots), (mod.__name__, root)
