"""WS-10 CI-cycle evidence-stream hygiene (2026-11-02).

W7 ("Runtime log posture") fail-closes on the literal "Traceback" anywhere in
the uvicorn runtime log. Handled faults on the recurring 30s poll path are
logged NON-FATAL events (error text + err_id + uptime metrics), not crashes —
they must not print full multi-line tracebacks into the evidence stream.
Real unhandled ASGI crashes are still tracebacked by uvicorn itself, so the
gate's crash-detection power is unchanged by this contract.

Pinned here:
1. Mechanism reproduction: a faulted Phase-2 analysis still propagates
   fail-loud (raise preserved) AND leaves no "Traceback" and no exc_info in
   the captured log — only the single-line error with err_id. (Note: the
   sites call plain logger.error(...) with NO exc_info argument — stdlib
   logging never attaches exception info implicitly, so every record on the
   evidence stream carries exc_info=None and no traceback text.)
2. Poll-loop fault path: a failing refresh cycle is logged and swallowed
   (loop keeps running) with the same no-traceback contract.
3. Source guard: `app/services/market_service.py` (the boot/poll evidence
   stream) contains no `logger.exception` sites — regression guard.
"""
import asyncio
import logging
from pathlib import Path

import pytest

import app.data.mock_market as mm
import app.services.market_service as msm


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _market_service_source() -> str:
    return (
        Path(__file__).resolve().parents[1] / "app" / "services" / "market_service.py"
    ).read_text(encoding="utf-8")


def test_poll_path_has_no_traceback_logging_sites():
    src = _market_service_source()
    assert "logger.exception" not in src, (
        "evidence-stream hygiene regression: market_service must log handled "
        "faults via plain logger.error(...) without exception info, never "
        "logger.exception"
    )


def test_phase2_fault_propagates_fail_loud_without_traceback_in_log():
    service = msm.market_service
    capture = _Capture()
    msm.logger.addHandler(capture)
    original_analyze = msm.analyze_market
    original_fetch = service.provider.fetch

    async def fake_fetch():
        return mm.generate_mock_market(12)

    def boom(*args, **kwargs):
        raise ValueError("repro-handled-phase2-fault")

    async def scenario():
        service.provider.fetch = fake_fetch  # type: ignore[method-assign]
        msm.analyze_market = boom  # type: ignore[assignment]
        try:
            with pytest.raises(ValueError):
                await service.refresh(force=True)
        finally:
            msm.analyze_market = original_analyze  # type: ignore[assignment]
            service.provider.fetch = original_fetch  # type: ignore[method-assign]

    try:
        asyncio.run(scenario())
    finally:
        msm.logger.removeHandler(capture)

    texts = [r.getMessage() for r in capture.records]
    joined = "\n".join(texts)
    assert any("analyze_market failed" in t for t in texts), texts
    assert any("repro-handled-phase2-fault" in t for t in texts), texts
    assert "Traceback" not in joined, texts
    assert all(r.exc_info is None for r in capture.records)
    # err_id correlation preserved: every fault line keeps the [hash] prefix
    assert any(t.startswith("[") and "]" in t for t in texts if "analyze_market failed" in t)


def test_poll_loop_swallows_refresh_fault_without_traceback():
    service = msm.market_service
    capture = _Capture()
    msm.logger.addHandler(capture)
    original_refresh = msm.MarketService.refresh

    async def boom(self, force=False):
        raise RuntimeError("repro-poll-fault")

    async def scenario():
        msm.MarketService.refresh = boom  # type: ignore[assignment]
        task = asyncio.create_task(service._poll_loop())
        try:
            # sleep: the loop sleeps first (>=10s) then refreshes; shrink the
            # wait by patching asyncio.sleep inside the loop's module namespace
            real_sleep = msm.asyncio.sleep

            async def fast_sleep(_seconds):
                await real_sleep(0.01)

            msm.asyncio.sleep = fast_sleep  # type: ignore[assignment]
            await real_sleep(0.2)  # let at least one fault cycle complete
        finally:
            task.cancel()
            msm.asyncio.sleep = real_sleep  # type: ignore[assignment]
            msm.MarketService.refresh = original_refresh  # type: ignore[assignment]
            try:
                await task
            except asyncio.CancelledError:
                pass

    try:
        asyncio.run(scenario())
    finally:
        msm.logger.removeHandler(capture)

    texts = [r.getMessage() for r in capture.records]
    joined = "\n".join(texts)
    assert any("poll error" in t and "repro-poll-fault" in t for t in texts), texts
    assert "Traceback" not in joined, texts
    assert all(r.exc_info is None for r in capture.records)
