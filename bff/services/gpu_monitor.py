"""GPU thermal / utilization monitor (Slice F.16).

Polls ``nvidia-smi`` in the background at a fixed interval and keeps
the last :data:`_HISTORY_SECONDS` seconds of samples in a per-GPU
ring buffer. The frontend and the :mod:`openhands_tools_ext.gpu`
PRE-tool hook both read the buffer through the routes exposed by
:mod:`bff.routers.gpu`.

Design notes
------------

* **Local-first.** Colossus is single-user; no auth, no rate limits.
  If ``nvidia-smi`` isn't on ``PATH`` (e.g. CI / dev laptop), the
  poller stays alive but records an ``unavailable=True`` sample so
  the API can respond honestly instead of crashing.
* **Zero new port.** Poller uses ``asyncio.create_subprocess_exec``
  directly. No dependency on ``pynvml`` — a subprocess call every
  ``FORGE_GPU_POLL_SEC`` seconds is well within noise.
* **Bounded memory.** Ring is a ``collections.deque`` with
  ``maxlen = ceil(_HISTORY_SECONDS / poll_interval)``. At the
  default 2 s cadence and 15 min window that's ~450 samples per
  GPU, six floats each — trivial.
* **Cutoff.** ``FORGE_GPU_TEMP_CUTOFF_C`` (default 83, well below
  the Blackwell 5090's ~90 C throttle floor) is the threshold the
  PRE-tool hook consults. It is a soft advisory — the hook decides
  whether to block; the poller only reports.

Environment
-----------

* ``FORGE_GPU_POLL_SEC``      — polling interval, default 2.
* ``FORGE_GPU_TEMP_CUTOFF_C`` — advisory cutoff, default 83.
* ``FORGE_GPU_HISTORY_SEC``   — ring window, default 900 (15 min).
* ``FORGE_GPU_NVIDIA_SMI``    — override ``nvidia-smi`` binary path.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# nvidia-smi CSV columns we read. Kept in one place so the parser
# and the dataclass field order stay in lock-step.
_QUERY_FIELDS = (
    "index",
    "name",
    "temperature.gpu",
    "utilization.gpu",
    "memory.used",
    "memory.total",
    "power.draw",
)
_QUERY_STR = ",".join(_QUERY_FIELDS)


def _poll_seconds() -> float:
    try:
        val = float(os.environ.get("FORGE_GPU_POLL_SEC", "2"))
    except ValueError:
        return 2.0
    return max(0.5, val)


def _cutoff_celsius() -> float:
    try:
        val = float(os.environ.get("FORGE_GPU_TEMP_CUTOFF_C", "83"))
    except ValueError:
        return 83.0
    # Clamp to sane bounds so a bad env var can't disable the guard.
    return max(50.0, min(val, 95.0))


def _warn_celsius() -> float:
    """Yellow-band threshold. Frontend uses this to color the sparkline.

    Defaults to the Colossus RTX 5090 telemetry line (52 C).
    """
    try:
        val = float(os.environ.get("FORGE_GPU_TEMP_WARN_C", "52"))
    except ValueError:
        return 52.0
    return max(30.0, min(val, 90.0))


def _critical_celsius() -> float:
    """Red-band threshold. Distinct from the cutoff so the frontend can
    warn before the hook actually blocks.

    Defaults to the Colossus RTX 5090 red-line (88 C).
    """
    try:
        val = float(os.environ.get("FORGE_GPU_TEMP_CRITICAL_C", "88"))
    except ValueError:
        return 88.0
    return max(60.0, min(val, 95.0))


def _vram_cutoff_pct() -> float | None:
    """Advisory VRAM cutoff (0–100). None disables the guard."""
    raw = os.environ.get("FORGE_GPU_VRAM_CUTOFF_PCT", "").strip()
    if not raw:
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return max(1.0, min(val, 100.0))


def _util_cutoff_pct() -> float | None:
    """Advisory utilization cutoff (0–100). None disables the guard."""
    raw = os.environ.get("FORGE_GPU_UTIL_CUTOFF_PCT", "").strip()
    if not raw:
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return max(1.0, min(val, 100.0))


def _power_cutoff_w() -> float | None:
    """Advisory power cutoff in watts. None disables the guard.

    Empirical Colossus finding: sustained draw above ~435 W on the RTX
    5090 overheats fast even with the fan curve maxed. Set
    ``FORGE_GPU_POWER_CUTOFF_W=435`` (or lower) to have the PRE-tool
    hook block a turn when the poller sees the card at or above that
    number.
    """
    raw = os.environ.get("FORGE_GPU_POWER_CUTOFF_W", "").strip()
    if not raw:
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    # Clamp to a sensible board-power range (50 W–1500 W covers every
    # consumer + datacenter card we would ever run on Colossus).
    return max(50.0, min(val, 1500.0))


def _history_seconds() -> float:
    try:
        val = float(os.environ.get("FORGE_GPU_HISTORY_SEC", "900"))
    except ValueError:
        return 900.0
    return max(60.0, val)


def _nvidia_smi_path() -> str | None:
    override = os.environ.get("FORGE_GPU_NVIDIA_SMI")
    if override:
        return override
    return shutil.which("nvidia-smi")


@dataclass(frozen=True)
class GpuSample:
    """One nvidia-smi row at a point in time."""

    ts_epoch: float
    index: int
    name: str
    temperature_c: float | None
    utilization_pct: float | None
    memory_used_mib: float | None
    memory_total_mib: float | None
    power_w: float | None
    unavailable: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _RingBuffer:
    """Bounded per-GPU history ring."""

    samples: deque[GpuSample] = field(default_factory=deque)

    def append(self, sample: GpuSample, maxlen: int) -> None:
        if self.samples.maxlen != maxlen:  # type: ignore[attr-defined]
            self.samples = deque(self.samples, maxlen=maxlen)
        self.samples.append(sample)

    def slice(self, window_sec: float | None) -> list[GpuSample]:
        if window_sec is None:
            return list(self.samples)
        cutoff = time.time() - window_sec
        return [s for s in self.samples if s.ts_epoch >= cutoff]

    def latest(self) -> GpuSample | None:
        if not self.samples:
            return None
        return self.samples[-1]


class GpuMonitor:
    """Background poller with a per-GPU history ring."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._buffers: dict[int, _RingBuffer] = {}
        # Unavailable-mode ring, keyed by index -1 so callers can
        # still ask for "any GPU" state.
        self._unavailable: _RingBuffer = _RingBuffer()
        self._stop_event: asyncio.Event | None = None
        self._nvidia_smi = _nvidia_smi_path()
        self._maxlen = max(1, int(_history_seconds() / _poll_seconds()))

    # -- lifecycle ------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(
            self._run(), name="gpu-monitor-poller"
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        assert self._stop_event is not None
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=3.0)
        except TimeoutError:
            self._task.cancel()
            with _suppress_cancel():
                await self._task
        finally:
            self._task = None
            self._stop_event = None

    # -- polling --------------------------------------------------------

    async def _run(self) -> None:
        interval = _poll_seconds()
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                samples = await self._poll_once()
                for s in samples:
                    self._ingest(s)
            except Exception as exc:  # pragma: no cover — belt and braces
                log.warning("gpu monitor poll failed: %s", exc)
                self._ingest(_unavailable_sample(str(exc)))
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=interval
                )
            except TimeoutError:
                continue

    async def _poll_once(self) -> list[GpuSample]:
        if not self._nvidia_smi:
            return [_unavailable_sample("nvidia-smi not on PATH")]
        proc = await asyncio.create_subprocess_exec(
            self._nvidia_smi,
            f"--query-gpu={_QUERY_STR}",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=5.0
            )
        except TimeoutError:
            proc.kill()
            return [_unavailable_sample("nvidia-smi timed out")]
        if proc.returncode != 0:
            return [
                _unavailable_sample(
                    f"nvidia-smi rc={proc.returncode}: "
                    f"{stderr.decode('utf-8', 'replace').strip()[:200]}"
                )
            ]
        return _parse_csv(stdout.decode("utf-8", "replace"))

    def _ingest(self, sample: GpuSample) -> None:
        if sample.unavailable:
            self._unavailable.append(sample, self._maxlen)
            return
        buf = self._buffers.setdefault(sample.index, _RingBuffer())
        buf.append(sample, self._maxlen)

    # -- public reads ---------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return the latest sample from every known GPU, plus meta.

        The ``peaks`` block is the frontend / thermal-hook contract:
        one entry per resource, all optional, hottest across GPUs.
        """
        gpus = []
        for idx in sorted(self._buffers):
            latest = self._buffers[idx].latest()
            if latest is not None:
                gpus.append(latest.to_dict())
        unavailable = self._unavailable.latest()
        return {
            "available": bool(gpus),
            "cutoff_c": _cutoff_celsius(),
            "warn_c": _warn_celsius(),
            "critical_c": _critical_celsius(),
            "vram_cutoff_pct": _vram_cutoff_pct(),
            "util_cutoff_pct": _util_cutoff_pct(),
            "power_cutoff_w": _power_cutoff_w(),
            "poll_sec": _poll_seconds(),
            "gpus": gpus,
            "peaks": {
                "temperature_c": self.hottest_temperature(),
                "utilization_pct": self.peak_utilization_pct(),
                "vram_pct": self.peak_vram_pct(),
                "power_w": self.peak_power_w(),
            },
            "unavailable": unavailable.to_dict() if unavailable else None,
        }

    def history(self, window_sec: float | None) -> dict[str, Any]:
        """Return the ring slice (or full ring) per GPU."""
        return {
            "window_sec": window_sec,
            "cutoff_c": _cutoff_celsius(),
            "gpus": {
                str(idx): [s.to_dict() for s in buf.slice(window_sec)]
                for idx, buf in sorted(self._buffers.items())
            },
        }

    def hottest_temperature(self) -> float | None:
        """Highest current temperature across GPUs, or None if unknown."""
        temps: list[float] = []
        for buf in self._buffers.values():
            latest = buf.latest()
            if latest and latest.temperature_c is not None:
                temps.append(latest.temperature_c)
        return max(temps) if temps else None

    def peak_utilization_pct(self) -> float | None:
        """Highest current GPU utilization across GPUs, or None."""
        vals: list[float] = []
        for buf in self._buffers.values():
            latest = buf.latest()
            if latest and latest.utilization_pct is not None:
                vals.append(latest.utilization_pct)
        return max(vals) if vals else None

    def peak_vram_pct(self) -> float | None:
        """Highest current VRAM usage percentage across GPUs, or None.

        Returned as 0–100. Requires both memory_used and memory_total
        to be reported for a given GPU; a GPU missing either is skipped.
        """
        vals: list[float] = []
        for buf in self._buffers.values():
            latest = buf.latest()
            if (
                latest
                and latest.memory_used_mib is not None
                and latest.memory_total_mib
            ):
                vals.append(
                    100.0 * latest.memory_used_mib / latest.memory_total_mib
                )
        return max(vals) if vals else None

    def peak_power_w(self) -> float | None:
        """Highest current board power draw across GPUs, or None."""
        vals: list[float] = []
        for buf in self._buffers.values():
            latest = buf.latest()
            if latest and latest.power_w is not None:
                vals.append(latest.power_w)
        return max(vals) if vals else None


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def _parse_csv(text: str) -> list[GpuSample]:
    now = time.time()
    out: list[GpuSample] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(_QUERY_FIELDS):
            continue
        try:
            index = int(parts[0])
        except ValueError:
            continue
        out.append(
            GpuSample(
                ts_epoch=now,
                index=index,
                name=parts[1],
                temperature_c=_as_float(parts[2]),
                utilization_pct=_as_float(parts[3]),
                memory_used_mib=_as_float(parts[4]),
                memory_total_mib=_as_float(parts[5]),
                power_w=_as_float(parts[6]),
            )
        )
    return out


def _as_float(v: str) -> float | None:
    v = v.strip()
    if not v or v.lower() in {"n/a", "not supported", "unknown"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _unavailable_sample(msg: str) -> GpuSample:
    return GpuSample(
        ts_epoch=time.time(),
        index=-1,
        name="",
        temperature_c=None,
        utilization_pct=None,
        memory_used_mib=None,
        memory_total_mib=None,
        power_w=None,
        unavailable=True,
        error=msg,
    )


class _suppress_cancel:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is asyncio.CancelledError


# ---------------------------------------------------------------------------
# Module singleton — the BFF lifespan starts/stops this one instance.
# ---------------------------------------------------------------------------


_monitor: GpuMonitor | None = None


def get_monitor() -> GpuMonitor:
    global _monitor
    if _monitor is None:
        _monitor = GpuMonitor()
    return _monitor


async def start() -> None:
    await get_monitor().start()


async def stop() -> None:
    if _monitor is not None:
        await _monitor.stop()
