"""Trajectory indexer drain scheduler (Slice F.13).

The trajectory hook (``openhands_tools_ext.trajectory.hook``) writes
records with ``embedding IS NULL`` when
``FORGE_OH_TRAJECTORY_INDEX_INLINE`` is unset \u2014 the default and the
recommended setting, because inline embedding on every STOP would add
seconds of GPU time to the tail of every run.

This module keeps those pending records from piling up forever by
running :meth:`TrajectoryIndexer.index_pending` on a fixed interval as
a background asyncio task owned by the BFF's lifespan. It also exposes
a :meth:`drain_once` method so an HTTP endpoint (or a test harness) can
force an immediate pass without waiting for the next tick.

Design notes:

* **One task per process.** Multiple BFF workers would each schedule
  their own drain; that's acceptable because
  :meth:`TrajectoryStore.update_embedding` is idempotent (last write
  wins on the same trajectory_id, and by construction only unembedded
  rows are pulled).
* **Never crashes the app.** Any exception inside the loop is logged
  and swallowed; the next tick tries again. A permanent embedder
  failure will spam WARN logs, which is the correct visibility
  (loud but non-fatal).
* **Cancellation-clean.** ``stop()`` cancels the task and awaits its
  cancellation so shutdown is deterministic.
* **Threaded embed calls.** The indexer's ``embed_batch`` is a
  potentially long CPU/GPU call; we run it in a thread via
  ``asyncio.to_thread`` so the event loop stays responsive.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openhands_tools_ext.trajectory.store import TrajectoryStore
    from openhands_tools_ext.trajectory.writer import TrajectoryIndexer

log = logging.getLogger(__name__)

# Environment knobs. Kept as module constants so tests can monkeypatch
# them and so operators can tune them without a code change.
DEFAULT_INTERVAL_SECONDS = 60.0
"""Seconds between drain passes. Overridable via ``FORGE_OH_TRAJECTORY_DRAIN_INTERVAL``."""

DEFAULT_BATCH_SIZE = 32
"""Records embedded per pass. Overridable via ``FORGE_OH_TRAJECTORY_DRAIN_BATCH``."""

DISABLED_ENV = "FORGE_OH_TRAJECTORY_DRAIN_DISABLED"
"""Set to ``1`` to skip starting the drain task on lifespan startup."""


def _read_interval() -> float:
    raw = os.environ.get("FORGE_OH_TRAJECTORY_DRAIN_INTERVAL")
    if raw is None:
        return DEFAULT_INTERVAL_SECONDS
    try:
        value = float(raw)
    except ValueError:
        log.warning(
            "FORGE_OH_TRAJECTORY_DRAIN_INTERVAL=%r is not a number; using %.0fs",
            raw,
            DEFAULT_INTERVAL_SECONDS,
        )
        return DEFAULT_INTERVAL_SECONDS
    if value <= 0:
        log.warning(
            "FORGE_OH_TRAJECTORY_DRAIN_INTERVAL=%.1f <= 0; using %.0fs",
            value,
            DEFAULT_INTERVAL_SECONDS,
        )
        return DEFAULT_INTERVAL_SECONDS
    return value


def _read_batch_size() -> int:
    raw = os.environ.get("FORGE_OH_TRAJECTORY_DRAIN_BATCH")
    if raw is None:
        return DEFAULT_BATCH_SIZE
    try:
        value = int(raw)
    except ValueError:
        log.warning(
            "FORGE_OH_TRAJECTORY_DRAIN_BATCH=%r is not an int; using %d",
            raw,
            DEFAULT_BATCH_SIZE,
        )
        return DEFAULT_BATCH_SIZE
    if value <= 0:
        log.warning(
            "FORGE_OH_TRAJECTORY_DRAIN_BATCH=%d <= 0; using %d",
            value,
            DEFAULT_BATCH_SIZE,
        )
        return DEFAULT_BATCH_SIZE
    return value


@dataclass
class DrainMetrics:
    """Cumulative counters exposed for inspection.

    These are intentionally simple ints \u2014 no Prometheus/OTel dependency
    for a single-user local system. If we ever need a real metrics
    surface, promote these to a real registry and keep the shape.
    """

    passes: int = 0
    """Total drain passes attempted (including empty ones)."""
    indexed: int = 0
    """Total records embedded across all passes."""
    errors: int = 0
    """Total passes that raised an exception."""
    last_error: str = field(default="")
    """String repr of the most recent exception, or empty."""


class TrajectoryDrainScheduler:
    """Owns the background drain asyncio task."""

    def __init__(
        self,
        store: TrajectoryStore,
        *,
        indexer_factory: type[TrajectoryIndexer] | None = None,
        interval_seconds: float | None = None,
        batch_size: int | None = None,
    ) -> None:
        # Lazy import so unit tests that don't touch the indexer path
        # (or don't have the embedder deps available) can still import
        # this module.
        if indexer_factory is None:
            from openhands_tools_ext.trajectory.writer import TrajectoryIndexer

            indexer_factory = TrajectoryIndexer

        self._store = store
        self._indexer_factory = indexer_factory
        self._interval = (
            interval_seconds if interval_seconds is not None else _read_interval()
        )
        self._batch_size = (
            batch_size if batch_size is not None else _read_batch_size()
        )
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self.metrics = DrainMetrics()

    @property
    def interval_seconds(self) -> float:
        return self._interval

    @property
    def batch_size(self) -> int:
        return self._batch_size

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def drain_once(self) -> int:
        """Run one indexer pass immediately.

        Returns the number of records embedded. Any exception is caught
        and reflected in :attr:`metrics.last_error` \u2014 callers on the
        HTTP path can check the metrics to distinguish "0 pending" from
        "embedder blew up". Never raises.
        """
        self.metrics.passes += 1
        try:
            # Build a fresh indexer per pass so a busted default embedder
            # can be swapped out at runtime by rewriting the module-level
            # default. Cost is negligible.
            indexer = self._indexer_factory(self._store, batch_size=self._batch_size)
            count = await asyncio.to_thread(indexer.index_pending)
            self.metrics.indexed += count
            return count
        except Exception as exc:
            self.metrics.errors += 1
            self.metrics.last_error = repr(exc)
            log.warning("trajectory drain pass failed: %s", exc)
            return 0

    async def _loop(self) -> None:
        # First pass runs immediately so a freshly-started BFF drains
        # any records the previous process left behind.
        log.info(
            "trajectory drain scheduler starting (interval=%.1fs, batch=%d)",
            self._interval,
            self._batch_size,
        )
        try:
            while not self._stop_event.is_set():
                indexed = await self.drain_once()
                if indexed:
                    log.info("trajectory drain: indexed %d record(s)", indexed)
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self._interval
                    )
                except TimeoutError:
                    # Normal tick expiration; loop.
                    continue
        except asyncio.CancelledError:
            log.info("trajectory drain scheduler cancelled")
            raise
        finally:
            log.info(
                "trajectory drain scheduler stopped "
                "(passes=%d, indexed=%d, errors=%d)",
                self.metrics.passes,
                self.metrics.indexed,
                self.metrics.errors,
            )

    def start(self) -> None:
        """Kick off the background loop. Safe to call multiple times."""
        if self.is_running():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(
            self._loop(), name="forge-oh-trajectory-drain"
        )

    async def stop(self) -> None:
        """Signal shutdown and await the task's exit."""
        if self._task is None:
            return
        self._stop_event.set()
        # Fast-path shutdown: cancel if the sleep hasn't returned yet.
        if not self._task.done():
            self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception) as exc:
            # We deliberately swallow exceptions during shutdown so a
            # busted drain can never prevent app shutdown.
            if not isinstance(exc, asyncio.CancelledError):
                log.warning("trajectory drain task raised during shutdown: %s", exc)
        finally:
            self._task = None


# ---------------------------------------------------------------------------
# Process-wide singleton, wired to the FastAPI lifespan.
# ---------------------------------------------------------------------------

_scheduler: TrajectoryDrainScheduler | None = None


def get_scheduler() -> TrajectoryDrainScheduler | None:
    """Return the process-wide scheduler if one is running, else None."""
    return _scheduler


async def start_scheduler(store: TrajectoryStore) -> TrajectoryDrainScheduler | None:
    """Create and start the process-wide drain scheduler.

    Returns the scheduler, or ``None`` if drain is disabled by env.
    Idempotent: repeated calls return the existing scheduler.
    """
    global _scheduler
    if os.environ.get(DISABLED_ENV) == "1":
        log.info(
            "trajectory drain scheduler disabled via %s=1", DISABLED_ENV
        )
        return None
    if _scheduler is not None:
        return _scheduler
    _scheduler = TrajectoryDrainScheduler(store)
    _scheduler.start()
    return _scheduler


async def stop_scheduler() -> None:
    """Stop and clear the process-wide scheduler."""
    global _scheduler
    if _scheduler is None:
        return
    await _scheduler.stop()
    _scheduler = None
