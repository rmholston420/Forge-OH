"""Tests for bff/routers/bash.py — the live bash streaming router.

Patches `bff.routers.bash.get_client` with an httpx-like fake so we can
exercise the reshaper, error handling, and the SSE relay without needing
a live agent-server.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import bash

app = FastAPI()
app.include_router(bash.router, prefix="/api")
client = TestClient(app)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _mk_bash_command(command_id: str = "c1", command: str = "echo hi") -> dict[str, Any]:
    return {
        "id": command_id,
        "kind": "BashCommand",
        "command_id": command_id,
        "command": command,
        "cwd": "/workspace",
        "timeout": 300,
        "order": 0,
        "timestamp": "2026-08-03T10:00:00Z",
    }


def _mk_bash_output(
    command_id: str = "c1",
    order: int = 1,
    stdout: str | None = "hi\n",
    stderr: str | None = None,
    exit_code: int | None = None,
) -> dict[str, Any]:
    return {
        "id": f"o{order}",
        "kind": "BashOutput",
        "command_id": command_id,
        "order": order,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "timestamp": "2026-08-03T10:00:01Z",
    }


def _mk_response(status_code: int, json_body: Any) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        request=httpx.Request("GET", "http://upstream/"),
    )


# ---------------------------------------------------------------------------
# reshaper
# ---------------------------------------------------------------------------


class TestToEventReshaper:
    def test_bash_command_shape(self) -> None:
        out = bash._to_event(_mk_bash_command())
        assert out["kind"] == "BashCommand"
        assert out["commandId"] == "c1"
        assert out["command"] == "echo hi"
        assert out["exitCode"] is None
        assert out["order"] == 0

    def test_bash_output_shape(self) -> None:
        out = bash._to_event(_mk_bash_output(exit_code=0, stdout="ok"))
        assert out["kind"] == "BashOutput"
        assert out["stdout"] == "ok"
        assert out["exitCode"] == 0

    def test_command_id_fallback_to_id(self) -> None:
        # An event that lacks command_id should fall back to id.
        raw = {"id": "abc", "kind": "BashCommand"}
        out = bash._to_event(raw)
        assert out["commandId"] == "abc"


# ---------------------------------------------------------------------------
# start / execute
# ---------------------------------------------------------------------------


def test_start_bash_proxies_to_start_bash_command() -> None:
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=_mk_response(200, _mk_bash_command()))
    with patch.object(bash, "get_client", return_value=fake_client):
        r = client.post("/api/runs/r1/bash", json={"command": "ls"})
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["kind"] == "BashCommand"
    fake_client.post.assert_awaited_once()
    called_path, called_kwargs = fake_client.post.await_args
    assert called_path[0] == "/api/bash/start_bash_command"
    assert called_kwargs["json"]["command"] == "ls"


def test_execute_bash_proxies_to_execute_bash_command() -> None:
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(
        return_value=_mk_response(200, _mk_bash_output(exit_code=0)),
    )
    with patch.object(bash, "get_client", return_value=fake_client):
        r = client.post("/api/runs/r1/bash/execute", json={"command": "ls", "timeout": 30})
    assert r.status_code == 200
    assert r.json()["data"]["exitCode"] == 0
    called_path, called_kwargs = fake_client.post.await_args
    assert called_path[0] == "/api/bash/execute_bash_command"
    assert called_kwargs["json"]["timeout"] == 30


def test_start_bash_rejects_empty_command() -> None:
    r = client.post("/api/runs/r1/bash", json={"command": ""})
    assert r.status_code == 422


def test_start_bash_propagates_upstream_error() -> None:
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(
        return_value=httpx.Response(
            status_code=500,
            text="boom",
            request=httpx.Request("POST", "http://upstream/"),
        )
    )
    with patch.object(bash, "get_client", return_value=fake_client):
        r = client.post("/api/runs/r1/bash", json={"command": "ls"})
    assert r.status_code == 500
    assert "boom" in r.json()["detail"]


# ---------------------------------------------------------------------------
# events search
# ---------------------------------------------------------------------------


def test_list_events_passes_filters() -> None:
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        return_value=_mk_response(
            200,
            {
                "items": [_mk_bash_command(), _mk_bash_output(order=1)],
                "next_page_id": None,
            },
        ),
    )
    with patch.object(bash, "get_client", return_value=fake_client):
        r = client.get(
            "/api/runs/r1/bash/events",
            params={"command_id": "c1", "order__gt": 0, "limit": 50},
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body["data"]) == 2
    assert body["data"][0]["commandId"] == "c1"
    called_path, called_kwargs = fake_client.get.await_args
    assert called_path[0] == "/api/bash/bash_events/search"
    params = called_kwargs["params"]
    assert params["command_id__eq"] == "c1"
    assert params["order__gt"] == 0
    assert params["limit"] == 50
    assert params["sort_order"] == "asc"


def test_list_events_omits_optional_filters_when_absent() -> None:
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        return_value=_mk_response(200, {"items": [], "next_page_id": None}),
    )
    with patch.object(bash, "get_client", return_value=fake_client):
        r = client.get("/api/runs/r1/bash/events")
    assert r.status_code == 200
    _, called_kwargs = fake_client.get.await_args
    params = called_kwargs["params"]
    assert "command_id__eq" not in params
    assert "order__gt" not in params


def test_clear_events_deletes_upstream() -> None:
    fake_client = AsyncMock()
    fake_client.delete = AsyncMock(return_value=_mk_response(200, {"deleted": 3}))
    with patch.object(bash, "get_client", return_value=fake_client):
        r = client.delete("/api/runs/r1/bash/events")
    assert r.status_code == 200
    assert r.json()["data"] == {"deleted": 3}
    called_path, _ = fake_client.delete.await_args
    assert called_path[0] == "/api/bash/bash_events"


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------


def test_stream_emits_open_events_and_close_on_exit() -> None:
    """SSE relay: open → event(command) → event(output) → close on exit_code."""
    # First poll returns the command + a chunk of stdout.
    # Second poll returns the terminating BashOutput with exit_code=0.
    responses = [
        _mk_response(
            200,
            {
                "items": [
                    _mk_bash_command(),
                    _mk_bash_output(order=1, stdout="hi\n"),
                ],
                "next_page_id": None,
            },
        ),
        _mk_response(
            200,
            {
                "items": [_mk_bash_output(order=2, stdout="", exit_code=0)],
                "next_page_id": None,
            },
        ),
    ]
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(side_effect=responses)

    # Speed up the poll loop so the test doesn't sleep for real.
    with (
        patch.object(bash, "get_client", return_value=fake_client),
        patch.object(bash, "_POLL_INTERVAL_S", 0.01),
        client.stream("GET", "/api/runs/r1/bash/stream?command_id=c1&from_order=-1") as r,
    ):
        assert r.status_code == 200
        body = b"".join(r.iter_bytes())

    text = body.decode()
    assert "event: open" in text
    assert "event: event" in text
    assert "event: close" in text
    assert '"exitCode": 0' in text
    # Two polls happened.
    assert fake_client.get.await_count == 2


def test_stream_reports_upstream_error_and_continues() -> None:
    """Transient upstream error yields an SSE 'error' frame and terminates
    when the client disconnects — verified by seeing the error frame."""
    responses = [
        httpx.Response(
            status_code=502,
            text="bad gateway",
            request=httpx.Request("GET", "http://upstream/"),
        ),
        _mk_response(
            200,
            {
                "items": [_mk_bash_output(order=1, exit_code=1)],
                "next_page_id": None,
            },
        ),
    ]
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(side_effect=responses)

    with (
        patch.object(bash, "get_client", return_value=fake_client),
        patch.object(bash, "_POLL_INTERVAL_S", 0.01),
        client.stream("GET", "/api/runs/r1/bash/stream") as r,
    ):
        assert r.status_code == 200
        body = b"".join(r.iter_bytes())

    text = body.decode()
    assert "event: error" in text
    assert "event: close" in text
