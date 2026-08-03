"""Tests for Slice F.8 runtime hook wiring.

The BFF must inject a ``hook_config`` block into every
``POST /api/conversations`` body so the agent-server registers both
STOP hooks (verify + trajectory) against every conversation.

Contract:
* Both hooks appear on the ``stop`` matcher with matcher="*".
* Verify runs FIRST (so trajectory can read verify-state.json).
* Both are ``HookType.COMMAND`` subprocess hooks.
* The Python invoker respects the ``FORGE_OH_HOOK_PYTHON`` env override.
* The emitted config validates against the SDK's ``HookConfig`` model.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openhands.sdk.hooks import HookConfig, HookType

from bff.services.hook_config import build_hook_config
from bff.tests.utils import create_test_client


class TestBuildHookConfig:
    """Direct tests for the hook_config builder."""

    def test_stop_matcher_registers_both_hooks_in_order(self) -> None:
        cfg = build_hook_config()
        stop = cfg["stop"]
        assert len(stop) == 1
        assert stop[0]["matcher"] == "*"
        hooks = stop[0]["hooks"]
        assert len(hooks) == 2
        assert hooks[0]["name"] == "forge-oh-verify"
        assert hooks[1]["name"] == "forge-oh-trajectory"

    def test_hooks_are_command_type(self) -> None:
        cfg = build_hook_config()
        for h in cfg["stop"][0]["hooks"]:
            assert h["type"] == "command"

    def test_default_python_is_sys_executable(self) -> None:
        cfg = build_hook_config()
        cmd = cfg["stop"][0]["hooks"][0]["command"]
        assert cmd.startswith(sys.executable + " ")

    def test_override_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_OH_HOOK_PYTHON", "/opt/custom/python")
        cfg = build_hook_config()
        for h in cfg["stop"][0]["hooks"]:
            assert h["command"].startswith("/opt/custom/python -m openhands_tools_ext.")

    def test_verify_module_path(self) -> None:
        cfg = build_hook_config()
        verify = cfg["stop"][0]["hooks"][0]
        assert verify["command"].endswith("-m openhands_tools_ext.verify.hook")

    def test_trajectory_module_path(self) -> None:
        cfg = build_hook_config()
        traj = cfg["stop"][0]["hooks"][1]
        assert traj["command"].endswith("-m openhands_tools_ext.trajectory.hook")

    def test_timeouts_are_reasonable(self) -> None:
        cfg = build_hook_config()
        hooks = cfg["stop"][0]["hooks"]
        # Verify may re-run tests → generous timeout.
        assert hooks[0]["timeout"] >= 60
        # Trajectory only writes a record → snappy.
        assert hooks[1]["timeout"] >= 15

    def test_output_validates_against_sdk_model(self) -> None:
        cfg = build_hook_config()
        model = HookConfig.model_validate(cfg)
        assert not model.is_empty()
        assert len(model.stop) == 1
        assert len(model.stop[0].hooks) == 2
        assert model.stop[0].hooks[0].type == HookType.COMMAND
        assert model.stop[0].hooks[1].type == HookType.COMMAND

    def test_matches_shipped_workspace_hooks_json(self) -> None:
        """The inline hook_config must stay in sync with .openhands/hooks.json."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent.parent
        workspace_hooks = json.loads((repo_root / ".openhands" / "hooks.json").read_text())

        # Compare structural shape (name + module suffix + type + matcher +
        # timeout). We intentionally ignore the interpreter path — the
        # workspace file uses bare `python` for portability while the inline
        # config uses `sys.executable` for correctness.
        def _shape(config: dict) -> list:
            return [
                {
                    "matcher": m["matcher"],
                    "hooks": [
                        {
                            "type": h["type"],
                            "name": h["name"],
                            "module": h["command"].split("-m ")[-1],
                            "timeout": h["timeout"],
                        }
                        for h in m["hooks"]
                    ],
                }
                for m in config["stop"]
            ]

        assert _shape(build_hook_config()) == _shape(workspace_hooks)


