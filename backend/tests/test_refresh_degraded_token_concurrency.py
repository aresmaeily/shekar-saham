"""MASTER-WAVE Q-1 concurrency regression tests — per-cycle degraded token.

Owner directive (2026-11-02, MASTER EXECUTION DIRECTIVE §5 WS-C): "Prioritize
the reported LOW finding concerning per-cycle degraded tokens during
concurrent refresh. Reproduce the condition before changing code. Add
concurrency and regression tests."

Finding Q-1 (MA-1 WS-12, LOW): ``MarketService.refresh()`` stores the
degraded-cycle marker in ONE shared instance attribute
(``self._fetch_degraded``) instead of a per-cycle token. Two concurrent
refresh cycles therefore share one marker slot: if cycle B's Phase-1
fresh-fetch write (``_fetch_degraded = False``) lands between cycle A's
degraded write (``_fetch_degraded = True``) and cycle A's Phase-3 read, A's
degraded state is lost and A's RECYCLED data is re-stamped as fresh — the
exact false-fresh hazard the P2 trust guard was built to prevent.

Why the hazard is latent, not live, on the pre-fix code shape: between the
Phase-1 flag write and the Phase-3 flag read the refresh body contains no
``await`` (verified by line scan, MA-1/CONSOL-NEXT records), so on the single
event loop the span is cycle-atomic and no interleaving can start. The hazard
opens the moment ANY yield point appears in that span (a new await, lock
contention suspending the Phase-3 acquisition, ...).

REPRODUCTION STRATEGY (no production code touched by the harness):
The tests inject the yield point through the seam the service itself uses —
its asyncio.Lock. ``SeamLock`` delegates to a real ``asyncio.Lock`` but
``__aenter__`` first awaits ``asyncio.sleep(0)`` (a pure control yield, one
loop turn per acquisition) and can run a ONE-SHOT async hook on the first
acquisition after the test arms it. The hook drives cycle B (suspended on its
provider future) just far enough to execute its Phase-1 fresh-fetch flag
write, then returns — leaving cycle A to enter Phase 3 AFTER B's clobbering
write. This is exactly the interleaving Q-1 describes.

DECISIVE OBSERVABLE: cycle B never reaches its own Phase-3 in the repro, so
no fresh stamp masks cycle A's decision. The service's ``_broadcast_live``
is temporarily replaced by a spy that snapshots ``_last_fetch_ts`` on its
FIRST invocation — which is cycle A's Phase 4, immediately after A's Phase-3
branch chose between "preserve old timestamp" (degraded honored) and
"re-stamp now" (degraded LOST). Pre-fix the spy records a just-now stamp
(test FAILS = defect reproduced); post-fix it records the preserved old
timestamp (test PASSES = hazard closed by the per-cycle token).

Determinism: no network (provider stub with manually-resolved futures;
conftest pins DATA_SOURCE=mock), no wall-clock dependence beyond the injected
timestamps, loop ordering driven only by explicit future resolutions, the
one-yield-per-acquisition seam, and observable-state polling (provider call
log, mirrored attribute) — never by acquisition indices or sleeps > 0.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from app.models.schemas import SymbolSnapshot
from app.services.market_service import MarketService


def _snapshot(l18: str = "فولاد") -> SymbolSnapshot:
    return SymbolSnapshot(l18=l18, l30="فولاد مبارکه", isin="IRO1", pl=100.0, py=100.0)


class OrchestratedProvider:
    """Provider whose successive fetch() calls await manually-resolved futures.

    fetch call #1 awaits futures[0] (cycle A), call #2 awaits futures[1]
    (cycle B). The test decides each outcome and WHEN it is delivered.
    """

    def __init__(self, n: int = 0) -> None:
        self.settings = None
        self.last_source = "tsetmc"
        self.last_error = ""
        self._n = n
        self._futures: list[asyncio.Future] = []
        self.calls: list[asyncio.Future] = []

    def _ensure_futures(self) -> None:
        if not self._futures:
            loop = asyncio.get_running_loop()
            self._futures = [loop.create_future() for _ in range(self._n)]

    def resolve(self, index: int, outcome: Any) -> None:
        self._ensure_futures()
        fut = self._futures[index]
        assert not fut.done(), f"future #{index} already resolved"
        if isinstance(outcome, BaseException):
            fut.set_exception(outcome)
        else:
            fut.set_result(outcome)

    async def fetch(self):  # noqa: ANN201
        self._ensure_futures()
        fut = self._futures[len(self.calls)]
        self.calls.append(fut)
        return await fut


class SeamLock:
    """asyncio.Lock wrapper: one pure control-yield per acquisition plus an
    optional ONE-SHOT async hook fired at the first acquisition whose
    predicate (evaluated per acquisition) returns True. The hook models any
    future yield point inside refresh()'s Phase-1→Phase-3 span and may run
    other coroutines partway before the caller proceeds."""

    def __init__(self) -> None:
        self._inner = asyncio.Lock()
        self._armed: tuple[Callable[[], bool], Callable[[], Awaitable[None]]] | None = None

    def arm_hook(
        self, predicate: Callable[[], bool], hook: Callable[[], Awaitable[None]]
    ) -> None:
        assert self._armed is None, "hook already armed"
        self._armed = (predicate, hook)

    async def __aenter__(self) -> None:
        await asyncio.sleep(0)  # pure control yield — deterministic
        if self._armed is not None and self._armed[0]():
            _predicate, hook = self._armed
            self._armed = None  # one-shot
            await hook()
        await self._inner.acquire()

    async def __aexit__(self, *exc: Any) -> None:
        self._inner.release()


def _make_service(provider: OrchestratedProvider, lock: Any) -> MarketService:
    service = MarketService.__new__(MarketService)  # avoid real provider wiring
    service.provider = provider
    service.settings = None
    service._lock = lock
    service._last_analysis = None
    service._last_symbols = [_snapshot()]  # truthy board: degraded fallback engages
    service._last_fetch_ts = 0.0
    service._last_big_moves = []
    service._last_tablocastic = []
    service._last_confluence = {}
    service._row_cache = []
    service._seen_alert_keys = set()
    service._trust_level = "mixed"
    service._source = "none"
    service._flow_meta = {}
    service._fetch_degraded = False
    service._fund_cache = {}
    service._fund_cache_max = 200
    service._last_prune_ts = 0.0
    service._prune_interval = 3600
    return service


async def _wait_until(predicate: Callable[[], bool], what: str) -> None:
    for _ in range(10_000):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"orchestration deadlock: never observed {what}")


def test_interleaved_fresh_cycle_must_not_steal_degraded_cycle_marker() -> None:
    """THE Q-1 REPRODUCTION (correct-behavior form).

    Cycle A is degraded (recycled board, old timestamp). Cycle B's Phase-1
    fresh-fetch flag write lands INSIDE A's Phase-1→Phase-3 span; B then
    stalls before its own Phase 3. A's Phase 3 must still honor A's own
    degraded outcome and preserve the old timestamp. On the pre-fix shared-
    attribute code shape this FAILS: A reads B's False and re-stamps the
    recycled data as fresh. GREEN here proves the per-cycle token fix holds
    under the interleaving.
    """
    provider = OrchestratedProvider(2)
    lock = SeamLock()
    service = _make_service(provider, lock)
    old_ts = time.time() - 10_000.0  # recycled data is ~2.8h old
    service._last_fetch_ts = old_ts

    cells: dict[str, Any] = {"a_stamp": None, "task_a": None}

    async def broadcast_spy(*_args: Any) -> None:
        # Invoked at each cycle's Phase 4, right after that cycle's Phase-3
        # chose a branch. Snapshot ONLY cycle A's stamp (the degraded one).
        import asyncio as _aio

        if cells["task_a"] is not None and _aio.current_task() is cells["task_a"]:
            if cells["a_stamp"] is None:
                cells["a_stamp"] = service._last_fetch_ts

    service._broadcast_live = broadcast_spy  # type: ignore[method-assign]

    async def scenario() -> None:
        task_a = asyncio.create_task(service.refresh(force=True))
        cells["task_a"] = task_a
        await _wait_until(lambda: len(provider.calls) == 1, "cycle A fetch suspension")

        task_b = asyncio.create_task(service.refresh(force=True))
        await _wait_until(lambda: len(provider.calls) == 2, "cycle B fetch suspension")

        # A's fetch fails: A enters its except path. Advance until A has
        # written the degraded marker (the shared write under test).
        provider.resolve(0, RuntimeError("synthetic provider outage (cycle A)"))
        await _wait_until(lambda: service._fetch_degraded, "A degraded write")

        # THE SEAM: fire the one-shot hook at cycle A's Phase-3 acquisition —
        # uniquely identified by (task is A) AND (degraded marker already
        # written). The hook completes B's Phase-1 fresh-flag write first,
        # then returns without letting B reach its own Phase 3.
        async def clobber_then_return() -> None:
            provider.resolve(1, [])  # B: fresh fetch succeeds
            await _wait_until(lambda: not service._fetch_degraded, "B fresh write")
            # B is now past its Phase-1 write; its next lock use is its own
            # Phase 3, which must NOT run before A's read.

        lock.arm_hook(
            predicate=lambda: (
                asyncio.current_task() is task_a and service._fetch_degraded
            ),
            hook=clobber_then_return,
        )
        await task_a
        await task_b

    asyncio.run(scenario())

    assert len(provider.calls) == 2
    assert cells["a_stamp"] is not None, "cycle A never reached Phase 4 — failure"
    assert cells["a_stamp"] == old_ts, (
        "Q-1 FALSE-FRESH REPRODUCED: the degraded cycle re-stamped its "
        f"recycled data as fresh (a_stamp={cells['a_stamp']!r} != "
        f"old_ts={old_ts!r}) — the shared _fetch_degraded marker was "
        "clobbered by the interleaved fresh cycle's Phase-1 write before "
        "the degraded Phase-3 read"
    )
    assert service._fetch_degraded is False  # one-cycle mirror consumed


def test_sequential_cycles_unchanged_no_interleaving() -> None:
    """Sequential-semantics pin (must hold before AND after the fix).

    Same two-cycle shape but WITHOUT mid-span interleaving: B's fresh fetch
    completes fully before A's degraded cycle. Documented sequential behavior:
    B stamps fresh, A keeps that timestamp untouched (recycled board, degraded
    cycle), mirror consumed either way. Guards the fix against changing any
    sequential outcome.
    """
    provider = OrchestratedProvider(2)
    lock = asyncio.Lock()
    service = _make_service(provider, lock)
    old_ts = time.time() - 10_000.0
    service._last_fetch_ts = old_ts

    async def scenario() -> None:
        # B first: fresh fetch (fetch call #1 -> future #0) with a truthy
        # board so A's later fallback can still engage, stamps fresh.
        provider.resolve(0, [_snapshot()])
        task_b = asyncio.create_task(service.refresh(force=True))
        await _wait_until(lambda: len(provider.calls) == 1, "cycle B fetch suspension")
        await task_b
        fresh_ts = service._last_fetch_ts
        assert fresh_ts > old_ts
        # A second: degraded (fetch call #2 -> future #1), must keep the
        # (now fresh) timestamp untouched.
        provider.resolve(1, RuntimeError("synthetic provider outage (cycle A)"))
        await service.refresh(force=True)
        assert service._last_fetch_ts == fresh_ts

    asyncio.run(scenario())
    assert service._fetch_degraded is False


def test_mirrored_attribute_matches_cycle_outcome_after_completion() -> None:
    """Observability mirror contract: after ANY completed cycle the shared
    attribute is False (consumed one-cycle flag, byte-identical to the
    pre-fix sequential semantics pinned by test_refresh_false_fresh.py)."""
    provider = OrchestratedProvider(1)
    lock = asyncio.Lock()
    service = _make_service(provider, lock)
    service._last_fetch_ts = time.time() - 10_000.0

    async def one_degraded_cycle() -> None:
        provider.resolve(0, RuntimeError("synthetic provider outage"))
        await service.refresh(force=True)

    asyncio.run(one_degraded_cycle())
    assert service._fetch_degraded is False
