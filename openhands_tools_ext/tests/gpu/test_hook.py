"""Unit tests for the F.16 PRE-tool GPU thermal cutoff hook.

The hook is a small script: three inputs (env, stdin, BFF snapshot) and
one output (exit code + JSON on stdout). We stub the HTTP call and
drive main() directly.
"""

from __future__ import annotations

import io
import json
import sys
from typing import Any, Self

import pytest

from openhands_tools_ext.gpu import hook as gpu_hook


def _make_snapshot(
    *,
    available: bool = True,
    temps: list[float] | None = None,
    utils: list[float] | None = None,
    vram_used: list[float] | None = None,
    vram_total: list[float] | None = None,
    powers: list[float] | None = None,
    cutoff: float = 83.0,
    vram_cutoff: float | None = None,
    util_cutoff: float | None = None,
    power_cutoff: float | None = None,
    include_peaks: bool = True,
) -> dict[str, Any]:
    n = max(
        len(temps or []),
        len(utils or []),
        len(vram_used or []),
        len(vram_total or []),
        len(powers or []),
    )
    gpus = []
    for i in range(n):
        gpus.append(
            {
                "index": i,
                "name": f"gpu-{i}",
                "temperature_c": (temps or [None] * n)[i],
                "utilization_pct": (utils or [None] * n)[i],
                "memory_used_mib": (vram_used or [None] * n)[i],
                "memory_total_mib": (vram_total or [None] * n)[i],
                "power_w": (powers or [None] * n)[i],
            }
        )
    snap: dict[str, Any] = {
        "available": available,
        "cutoff_c": cutoff,
        "warn_c": 52.0,
        "critical_c": 88.0,
        "vram_cutoff_pct": vram_cutoff,
        "util_cutoff_pct": util_cutoff,
        "power_cutoff_w": power_cutoff,
        "poll_sec": 2.0,
        "gpus": gpus,
        "unavailable": None if available else {"error": "no nvidia-smi"},
    }
    if include_peaks:
        temps_f = [t for t in (temps or []) if isinstance(t, (int, float))]
        utils_f = [u for u in (utils or []) if isinstance(u, (int, float))]
        powers_f = [p for p in (powers or []) if isinstance(p, (int, float))]
        vram_pct: list[float] = []
        for used, total in zip(vram_used or [], vram_total or []):
            if (
                isinstance(used, (int, float))
                and isinstance(total, (int, float))
                and total
            ):
                vram_pct.append(100.0 * used / total)
        snap["peaks"] = {
            "temperature_c": max(temps_f) if temps_f else None,
            "utilization_pct": max(utils_f) if utils_f else None,
            "vram_pct": max(vram_pct) if vram_pct else None,
            "power_w": max(powers_f) if powers_f else None,
        }
    return snap


@pytest.fixture(autouse=True)
def _stdin_stub(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))


class TestFetchSnapshot:
    def test_returns_none_on_url_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(*_a: Any, **_kw: Any) -> Any:
            raise OSError("connection refused")

        monkeypatch.setattr(gpu_hook.urllib.request, "urlopen", _raise)
        assert gpu_hook._fetch_snapshot() is None

    def test_returns_none_on_bad_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _Resp:
            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_: object) -> None: ...

            def read(self) -> bytes:
                return b"not json"

        monkeypatch.setattr(
            gpu_hook.urllib.request, "urlopen", lambda *a, **kw: _Resp()
        )
        assert gpu_hook._fetch_snapshot() is None