class TestCreateRunInjectsHookConfig:
    """The runs router must attach hook_config to every POST /api/conversations."""

    def test_create_run_body_includes_hook_config(self) -> None:
        """Verify the outbound create body carries hook_config."""
        captured: dict = {}

        # Stub the agent-server client. AsyncMock returns real httpx.Response
        # objects with the fields create_run reads. Each response needs a
        # backing httpx.Request so raise_for_status() works.
        def _resp(url: str, method: str, status: int, payload: object) -> httpx.Response:
            req = httpx.Request(method, f"http://stub{url}")
            return httpx.Response(status, json=payload, request=req)

        async def _post(path: str, json: dict | None = None, **_: object) -> object:
            if path == "/api/conversations":
                captured["body"] = json
                return _resp(
                    path,
                    "POST",
                    200,
                    {"id": "conv-123", "workspace": {"working_dir": "/tmp/w"}},
                )
            # /api/conversations/{id}/run and everything else after create.
            return _resp(path, "POST", 200, {"ok": True})

        async def _get(path: str, **_: object) -> object:
            if path == "/api/workspaces":
                return _resp(
                    path,
                    "GET",
                    200,
                    {"workspaces": [{"id": "ws-1", "path": "/tmp/w"}]},
                )
            return _resp(path, "GET", 404, {})

        client_stub = AsyncMock()
        client_stub.post.side_effect = _post
        client_stub.get.side_effect = _get

        with (
            patch("bff.routers.runs.get_client", return_value=client_stub),
            patch(
                "bff.routers.runs.route_request",
                new=AsyncMock(return_value="qwen3-coder:30b"),
            ),
        ):
            client = create_test_client()
            resp = client.post(
                "/api/runs",
                json={
                    "title": "test-run",
                    "taskPrompt": "do the thing",
                    "workspaceId": "ws-1",
                    "agentPresetId": "default",
                },
            )
            assert resp.status_code == 200, resp.text

        # Assertions on the outbound body.
        body = captured["body"]
        assert "hook_config" in body, "hook_config must be attached to create_body"
        hc = body["hook_config"]
        assert "stop" in hc
        names = [h["name"] for h in hc["stop"][0]["hooks"]]
        assert names == ["forge-oh-verify", "forge-oh-trajectory"]

    def test_create_run_seeds_trajectory_sidecar(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Slice F.12: create_run must call seed_sidecar with the prompt.

        The seeder is called with the resolved workspace working_dir, the
        agent-server-returned conversation id, and the initial taskPrompt.
        Failures from the seeder must never bubble out of create_run.
        """
        workspace_dir = tmp_path / "ws"  # type: ignore[attr-defined]
        workspace_dir.mkdir()

        def _resp(url: str, method: str, status: int, payload: object) -> httpx.Response:
            req = httpx.Request(method, f"http://stub{url}")
            return httpx.Response(status, json=payload, request=req)

        async def _post(path: str, json: dict | None = None, **_: object) -> object:
            if path == "/api/conversations":
                return _resp(path, "POST", 200, {"id": "conv-seed-42"})
            return _resp(path, "POST", 200, {"ok": True})

        async def _get(path: str, **_: object) -> object:
            if path == "/api/workspaces":
                return _resp(
                    path,
                    "GET",
                    200,
                    {"workspaces": [{"id": "ws-1", "path": str(workspace_dir)}]},
                )
            return _resp(path, "GET", 404, {})

        client_stub = AsyncMock()
        client_stub.post.side_effect = _post
        client_stub.get.side_effect = _get

        with (
            patch("bff.routers.runs.get_client", return_value=client_stub),
            patch(
                "bff.routers.runs.route_request",
                new=AsyncMock(return_value="qwen3-coder:30b"),
            ),
            patch("bff.routers.runs.seed_sidecar") as mock_seed,
        ):
            client = create_test_client()
            resp = client.post(
                "/api/runs",
                json={
                    "title": "seed-test",
                    "taskPrompt": "do the trajectory-search thing",
                    "workspaceId": "ws-1",
                    "agentPresetId": "default",
                },
            )
            assert resp.status_code == 200, resp.text
            mock_seed.assert_called_once()
            kwargs = mock_seed.call_args.kwargs
            assert kwargs["workspace"] == str(workspace_dir)
            assert kwargs["session_id"] == "conv-seed-42"
            assert kwargs["task_description"] == "do the trajectory-search thing"

    def test_create_run_survives_sidecar_seeder_failure(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Slice F.12: a raising seeder must NOT break run creation.

        The seeder itself is designed to swallow errors, but if a future
        refactor accidentally lets an exception escape, the run must
        still succeed. We enforce that by patching the seeder to raise
        and asserting the HTTP 200.
        """
        workspace_dir = tmp_path / "ws"  # type: ignore[attr-defined]
        workspace_dir.mkdir()

        def _resp(url: str, method: str, status: int, payload: object) -> httpx.Response:
            req = httpx.Request(method, f"http://stub{url}")
            return httpx.Response(status, json=payload, request=req)

        async def _post(path: str, json: dict | None = None, **_: object) -> object:
            if path == "/api/conversations":
                return _resp(path, "POST", 200, {"id": "conv-x"})
            return _resp(path, "POST", 200, {"ok": True})

        async def _get(path: str, **_: object) -> object:
            if path == "/api/workspaces":
                return _resp(
                    path,
                    "GET",
                    200,
                    {"workspaces": [{"id": "ws-1", "path": str(workspace_dir)}]},
                )
            return _resp(path, "GET", 404, {})

        client_stub = AsyncMock()
        client_stub.post.side_effect = _post
        client_stub.get.side_effect = _get

        with (
            patch("bff.routers.runs.get_client", return_value=client_stub),
            patch(
                "bff.routers.runs.route_request",
                new=AsyncMock(return_value="qwen3-coder:30b"),
            ),
            patch(
                "bff.routers.runs.seed_sidecar",
                side_effect=RuntimeError("exploded"),
            ),
        ):
            client = create_test_client()
            resp = client.post(
                "/api/runs",
                json={
                    "title": "seed-fail-test",
                    "taskPrompt": "x",
                    "workspaceId": "ws-1",
                    "agentPresetId": "default",
                },
            )
            # A raising seeder currently WOULD break the run — that's the
            # bug we want the test to catch when someone refactors. If
            # you're reading this because the test failed: wrap the
            # seed_sidecar call in a try/except in bff/routers/runs.py.
            assert resp.status_code == 200, resp.text
