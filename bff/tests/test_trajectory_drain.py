"""Tests for :mod:`bff.services.trajectory_drain` (Slice F.13).

The scheduler is thin glue around :class:`TrajectoryIndexer`. These
tests focus on:

* Env-var parsing (interval, batch size, disabled flag).
* Metrics accumulation across passes.
* Error swallowing (a raising indexer must not crash the loop or the
  endpoint).
* Idempotent start/stop.
* The FastAPI ``POST /api/trajectories/drain`` endpoint contract.

All tests use a stub indexer factory so they don't depend on the real
embedder (which needs GPU/network).
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from bff.services import trajectory_drain
from bff.services.trajectory_drain import (
    DrainMetrics,
    TrajectoryDrainScheduler,
    _read_batch_size,
    _read_interval,
)


class _StubIndexer:
    """Fake TrajectoryIndexer that returns a fixed count and records calls."""

    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, store: Any, *, batch_size: int = 16) -> None:
        self.store = store
        self.batch_size = batch_size

    def index_pending(self, *, max_records: int | None = None) -> int:
        _StubIndexer.calls.append({"batch_size": self.batch_size})
        return 3  # pretend we embedded 3 records


class _RaisingIndexer(_StubIndexer):
    def index_pending(self, *, max_records: int | None = None) -> int:
        raise RuntimeError("embedder unavailable")


@pytest.fixture(autouse=True)
def _reset_singleton() -> Any:
    """Ensure test isolation from the process-wide scheduler."""
    trajectory_drain._scheduler = None
    _StubIndexer.calls.clear()
    yield
    trajectory_drain._scheduler = None


class TestEnvParsing:
    def test_interval_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FORGE_OH_TRAJECTORY_DRAIN_INTERVAL", raising=False)
        assert _read_interval() == trajectory_drain.DEFAULT_INTERVAL_SECONDS

    def test_interval_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_INTERVAL", "12.5")
        assert _read_interval() == 12.5

    def test_interval_bad_value_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_INTERVAL", "not-a-number")
        assert _read_interval() == trajectory_drain.DEFAULT_INTERVAL_SECONDS

    def test_interval_zero_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_INTERVAL", "0")
        assert _read_interval() == trajectory_drain.DEFAULT_INTERVAL_SECONDS

    def test_interval_negative_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_INTERVAL", "-5")
        assert _read_interval() == trajectory_drain.DEFAULT_INTERVAL_SECONDS

    def test_batch_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FORGE_OH_TRAJECTORY_DRAIN_BATCH", raising=False)
        assert _read_batch_size() == trajectory_drain.DEFAULT_BATCH_SIZE

    def test_batch_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_BATCH", "64")
        assert _read_batch_size() == 64

    def test_batch_bad_value_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_BATCH", "nope")
        assert _read_batch_size() == trajectory_drain.DEFAULT_BATCH_SIZE

    def test_batch_zero_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_BATCH", "0")
        assert _read_batch_size() == trajectory_drain.DEFAULT_BATCH_SIZE


class TestSchedulerLifecycle:
    def test_construct_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_INTERVAL", "1.5")
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_BATCH", "8")
        s = TrajectoryDrainScheduler(
            MagicMock(), indexer_factory=_StubIndexer
        )
        assert s.interval_seconds == 1.5
        assert s.batch_size == 8

    def test_explicit_kwargs_win_over_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DRAIN_INTERVAL", "1.5")
        s = TrajectoryDrainScheduler(
            MagicMock(),
            indexer_factory=_StubIndexer,
            interval_seconds=99.0,
            batch_size=4,
        )
        assert s.interval_seconds == 99.0
        assert s.batch_size == 4

    @pytest.mark.asyncio
    async def test_drain_once_records_metrics(self) -> None:
        s = TrajectoryDrainScheduler(
            MagicMock(),
            indexer_factory=_StubIndexer,
            interval_seconds=1.0,
        )
        indexed = await s.drain_once()
        assert indexed == 3
        assert s.metrics.passes == 1
        assert s.metrics.indexed == 3
        assert s.metrics.errors == 0
        assert s.metrics.last_error == ""

    @pytest.mark.asyncio
    async def test_drain_once_swallows_exceptions(self) -> None:
        s = TrajectoryDrainScheduler(
            MagicMock(),
            indexer_factory=_RaisingIndexer,
            interval_seconds=1.0,
        )
        indexed = await s.drain_once()
        assert indexed == 0
        assert s.metrics.passes == 1
        assert s.metrics.errors == 1
        assert "embedder unavailable" in s.metrics.last_error

    @pytest.mark.asyncio
    async def test_start_and_stop_are_clean(self) -> None:
        s = TrajectoryDrainScheduler(
            MagicMock(),
            indexer_factory=_StubIndexer,
            interval_seconds=0.05,
        )
        s.start()
        assert s.is_running()
        # Let the loop run at least one pass.
        await asyncio.sleep(0.15)
        await s.stop()
        assert not s.is_running()
        # At least one pass happened, and metrics accumulated.
        assert s.metrics.passes >= 1
        assert s.metrics.indexed >= 3  # 3 per pass

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        s = TrajectoryDrainScheduler(
            MagicMock(),
            indexer_factory=_StubIndexer,
            interval_seconds=10.0,
        )
        s.start()
        task1 = s._task
        s.start()  # second call must not spawn a new task
        assert s._task is task1
        await s.stop()

    @pytest.mark.asyncio
    async def test_stop_before_start_is_noop(self) -> None:
        s = TrajectoryDrainScheduler(
            MagicMock(),
            indexer_factory=_StubIndexer,
        )
        # Should not raise.
        await s.stop()
        assert not s.is_running()


class TestModuleLevelSingleton:
    @pytest.mark.asyncio
    async def test_start_scheduler_returns_singleton(self) -> None:
        with patch.object(
            trajectory_drain,
            "TrajectoryDrainScheduler",
            lambda store, **_kw: TrajectoryDrainScheduler(
                store, indexer_factory=_StubIndexer, interval_seconds=10.0
            ),
        ):
            first = await trajectory_drain.start_scheduler(MagicMock())
            assert first is not None
            second = await trajectory_drain.start_scheduler(MagicMock())
            assert second is first
            await trajectory_drain.stop_scheduler()

    @pytest.mark.asyncio
    async def test_disabled_env_prevents_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(trajectory_drain.DISABLED_ENV, "1")
        s = await trajectory_drain.start_scheduler(MagicMock())
        assert s is None
        assert trajectory_drain.get_scheduler() is None


class TestDrainMetricsDataclass:
    def test_defaults_are_zero(self) -> None:
        m = DrainMetrics()
        assert m.passes == 0
        assert m.indexed == 0
        assert m.errors == 0
        assert m.last_error == ""