class TestMain:
    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        snapshot: dict[str, Any] | None,
    ) -> tuple[int, str, str]:
        monkeypatch.setattr(gpu_hook, "_fetch_snapshot", lambda: snapshot)
        rc = gpu_hook.main()
        captured = capsys.readouterr()
        return rc, captured.out, captured.err

    def test_fall_open_when_bff_unreachable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc, out, _ = self._run(monkeypatch, capsys, snapshot=None)
        assert rc == 0
        assert json.loads(out.strip())["decision"] == "allow"

    def test_fall_open_when_monitor_unavailable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc, out, _ = self._run(
            monkeypatch, capsys, snapshot=_make_snapshot(available=False)
        )
        assert rc == 0
        assert json.loads(out.strip())["decision"] == "allow"

    def test_fall_open_when_no_temp_samples(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc, out, _ = self._run(
            monkeypatch, capsys, snapshot=_make_snapshot(temps=[])
        )
        assert rc == 0
        assert json.loads(out.strip())["decision"] == "allow"

    def test_allow_below_cutoff(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc, out, _ = self._run(
            monkeypatch, capsys, snapshot=_make_snapshot(temps=[70.0, 60.0])
        )
        assert rc == 0
        payload = json.loads(out.strip())
        assert payload["decision"] == "allow"

    def test_block_at_cutoff(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc, out, err = self._run(
            monkeypatch,
            capsys,
            snapshot=_make_snapshot(temps=[83.0], cutoff=83.0),
        )
        assert rc == 2
        payload = json.loads(out.strip())
        assert payload["decision"] == "deny"
        assert payload["hottest_temperature_c"] == 83.0
        assert payload["cutoff_c"] == 83.0
        assert "GPU thermal cutoff" in err

    def test_block_above_cutoff_picks_hottest(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc, out, _ = self._run(
            monkeypatch,
            capsys,
            snapshot=_make_snapshot(temps=[70.0, 91.0, 60.0], cutoff=83.0),
        )
        assert rc == 2
        assert json.loads(out.strip())["hottest_temperature_c"] == 91.0

    def test_disabled_via_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("FORGE_GPU_HOOK_DISABLED", "1")
        # Even a hot snapshot must be ignored.
        rc, out, _ = self._run(
            monkeypatch,
            capsys,
            snapshot=_make_snapshot(temps=[95.0], cutoff=83.0),
        )
        assert rc == 0
        assert json.loads(out.strip())["decision"] == "allow"

    def test_vram_cutoff_blocks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        snap = _make_snapshot(
            temps=[60.0],
            vram_used=[31000.0],
            vram_total=[32768.0],
            vram_cutoff=90.0,  # 31000/32768 = 94.6% >= 90%
        )
        rc, out, err = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 2
        payload = json.loads(out.strip())
        assert payload["decision"] == "deny"
        assert payload["peak_vram_pct"] == pytest.approx(94.60, abs=0.05)
        assert "VRAM cutoff" in err

    def test_util_cutoff_blocks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        snap = _make_snapshot(
            temps=[70.0],
            utils=[99.0],
            util_cutoff=98.0,
        )
        rc, out, err = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 2
        payload = json.loads(out.strip())
        assert payload["peak_utilization_pct"] == 99.0
        assert "utilization cutoff" in err

    def test_thermal_beats_vram_and_util(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When multiple cutoffs would trip, thermal takes precedence."""
        snap = _make_snapshot(
            temps=[90.0],
            utils=[99.0],
            vram_used=[32000.0],
            vram_total=[32768.0],
            cutoff=83.0,
            vram_cutoff=90.0,
            util_cutoff=95.0,
        )
        rc, _, err = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 2
        assert "thermal cutoff" in err

    def test_optional_cutoffs_none_means_no_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """High VRAM/util alone must not block when their cutoffs are None."""
        snap = _make_snapshot(
            temps=[70.0],
            utils=[99.0],
            vram_used=[32000.0],
            vram_total=[32768.0],
            vram_cutoff=None,
            util_cutoff=None,
        )
        rc, out, _ = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 0
        assert json.loads(out.strip())["decision"] == "allow"

    def test_peaks_derived_when_missing_from_snapshot(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Older BFFs may omit the ``peaks`` block — hook derives it."""
        snap = _make_snapshot(
            temps=[95.0], cutoff=83.0, include_peaks=False
        )
        rc, out, _ = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 2
        assert json.loads(out.strip())["hottest_temperature_c"] == 95.0

    def test_power_cutoff_blocks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Sustained draw at/above the cutoff overheats the 5090 fast."""
        snap = _make_snapshot(
            temps=[70.0],
            powers=[440.0],
            power_cutoff=435.0,
        )
        rc, out, err = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 2
        payload = json.loads(out.strip())
        assert payload["decision"] == "deny"
        assert payload["peak_power_w"] == 440.0
        assert payload["power_cutoff_w"] == 435.0
        assert "power cutoff" in err

    def test_power_cutoff_none_means_no_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        snap = _make_snapshot(
            temps=[70.0], powers=[600.0], power_cutoff=None
        )
        rc, out, _ = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 0
        assert json.loads(out.strip())["decision"] == "allow"

    def test_thermal_beats_power(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        snap = _make_snapshot(
            temps=[90.0],
            powers=[500.0],
            cutoff=83.0,
            power_cutoff=435.0,
        )
        rc, _, err = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 2
        assert "thermal cutoff" in err

    def test_power_beats_vram(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        snap = _make_snapshot(
            temps=[70.0],
            powers=[500.0],
            vram_used=[31000.0],
            vram_total=[32768.0],
            power_cutoff=435.0,
            vram_cutoff=90.0,
        )
        rc, _, err = self._run(monkeypatch, capsys, snapshot=snap)
        assert rc == 2
        assert "power cutoff" in err
