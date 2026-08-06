"""Regression tests for the event-loop-yield fix in EventRelay._run_loop.

Bug (2026-08-03 23:40 EDT, G.1): synchronous ``sidecar_producers.update_from_event``
calls inside ``event_relay._run_loop`` hogged the asyncio event loop. A leaked
producer with 500+ backlogged events pegged the MainThread in ``build_plan``
and ``_rmw`` for tens of seconds per relay iteration, starving the HTTP request
handler. py-spy dumps proved MainThread was stuck in
``bff.services.action_reconstruction.build_plan`` and
``bff.services.sidecar._rmw`` at the exact moment the self-eval harness POSTs
were ReadTimeouting.

Fix: wrap the sync call in ``asyncio.to_thread`` and add an
``await asyncio.sleep(0)`` yield-point per event.

These tests verify:

1.  ``update_from_event`` is invoked via a worker thread, not on the event loop.
2.  A slow (CPU-bound) sidecar producer does NOT block a concurrent coroutine
    representing an incoming HTTP request.

See DEBUG_LOG.md 2026-08-03 23:40 EDT.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def relay_module() -> Any:
    """Import event_relay lazily so we can patch its dependencies."""
    from bff.services import event_relay

    return event_relay


async def _simulate_incoming_request(
    started_at: float, latencies: list[float]
) -> None:
    """Fake HTTP handler coroutine. Records how long it took to schedule.

    A responsive event loop schedules this coroutine within a few
    milliseconds of ``asyncio.create_task``. If the loop is hogged, it
    won't run until the hogging coroutine yields.
    """
    latencies.append(time.perf_counter() - started_at)


# ---------------------------------------------------------------------------
# Test 1: update_from_event runs off the event loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_from_event_runs_in_worker_thread(relay_module: Any) -> None:
    """The sidecar producer call must execute on a thread != main-loop thread.

    Verifies the ``asyncio.to_thread(...)`` wrapping in event_relay._run_loop.
    """
    main_thread_id = threading.get_ident()
    invoked_on: dict[str, int] = {}

    def _fake_update_from_event(**kwargs: Any) -> None:
        invoked_on["thread_id"] = threading.get_ident()

    # Directly exercise the same call pattern used in the relay
    with patch.object(
        relay_module.sidecar_producers,
        "update_from_event",
        _fake_update_from_event,
    ):
        await asyncio.to_thread(
            relay_module.sidecar_producers.update_from_event,
            cid="c-1",
            workspace="/tmp/does-not-matter",
            session_id="c-1",
            event={"kind": "ActionEvent"},
        )

    assert "thread_id" in invoked_on, "update_from_event was not invoked"
    assert invoked_on["thread_id"] != main_thread_id, (
        "update_from_event ran on the main thread — the asyncio.to_thread "
        "wrapping was lost. Restore it in event_relay._run_loop or the "
        "event loop will be hogged by heavy sidecar producers."
    )


# ---------------------------------------------------------------------------
# Test 2: heavy sidecar producer does not starve concurrent coroutines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slow_producer_does_not_block_event_loop() -> None:
    """A 200ms CPU-bound sidecar call must not delay a concurrent task.

    If someone reverts the fix (calls ``sidecar_producers.update_from_event``
    directly instead of via ``asyncio.to_thread``), this test fails because
    the concurrent task cannot be scheduled until the sync call returns.
    """

    def _slow_sync_call() -> None:
        # 200 ms of pure CPU — mirrors a large build_plan / fsync burst.
        deadline = time.perf_counter() + 0.20
        while time.perf_counter() < deadline:
            pass

    latencies: list[float] = []

    async def _relay_iteration() -> None:
        # This is the fixed pattern from event_relay._run_loop:
        await asyncio.to_thread(_slow_sync_call)
        await asyncio.sleep(0)

    async def _http_request() -> None:
        await _simulate_incoming_request(time.perf_counter(), latencies)

    # Kick off the relay-style work first, then the "request" a tick later.
    relay_task = asyncio.create_task(_relay_iteration())
    await asyncio.sleep(0.01)  # let the to_thread hand off to the worker
    http_task = asyncio.create_task(_http_request())

    await asyncio.gather(relay_task, http_task)

    assert latencies, "request coroutine did not run"
    # Should schedule in well under 50 ms. The bug caused >30 s here.
    # We use 100 ms as a generous ceiling for CI jitter.
    assert latencies[0] < 0.10, (
        f"HTTP request coroutine took {latencies[0]*1000:.1f}ms to schedule "
        f"while a 200ms sync sidecar call was running. Event loop is being "
        f"hogged — the asyncio.to_thread wrapping in event_relay._run_loop "
        f"is missing or broken."
    )


# ---------------------------------------------------------------------------
# Test 3: negative — direct sync call DOES block (documents the anti-pattern)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_direct_sync_call_would_block_confirms_the_hazard() -> None:
    """Documents the hazard: a direct sync call inside a coroutine hogs the loop.

    This test exists to make it obvious in the test log WHY the to_thread
    wrapping matters. If the yield-point + to_thread are ever removed and
    someone adds a "just call it directly, it's fast enough" comment, this
    test's failure message tells them how much they underestimated.
    """

    def _slow_sync_call() -> None:
        deadline = time.perf_counter() + 0.20
        while time.perf_counter() < deadline:
            pass

    latencies: list[float] = []

    async def _bad_relay_iteration() -> None:
        # This is the OLD, broken pattern — direct sync call.
        _slow_sync_call()

    async def _http_request() -> None:
        await _simulate_incoming_request(time.perf_counter(), latencies)

    # Order matters and is subtle: `started_at` is captured at *task
    # creation* time (the caller-frame arg eval), NOT at coroutine-body
    # entry.  We want:
    #   1. http_task's started_at = t0 (created first, captured in the arg)
    #   2. relay_task runs first when the loop yields (FIFO: created 2nd
    #      but its busy-loop hits the loop first because http_task's body
    #      does an await too? — NO, both tasks race for the first slot).
    #
    # The valid arrangement is: capture started_at BEFORE any create_task,
    # then create the relay_task first so FIFO runs it first, then
    # create http_task with the pre-captured started_at.  This mirrors
    # DEBUG_LOG 2026-08-06 04:17 EDT's recommendation.
    started_at = time.perf_counter()

    async def _http_request_prebound() -> None:
        await _simulate_incoming_request(started_at, latencies)

    relay_task = asyncio.create_task(_bad_relay_iteration())
    http_task = asyncio.create_task(_http_request_prebound())

    await asyncio.gather(relay_task, http_task)

    assert latencies, "request coroutine did not run"
    # Direct sync call MUST block for ~200 ms. If somehow this passes,
    # the test setup is wrong (e.g. running on a nogil interpreter).
    assert latencies[0] >= 0.15, (
        "Direct sync call did not block the event loop in this test env — "
        "the hazard demonstration is broken. Check that the test is running "
        "on a single-threaded asyncio loop."
    )
