"""Stage 6.4b step 2 tests \u2014 worktree wiring in bff.routers.runs.

Covers:
  * DELETE /runs/{id} happy path: fetches conv, deletes on agent-server,
    reaps the worktree whose name we recovered from working_dir.
  * DELETE /runs/{id} skips reap when working_dir isn't a managed
    worktree (doesn't start with "run-").
  * DELETE /runs/{id} still succeeds when agent-server delete 409/404s.
  * DELETE /runs/{id} 404 propagates when the run doesn't exist.
  * DELETE /runs/{id} 502 propagates on agent-server unreachable.
  * DELETE /runs/{id} tolerates worktree reap failure (logs, still 204).

Uses the _FakeUpstream pattern from test_runs_fork.py so the test
suite doesn't need a live agent-server.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import runs

app = FastAPI()
app.include_router(runs.router, prefix="/api")
client = TestClient(app)


def _mk_response(status_code: int, json_body: Any = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body if json_body is not None else {},
        request=httpx.Request("DELETE", "http://upstream/"),
    )


class _FakeAgentServer:
    """Records GET + DELETE calls; returns queued responses."""

    def __init__(self, get_resp: httpx.Response, delete_resp: httpx.Response) -> None:
        self._get_resp = get_resp
        self._delete_resp = delete_resp
        self.get_calls: list[str] = []
        self.delete_calls: list[str] = []

    async def get(self, url: str, **_: Any) -> httpx.Response:
        self.get_calls.append(url)
        return self._get_resp

    async def delete(self, url: str, **_: Any) -> httpx.Response:
        self.delete_calls.append(url)
        return self._delete_resp


def _conv_json(working_dir: str, cid: str = "cid-1") -> dict[str, Any]:
    return {
        "id": cid,
        "workspace": {"working_dir": working_dir, "kind": "LocalWorkspace"},
        "execution_status": "idle",
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestDeleteRunHappyPath:
    def test_reaps_worktree_when_working_dir_is_managed(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """working_dir last segment starts with 'run-' \u2192 reap."""
        reaped: list[tuple[str, bool]] = []

        def _fake_remove(run_id: str, *, missing_ok: bool = False) -> None:
            reaped.append((run_id, missing_ok))

        monkeypatch.setattr(runs, "remove_worktree", _fake_remove)

        fake = _FakeAgentServer(
            get_resp=_mk_response(
                200,
                _conv_json(working_dir="/tmp/wt/run-abc123def456"),
            ),
            delete_resp=_mk_response(204),
        )
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.delete("/api/runs/cid-1")

        assert r.status_code == 204, r.text
        assert fake.get_calls == ["/api/conversations/cid-1"]
        assert fake.delete_calls == ["/api/conversations/cid-1"]
        assert reaped == [("run-abc123def456", True)]

    def test_skips_reap_when_working_dir_is_not_managed(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A workspace dir like /workspaces/foo (no 'run-' prefix) is
        left alone \u2014 we never touched it."""
        reaped: list[str] = []
        monkeypatch.setattr(
            runs, "remove_worktree",
            lambda run_id, **_: reaped.append(run_id),
        )
        fake = _FakeAgentServer(
            get_resp=_mk_response(
                200, _conv_json(working_dir="/workspaces/plain"),
            ),
            delete_resp=_mk_response(204),
        )
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.delete("/api/runs/cid-1")

        assert r.status_code == 204
        assert reaped == []  # remove_worktree must NOT be called

    def test_skips_reap_when_working_dir_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        reaped: list[str] = []
        monkeypatch.setattr(
            runs, "remove_worktree",
            lambda run_id, **_: reaped.append(run_id),
        )
        fake = _FakeAgentServer(
            get_resp=_mk_response(200, {"id": "cid-1", "workspace": {}}),
            delete_resp=_mk_response(204),
        )
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.delete("/api/runs/cid-1")

        assert r.status_code == 204
        assert reaped == []


# ---------------------------------------------------------------------------
# Idempotency + failure tolerance
# ---------------------------------------------------------------------------


class TestDeleteRunIdempotency:
    def test_agent_server_delete_returning_404_still_reaps_worktree(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """agent-server says 'already gone' \u2192 we still clean up."""
        reaped: list[str] = []
        monkeypatch.setattr(
            runs, "remove_worktree",
            lambda run_id, **_: reaped.append(run_id),
        )
        fake = _FakeAgentServer(
            get_resp=_mk_response(200, _conv_json("/tmp/wt/run-orphan01ab")),
            delete_resp=_mk_response(404),
        )
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.delete("/api/runs/cid-1")
        assert r.status_code == 204
        assert reaped == ["run-orphan01ab"]

    def test_worktree_reap_failure_does_not_fail_the_request(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A stray worktree that can't be removed logs and is left for GC."""
        def _boom(_run_id: str, **_: Any) -> None:
            raise RuntimeError("filesystem died")

        monkeypatch.setattr(runs, "remove_worktree", _boom)
        fake = _FakeAgentServer(
            get_resp=_mk_response(200, _conv_json("/tmp/wt/run-cannotrm00")),
            delete_resp=_mk_response(204),
        )
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.delete("/api/runs/cid-1")

        assert r.status_code == 204  # still succeeds


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestDeleteRunErrors:
    def test_404_when_conversation_not_found(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        reaped: list[str] = []
        monkeypatch.setattr(
            runs, "remove_worktree",
            lambda run_id, **_: reaped.append(run_id),
        )
        fake = _FakeAgentServer(
            get_resp=_mk_response(404),
            delete_resp=_mk_response(204),
        )
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.delete("/api/runs/does-not-exist")
        assert r.status_code == 404
        # Never called agent-server delete, never reaped.
        assert fake.delete_calls == []
        assert reaped == []

    def test_502_when_agent_server_unreachable_on_get(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class _Bomb:
            async def get(self, *_: Any, **__: Any) -> httpx.Response:
                raise httpx.ConnectError("agent-server down")

            async def delete(self, *_: Any, **__: Any) -> httpx.Response:
                raise AssertionError("should not be called")

        reaped: list[str] = []
        monkeypatch.setattr(
            runs, "remove_worktree",
            lambda run_id, **_: reaped.append(run_id),
        )
        with patch("bff.routers.runs.get_client", return_value=_Bomb()):
            r = client.delete("/api/runs/cid-1")
        assert r.status_code == 502
        assert reaped == []
