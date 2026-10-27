"""WS-HARDEN-1/W2 — request_id contextvar bridge regression tests.

Before this workstream the middleware wrote ONLY ``request.state.request_id``;
the logging filter rendered ``request_id=-`` on every line because nothing ever
set the attribute on log records and no contextvar existed. These tests pin the
bridge: middleware -> contextvar -> logging filter, plus isolation semantics.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.request_id import RequestIdMiddleware, get_current_request_id


def _tiny_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/echo")
    async def echo(request: Request):
        return {"state": request.state.request_id, "ctx": get_current_request_id()}

    return app


def test_generated_request_id_shape():
    client = TestClient(_tiny_app())
    res = client.get("/echo")
    rid = res.headers["X-Request-ID"]
    assert len(rid) == 12
    int(rid, 16)  # must be hex
    body = res.json()
    assert body["state"] == rid
    assert body["ctx"] == rid  # contextvar bridge visible inside the endpoint


def test_incoming_x_request_id_honored():
    client = TestClient(_tiny_app())
    res = client.get("/echo", headers={"X-Request-ID": "abcd1234ef56"})
    assert res.headers["X-Request-ID"] == "abcd1234ef56"
    assert res.json()["ctx"] == "abcd1234ef56"


def test_no_bleed_between_sequential_requests():
    client = TestClient(_tiny_app())
    first = client.get("/echo", headers={"X-Request-ID": "aaaaaaaaaaaa"}).json()["ctx"]
    second = client.get("/echo", headers={"X-Request-ID": "bbbbbbbbbbbb"}).json()["ctx"]
    assert first == "aaaaaaaaaaaa"
    assert second == "bbbbbbbbbbbb"  # token reset: no leakage from the first request


def test_contextvar_none_outside_request():
    assert get_current_request_id() is None


def test_log_filter_defaults_to_dash_outside_request():
    from app.main import RequestIdFilter

    record = logging.LogRecord("probe", logging.INFO, __file__, 1, "msg", None, None)
    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "-"


def test_real_app_unauthorized_response_bridges_request_id(monkeypatch):
    """401 short-circuits in an OUTER middleware: after WS-HARDEN-1/W2 the outermost
    RequestIdMiddleware still stamps the header, and the 401 body's request_id
    (read from request.state) is populated — both were broken before the reorder."""
    for key in ("PRIVATE_MODE", "PRIVATE_PASSWORD", "API_KEY", "AUTH_REQUIRED", "ENV", "APP_ENV", "SHEKAR_ENV", "FERNET_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PRIVATE_MODE", "1")
    monkeypatch.setenv("API_KEY", "correct-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    get_settings.cache_clear()
    client = TestClient(create_app())

    res = client.get("/api/config/thresholds", headers={"X-API-Key": "wrong-key"})
    assert res.status_code == 401
    rid = res.headers["X-Request-ID"]
    assert rid, "401 short-circuit must still carry X-Request-ID (outermost middleware)"
    assert res.json()["request_id"] == rid


def test_real_app_middleware_warning_log_carries_request_id(monkeypatch, caplog):
    """End-to-end bridge on the real app: the audit middleware warning emitted inside
    the request task must carry the same request_id as the X-Request-ID header."""
    for key in ("PRIVATE_MODE", "PRIVATE_PASSWORD", "API_KEY", "AUTH_REQUIRED", "ENV", "APP_ENV", "SHEKAR_ENV", "FERNET_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PRIVATE_MODE", "1")
    monkeypatch.setenv("API_KEY", "correct-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import RequestIdFilter, create_app

    get_settings.cache_clear()
    client = TestClient(create_app())

    caplog.set_level(logging.WARNING)
    caplog.handler.addFilter(RequestIdFilter())  # mirror the root-handler filter setup
    res = client.get("/api/health?api_key=leak-attempt")
    assert res.status_code == 200
    rid = res.headers["X-Request-ID"]

    warns = [r for r in caplog.records if "API key in query param" in r.getMessage()]
    assert warns, "expected the query-param warning to be captured"
    assert all(getattr(r, "request_id", "-") == rid for r in warns)
