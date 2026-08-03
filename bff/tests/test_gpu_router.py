"""Tests for the F.16 /api/gpu router.

The router is a thin adapter over the singleton monitor \u2014 these tests
inject known state into the monitor and check that the JSON shape and
query-parameter validation match the frontend contract.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from bff.services import gpu_monitor
from bff.services.gpu_monitor import GpuSample


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    """Build a FastAPI TestClient with a fresh gpu_monitor singleton.

    ``bff.main`` triggers real startup tasks (Neo4j, OpenHands client,
    trajectory drain). We import the app module for its ``app`` object
    and mount the router under test in isolation so these tests stay
    offline-safe and fast.
    """
    from fastapi import FastAPI

    from bff.routers import gpu

    # Reset the module singleton per-test.
    gpu_monitor._monitor = None  # type: ignore[attr-defined]

    app = FastAPI()
    app.include_router(gpu.router)
    return TestClient(app)


def _seed_sample(temp: float, index: int = 0) -> None:
    mon = gpu_monitor.get_monitor()
    mon._ingest(  # type: ignore[attr-defined]
        GpuSample(
            ts_epoch=time.time(),
            index=index,
            name=f"gpu-{index}",
            temperature_c=temp,
            utilization_pct=42,
            memory_used_mib=1024,
            memory_total_mib=32768,
            power_w=200,
        )
    )


class TestSnapshotRoute:
    def test_returns_unavailable_when_no_samples(self, client: TestClient) -> None:
        res = client.get("/api/gpu")
        assert res.status_code == 200
        body = res.json()
        assert body["available"] is False
        assert body["gpus"] == []
        # Bands + cutoff must always be present so the frontend can
        # color-code even before the first sample arrives.
        assert body["cutoff_c"] == pytest.approx(83.0)
        assert body["warn_c"] == pytest.approx(52.0)
        assert body["critical_c"] == pytest.approx(88.0)
        assert "poll_sec" in body
        assert body["peaks"] == {
            "temperature_c": None,
            "utilization_pct": None,
            "vram_pct": None,
            "power_w": None,
        }

    def test_returns_sample_when_present(self, client: TestClient) -> None:
        _seed_sample(temp=72.0)
        body = client.get("/api/gpu").json()
        assert body["available"] is True
        assert len(body["gpus"]) == 1
        g = body["gpus"][0]
        assert g["index"] == 0
        assert g["temperature_c"] == 72.0
        assert g["utilization_pct"] == 42
        peaks = body["peaks"]
        assert peaks["temperature_c"] == 72.0
        assert peaks["utilization_pct"] == 42.0
        # VRAM % derived from 1024 / 32768 = 3.125
        assert peaks["vram_pct"] == pytest.approx(3.125)
        assert peaks["power_w"] == 200.0

    def test_multiple_gpus_sorted_by_index(self, client: TestClient) -> None:
        _seed_sample(70.0, index=1)
        _seed_sample(68.0, index=0)
        body = client.get("/api/gpu").json()
        assert [g["index"] for g in body["gpus"]] == [0, 1]
        # Peaks aggregate across GPUs.
        assert body["peaks"]["temperature_c"] == 70.0

    def test_optional_cutoffs_exposed(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FORGE_GPU_VRAM_CUTOFF_PCT", "95")
        monkeypatch.setenv("FORGE_GPU_UTIL_CUTOFF_PCT", "98")
        monkeypatch.setenv("FORGE_GPU_POWER_CUTOFF_W", "435")
        body = client.get("/api/gpu").json()
        assert body["vram_cutoff_pct"] == pytest.approx(95.0)
        assert body["util_cutoff_pct"] == pytest.approx(98.0)
        assert body["power_cutoff_w"] == pytest.approx(435.0)


class TestHistoryRoute:
    def test_history_empty_by_default(self, client: TestClient) -> None:
        body = client.get("/api/gpu/history").json()
        assert body["window_sec"] is None
        assert body["gpus"] == {}

    def test_history_carries_sample(self, client: TestClient) -> None:
        _seed_sample(65.0)
        body = client.get("/api/gpu/history?window_sec=60").json()
        assert body["window_sec"] == 60.0
        assert list(body["gpus"].keys()) == ["0"]
        assert len(body["gpus"]["0"]) == 1

    def test_negative_window_rejected(self, client: TestClient) -> None:
        # FastAPI ge=0 validator surfaces as 422.
        assert client.get("/api/gpu/history?window_sec=-5").status_code == 422
