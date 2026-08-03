"""PRE-tool GPU thermal cutoff hook.

Invoked by the OpenHands SDK as::

    python -m openhands_tools_ext.gpu.hook

Contract (mirrors the SDK's ``HookType.COMMAND``):

* Reads the ``HookEvent`` payload as JSON on stdin (unused here — the
  guard is tool-agnostic; the matcher decides which tools it applies
  to).
* Consults ``GET /api/gpu`` on the BFF (default
  ``http://127.0.0.1:8081``) for the latest sample.
* Exits ``2`` (SDK's documented **blocking** exit code) when any of
  four thresholds is exceeded on the hottest / busiest GPU:

    - ``FORGE_GPU_TEMP_CUTOFF_C``    — thermal, default 83 C.
    - ``FORGE_GPU_POWER_CUTOFF_W``   — board power in watts, unset by
      default. Set e.g. ``435`` on the RTX 5090: sustained draw at or
      above that empirically overheats the card fast.
    - ``FORGE_GPU_VRAM_CUTOFF_PCT``  — VRAM usage %, unset by default
      (guard disabled). Set e.g. ``95`` to block when VRAM is
      saturated.
    - ``FORGE_GPU_UTIL_CUTOFF_PCT``  — utilization %, unset by
      default. Set e.g. ``98`` to yield tool time under sustained
      GPU load.

  ``stderr`` carries the reason; check order is
  thermal → power → VRAM → utilization (thermal is the direct
  hazard; power is its leading indicator).
* Exits ``0`` otherwise (allow), including when the BFF is
  unreachable or the poller reports ``unavailable=true`` — a
  "fall-open" allow is safer than blocking every tool call the
  moment the poller hiccups.

Environment
-----------

* ``FORGE_BFF_URL``             — BFF base URL, default
  ``http://127.0.0.1:8081``.
* ``FORGE_GPU_TEMP_CUTOFF_C``    — thermal cutoff, default 83.
* ``FORGE_GPU_POWER_CUTOFF_W``   — power cutoff in watts, disabled
  unless set. Recommended: 435 for RTX 5090.
* ``FORGE_GPU_VRAM_CUTOFF_PCT``  — VRAM cutoff (0–100), disabled
  unless set.
* ``FORGE_GPU_UTIL_CUTOFF_PCT``  — utilization cutoff (0–100),
  disabled unless set.
* ``FORGE_GPU_HOOK_TIMEOUT``    — HTTP timeout in seconds, default 2.
* ``FORGE_GPU_HOOK_DISABLED``   — set to ``1`` to short-circuit the
  hook (useful in CI / offline test runs).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def _cutoff() -> float:
    try:
        val = float(os.environ.get("FORGE_GPU_TEMP_CUTOFF_C", "83"))
    except ValueError:
        return 83.0
    return max(50.0, min(val, 95.0))


def _bff_url() -> str:
    return os.environ.get("FORGE_BFF_URL", "http://127.0.0.1:8081").rstrip("/")


def _timeout() -> float:
    try:
        return max(0.1, float(os.environ.get("FORGE_GPU_HOOK_TIMEOUT", "2")))
    except ValueError:
        return 2.0


def _fetch_snapshot() -> dict[str, Any] | None:
    url = f"{_bff_url()}/api/gpu"
    try:
        with urllib.request.urlopen(url, timeout=_timeout()) as resp:
            body = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _optional_pct(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return max(1.0, min(float(raw), 100.0))
    except ValueError:
        return None


def _optional_power_w(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return max(50.0, min(float(raw), 1500.0))
    except ValueError:
        return None


def _peaks(snapshot: dict[str, Any]) -> dict[str, float | None]:
    """Return peaks either from the ``peaks`` block (BFF supplies it)
    or derived from the raw ``gpus`` list (older BFFs, or tests).
    """
    peaks = snapshot.get("peaks") or {}
    out: dict[str, float | None] = {
        "temperature_c": _num(peaks.get("temperature_c")),
        "utilization_pct": _num(peaks.get("utilization_pct")),
        "vram_pct": _num(peaks.get("vram_pct")),
        "power_w": _num(peaks.get("power_w")),
    }
    if any(v is not None for v in out.values()):
        return out

    # Fallback: derive from raw samples.
    gpus = snapshot.get("gpus") or []
    temps: list[float] = []
    utils: list[float] = []
    vram: list[float] = []
    powers: list[float] = []
    for g in gpus:
        t = _num(g.get("temperature_c"))
        if t is not None:
            temps.append(t)
        u = _num(g.get("utilization_pct"))
        if u is not None:
            utils.append(u)
        used = _num(g.get("memory_used_mib"))
        total = _num(g.get("memory_total_mib"))
        if used is not None and total:
            vram.append(100.0 * used / total)
        p = _num(g.get("power_w"))
        if p is not None:
            powers.append(p)
    return {
        "temperature_c": max(temps) if temps else None,
        "utilization_pct": max(utils) if utils else None,
        "vram_pct": max(vram) if vram else None,
        "power_w": max(powers) if powers else None,
    }


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _emit_block(reason: str, payload_extras: dict[str, Any]) -> None:
    # JSON on stdout is optional; stderr is what the SDK logs to the
    # user-visible hook decision. Emit both for good measure.
    payload = {"decision": "deny", "reason": reason, **payload_extras}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stderr.write(reason + "\n")


def _emit_allow(msg: str = "") -> None:
    payload: dict[str, Any] = {"decision": "allow"}
    if msg:
        payload["reason"] = msg
    sys.stdout.write(json.dumps(payload) + "\n")


def main() -> int:
    # Drain stdin — the SDK writes the HookEvent there and we don't
    # want to leave a half-written pipe.
    try:
        sys.stdin.read()
    except Exception:
        pass

    if os.environ.get("FORGE_GPU_HOOK_DISABLED") == "1":
        _emit_allow("hook disabled via FORGE_GPU_HOOK_DISABLED")
        return 0

    snapshot = _fetch_snapshot()
    if snapshot is None:
        # BFF unreachable — fall open. See module docstring for rationale.
        _emit_allow("gpu snapshot unavailable")
        return 0

    if not snapshot.get("available", False):
        _emit_allow("gpu monitor unavailable")
        return 0

    # Effective cutoffs: prefer whatever the BFF reports (single source
    # of truth for the frontend + this hook), fall back to env-var
    # readers for older BFFs.
    temp_cutoff = _num(snapshot.get("cutoff_c")) or _cutoff()
    vram_cutoff = (
        _num(snapshot.get("vram_cutoff_pct"))
        or _optional_pct("FORGE_GPU_VRAM_CUTOFF_PCT")
    )
    util_cutoff = (
        _num(snapshot.get("util_cutoff_pct"))
        or _optional_pct("FORGE_GPU_UTIL_CUTOFF_PCT")
    )
    power_cutoff = (
        _num(snapshot.get("power_cutoff_w"))
        or _optional_power_w("FORGE_GPU_POWER_CUTOFF_W")
    )

    peaks = _peaks(snapshot)
    hottest = peaks["temperature_c"]
    peak_util = peaks["utilization_pct"]
    peak_vram = peaks["vram_pct"]
    peak_power = peaks["power_w"]

    if (
        hottest is None
        and peak_util is None
        and peak_vram is None
        and peak_power is None
    ):
        _emit_allow("no gpu samples")
        return 0

    # Ordered checks: thermal → power → VRAM → utilization.
    # First trip blocks; keep the diagnostic fields in the payload
    # regardless of which cutoff tripped so the frontend can render
    # the whole context.
    extras: dict[str, Any] = {
        "hottest_temperature_c": hottest,
        "cutoff_c": temp_cutoff,
        "peak_power_w": peak_power,
        "power_cutoff_w": power_cutoff,
        "peak_utilization_pct": peak_util,
        "peak_vram_pct": peak_vram,
        "vram_cutoff_pct": vram_cutoff,
        "util_cutoff_pct": util_cutoff,
    }

    if hottest is not None and hottest >= temp_cutoff:
        _emit_block(
            reason=(
                f"GPU thermal cutoff hit: hottest={hottest:.1f} C >= "
                f"cutoff={temp_cutoff:.1f} C — pausing tool execution."
            ),
            payload_extras=extras,
        )
        return 2

    if (
        power_cutoff is not None
        and peak_power is not None
        and peak_power >= power_cutoff
    ):
        _emit_block(
            reason=(
                f"GPU power cutoff hit: peak={peak_power:.1f} W >= "
                f"cutoff={power_cutoff:.1f} W — pausing tool execution."
            ),
            payload_extras=extras,
        )
        return 2

    if (
        vram_cutoff is not None
        and peak_vram is not None
        and peak_vram >= vram_cutoff
    ):
        _emit_block(
            reason=(
                f"GPU VRAM cutoff hit: peak={peak_vram:.1f}% >= "
                f"cutoff={vram_cutoff:.1f}% — pausing tool execution."
            ),
            payload_extras=extras,
        )
        return 2

    if (
        util_cutoff is not None
        and peak_util is not None
        and peak_util >= util_cutoff
    ):
        _emit_block(
            reason=(
                f"GPU utilization cutoff hit: peak={peak_util:.1f}% >= "
                f"cutoff={util_cutoff:.1f}% — pausing tool execution."
            ),
            payload_extras=extras,
        )
        return 2

    parts: list[str] = []
    if hottest is not None:
        parts.append(f"temp={hottest:.1f}C<{temp_cutoff:.0f}C")
    if peak_power is not None:
        cutoff_str = f"<{power_cutoff:.0f}W" if power_cutoff is not None else ""
        parts.append(f"pwr={peak_power:.0f}W{cutoff_str}")
    if peak_util is not None:
        cutoff_str = f"<{util_cutoff:.0f}%" if util_cutoff is not None else ""
        parts.append(f"util={peak_util:.0f}%{cutoff_str}")
    if peak_vram is not None:
        cutoff_str = f"<{vram_cutoff:.0f}%" if vram_cutoff is not None else ""
        parts.append(f"vram={peak_vram:.0f}%{cutoff_str}")
    _emit_allow(" ".join(parts) if parts else "below cutoffs")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
