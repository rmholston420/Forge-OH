"""Tests for the F.16 GPU thermal monitor.

Focus: CSV parsing, ring buffer behaviour, snapshot/history JSON shape,
and the graceful "nvidia-smi missing" path. The poller loop itself is
exercised indirectly by patching ``_poll_once`` from the unit tests \u2014
we don't spin up a real subprocess in bff/tests.
"""

from __future__ import annotations

import time

import pytest

from bff.services import gpu_monitor
from bff.services.gpu_monitor import (
    GpuMonitor,
    GpuSample,
    _parse_csv,
    _unavailable_sample,
)


class TestCsvParsing:
    def test_parses_single_gpu_row(self) -> None:
        raw = "0, NVIDIA GeForce RTX 5090, 62, 34, 8192, 32768, 145.20\n"
        samples = _parse_csv(raw)
        assert len(samples) == 1
        s = samples[0]
        assert s.index == 0
        assert s.name == "NVIDIA GeForce RTX 5090"
        assert s.temperature_c == 62.0
        assert s.utilization_pct == 34.0
        assert s.memory_used_mib == 8192.0
        assert s.memory_total_mib == 32768.0
        assert s.power_w == pytest.approx(145.2)
        assert not s.unavailable

    def test_parses_multi_gpu(self) -> None:
        raw = (
            "0, A100, 55, 20, 1024, 40960, 100.00\n"
            "1, A100, 66, 55, 2048, 40960, 220.00\n"
        )
        samples = _parse_csv(raw)
        assert [s.index for s in samples] == [0, 1]
        assert samples[1].temperature_c == 66.0

    def test_handles_na_fields(self) -> None:
        raw = "0, X, N/A, [Not Supported], 100, 200, N/A\n"
        s = _parse_csv(raw)[0]
        assert s.temperature_c is None
        # "[Not Supported]" isn't in the sentinel set exactly \u2014 float parse
        # fails, treated as None.
        assert s.utilization_pct is None
        assert s.power_w is None
        assert s.memory_used_mib == 100.0

    def test_ignores_blank_and_malformed_lines(self) -> None:
        raw = "\n\nBAD_LINE\n0, X, 60, 10, 100, 200, 5\n"
        samples = _parse_csv(raw)
        assert len(samples) == 1
        assert samples[0].index == 0


class TestRingBuffer:
    def test_snapshot_empty_when_never_polled(self) -> None:
        m = GpuMonitor()
        snap = m.snapshot()
        assert snap["available"] is False
        assert snap["gpus"] == []
        assert snap["unavailable"] is None

    def test_ingest_records_latest_per_gpu(self) -> None:
        m = GpuMonitor()
        now = time.time()
        m._ingest(  # type: ignore[attr-defined]
            GpuSample(
                ts_epoch=now,
                index=0,
                name="X",
                temperature_c=70,
                utilization_pct=10,
                memory_used_mib=100,
                memory_total_mib=1000,
                power_w=50,
            )
        )
        m._ingest(  # type: ignore[attr-defined]
            GpuSample(
                ts_epoch=now + 1,
                index=0,
                name="X",
                temperature_c=72,
                utilization_pct=15,
                memory_used_mib=110,
                memory_total_mib=1000,
                power_w=55,
            )
        )
        snap = m.snapshot()
        assert snap["available"] is True
        assert len(snap["gpus"]) == 1
        assert snap["gpus"][0]["temperature_c"] == 72
        assert m.hottest_temperature() == 72

    def test_unavailable_flow_records_but_stays_unavailable(self) -> None:
        m = GpuMonitor()
        m._ingest(_unavailable_sample("nvidia-smi missing"))  # type: ignore[attr-defined]
        snap = m.snapshot()
        assert snap["available"] is False
        assert snap["unavailable"] is not None
        assert "nvidia-smi missing" in snap["unavailable"]["error"]

    def test_history_windowing(self) -> None:
        m = GpuMonitor()
        now = time.time()
        for i, ts in enumerate([now - 1000, now - 100, now - 10, now]):
            m._ingest(  # type: ignore[attr-defined]
                GpuSample(
                    ts_epoch=ts,
                    index=0,
                    name="X",
                    temperature_c=60 + i,
                    utilization_pct=0,
                    memory_used_mib=0,
                    memory_total_mib=1,
                    power_w=0,
                )
            )
        # 60-second window keeps only the last 2 samples.
        hist = m.history(window_sec=60)
        assert len(hist["gpus"]["0"]) == 2
        # None-window returns the whole ring.
        full = m.history(window_sec=None)
        assert len(full["gpus"]["0"]) == 4


class TestPollingFallOpen:
    @pytest.mark.asyncio
    async def test_no_nvidia_smi_records_unavailable_sample(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When nvidia-smi is missing, _poll_once must not raise."""
        monkeypatch.setattr(gpu_monitor, "_nvidia_smi_path", lambda: None)
        m = GpuMonitor()
        m._nvidia_smi = None  # simulate missing binary post-construction
        samples = await m._poll_once()  # type: ignore[attr-defined]
        assert len(samples) == 1
        assert samples[0].unavailable is True
        assert "nvidia-smi" in samples[0].error


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop_is_idempotent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeat start() must not spawn a second task; stop() must clean up."""
        monkeypatch.setattr(gpu_monitor, "_nvidia_smi_path", lambda: None)
        # Reset the module singleton so this test runs in isolation.
        gpu_monitor._monitor = None  # type: ignore[attr-defined]
        await gpu_monitor.start()
        first_task = gpu_monitor.get_monitor()._task  # type: ignore[attr-defined]
        await gpu_monitor.start()
        assert gpu_monitor.get_monitor()._task is first_task  # type: ignore[attr-defined]
        await gpu_monitor.stop()
        assert gpu_monitor.get_monitor()._task is None  # type: ignore[attr-defined]
        # Second stop is a no-op.
        await gpu_monitor.stop()
