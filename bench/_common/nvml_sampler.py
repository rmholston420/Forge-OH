"""GPU sampler — background pynvml poller for bench instrumentation.

Samples GPU 0 at a fixed cadence (default 500ms) while a request is
in-flight. Returns aggregate stats (avg/max) at stop().

Fields captured per sample:
    - gpu_util_pct           (0-100)
    - vram_used_mib          (int)
    - gpu_temp_c             (int, degrees C)
    - power_draw_w           (float, watts)

Aggregates returned at stop():
    - samples                       int; number of samples taken
    - gpu_util_avg_pct              float
    - gpu_util_max_pct              int
    - vram_avg_mib                  float
    - vram_max_mib                  int
    - gpu_temp_avg_c                float
    - gpu_temp_max_c                int
    - power_avg_w                   float
    - power_max_w                   float
    - sampling_interval_s           float
    - sampling_wall_s               float

Design notes:
    - GPU index hard-coded to 0 (Colossus has single RTX 5090).
    - pynvml is thread-safe for read queries; sampler runs in a daemon thread.
    - If pynvml is unavailable (dev machine without NVIDIA driver), sampler
      degrades to no-op and stop() returns {"samples": 0, "nvml_available": False}.
    - Sampler is intentionally light: 500ms cadence over a ~30s request is
      ~60 samples, negligible CPU overhead vs vLLM inference load.

ADR-013 Path F: this replaces the un-instrumented Path E harness. All
future bench runs (F.19-post, ADR-013 amendments, and any later cell)
must use this sampler so VRAM/temperature/power/utilization are captured
alongside quality and speed.
"""
from __future__ import annotations

import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import pynvml  # type: ignore
    _NVML_AVAILABLE = True
except ImportError:
    pynvml = None  # type: ignore
    _NVML_AVAILABLE = False


@dataclass
class _Sample:
    ts: float
    gpu_util_pct: int
    vram_used_mib: int
    gpu_temp_c: int
    power_draw_w: float


@dataclass
class GpuStats:
    """Aggregate stats returned from GpuSampler.stop()."""
    samples: int = 0
    sampling_interval_s: float = 0.0
    sampling_wall_s: float = 0.0
    nvml_available: bool = True
    gpu_util_avg_pct: float = 0.0
    gpu_util_max_pct: int = 0
    vram_avg_mib: float = 0.0
    vram_max_mib: int = 0
    gpu_temp_avg_c: float = 0.0
    gpu_temp_max_c: int = 0
    power_avg_w: float = 0.0
    power_max_w: float = 0.0

    def to_dict(self) -> dict:
        return {
            "samples": self.samples,
            "sampling_interval_s": self.sampling_interval_s,
            "sampling_wall_s": round(self.sampling_wall_s, 3),
            "nvml_available": self.nvml_available,
            "gpu_util_avg_pct": round(self.gpu_util_avg_pct, 2),
            "gpu_util_max_pct": self.gpu_util_max_pct,
            "vram_avg_mib": round(self.vram_avg_mib, 1),
            "vram_max_mib": self.vram_max_mib,
            "gpu_temp_avg_c": round(self.gpu_temp_avg_c, 2),
            "gpu_temp_max_c": self.gpu_temp_max_c,
            "power_avg_w": round(self.power_avg_w, 2),
            "power_max_w": round(self.power_max_w, 2),
        }


class GpuSampler:
    """Background GPU sampler using pynvml.

    Usage:
        s = GpuSampler(interval_s=0.5)
        s.start()
        # ...run request...
        stats = s.stop()
        record["gpu"] = stats.to_dict()
    """

    def __init__(self, gpu_index: int = 0, interval_s: float = 0.5):
        self.gpu_index = gpu_index
        self.interval_s = interval_s
        self._samples: List[_Sample] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._handle = None
        self._t0: float = 0.0
        self._t1: float = 0.0
        self._nvml_initialized = False

    def _init_nvml(self) -> bool:
        if not _NVML_AVAILABLE:
            return False
        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
            self._nvml_initialized = True
            return True
        except Exception:
            return False

    def _shutdown_nvml(self) -> None:
        if self._nvml_initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml_initialized = False

    def _sample_once(self) -> Optional[_Sample]:
        if self._handle is None:
            return None
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            temp = pynvml.nvmlDeviceGetTemperature(self._handle, pynvml.NVML_TEMPERATURE_GPU)
            # power_usage returns milliwatts
            power_mw = pynvml.nvmlDeviceGetPowerUsage(self._handle)
        except Exception:
            return None
        return _Sample(
            ts=time.time(),
            gpu_util_pct=int(util.gpu),
            vram_used_mib=int(mem.used // (1024 * 1024)),
            gpu_temp_c=int(temp),
            power_draw_w=power_mw / 1000.0,
        )

    def _run(self) -> None:
        # Take samples until stop_event set.
        while not self._stop_event.is_set():
            s = self._sample_once()
            if s is not None:
                self._samples.append(s)
            # Sleep for interval, but wake early on stop.
            self._stop_event.wait(self.interval_s)

    def start(self) -> None:
        self._samples.clear()
        self._stop_event.clear()
        self._t0 = time.time()
        if not self._init_nvml():
            # NVML unavailable — sampler becomes a no-op.
            self._thread = None
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> GpuStats:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._t1 = time.time()
        self._shutdown_nvml()

        wall = self._t1 - self._t0
        if not self._samples:
            return GpuStats(
                samples=0,
                sampling_interval_s=self.interval_s,
                sampling_wall_s=wall,
                nvml_available=_NVML_AVAILABLE and self._nvml_initialized,
            )

        gpu_util = [s.gpu_util_pct for s in self._samples]
        vram = [s.vram_used_mib for s in self._samples]
        temp = [s.gpu_temp_c for s in self._samples]
        power = [s.power_draw_w for s in self._samples]

        return GpuStats(
            samples=len(self._samples),
            sampling_interval_s=self.interval_s,
            sampling_wall_s=wall,
            nvml_available=True,
            gpu_util_avg_pct=statistics.fmean(gpu_util),
            gpu_util_max_pct=max(gpu_util),
            vram_avg_mib=statistics.fmean(vram),
            vram_max_mib=max(vram),
            gpu_temp_avg_c=statistics.fmean(temp),
            gpu_temp_max_c=max(temp),
            power_avg_w=statistics.fmean(power),
            power_max_w=max(power),
        )


def _cli_smoke_test():
    """Standalone: sample for 5 seconds while printing progress.

    Run:
        python -m bench.pathF_instrumented.nvml_sampler
    """
    print(f"NVML available: {_NVML_AVAILABLE}")
    s = GpuSampler(interval_s=0.5)
    s.start()
    print("sampling for 5s...")
    time.sleep(5.0)
    stats = s.stop()
    import json
    print(json.dumps(stats.to_dict(), indent=2))


if __name__ == "__main__":
    _cli_smoke_test()
