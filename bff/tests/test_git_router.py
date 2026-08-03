"""Tests for bff/routers/git.py — the real-git-diff proxy router."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import git

app = FastAPI()
app.include_router(git.router, prefix="/api")
client = TestClient(app)


def _mk_response(status_code: int, json_body: Any) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        request=httpx.Request("GET", "http://upstream/"),
    )


# ---------------------------------------------------------------------------
# _encode_path
# ---------------------------------------------------------------------------


class TestEncodePath:
    def test_keeps_slashes(self) -> None:
        assert git._encode_path("/workspace/runs/pending") == "/workspace/runs/pending"

    def test_encodes_spaces_and_specials(self) -> None:
        assert git._encode_path("/tmp/a b/c#d") == "/tmp/a%20b/c%23d"


# ---------------------------------------------------------------------------
# /changes
# ---------------------------------------------------------------------------


def test_changes_proxies_and_normalises_status() -> None:
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        return_value=_mk_response(
            200,
            [
                {"status": "MODIFIED", "path": "src/a.py"},
                {"status": "added", "path": "src/b.py"},
            ],
        )
    )
    with patch.object(git, "get_client", return_value=fake_client):
        r = client.get(
            "/api/runs/r1/git/changes",
            params={"workspace_path": "/workspace/runs/pending"},
        )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data == [
        {"status": "modified", "path": "src/a.py"},
        {"status": "added", "path": "src/b.py"},
    ]
    called_path, _ = fake_client.get.await_args
    assert called_path[0] == "/api/git/changes/%2Fworkspace%2Fruns%2Fpending" or (
        called_path[0] == "/api/git/changes//workspace/runs/pending"
    )


def test_changes_requires_workspace_path() -> None:
    r = client.get("/api/runs/r1/git/changes")
    assert r.status_code == 422


def test_changes_propagates_upstream_error() -> None:
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        return_value=httpx.Response(
            status_code=404,
            text="not a git repo",
            request=httpx.Request("GET", "http://upstream/"),
        )
    )
    with patch.object(git, "get_client", return_value=fake_client):
        r = client.get("/api/runs/r1/git/changes", params={"workspace_path": "/nope"})
    assert r.status_code == 404
    assert "not a git repo" in r.json()["detail"]


# ---------------------------------------------------------------------------
# /diff
# ---------------------------------------------------------------------------


def test_diff_absolute_path_passes_through() -> None:
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        return_value=_mk_response(200, {"original": "old\n", "modified": "new\n"})
    )
    with patch.object(git, "get_client", return_value=fake_client):
        r = client.get(
            "/api/runs/r1/git/diff",
            params={"file_path": "/workspace/runs/pending/src/a.py"},
        )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body == {
        "path": "/workspace/runs/pending/src/a.py",
        "original": "old\n",
        "modified": "new\n",
    }
    called_path, _ = fake_client.get.await_args
    assert "src/a.py" in called_path[0]
    assert called_path[0].startswith("/api/git/diff/")


def test_diff_joins_relative_path_with_workspace_root() -> None:
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        return_value=_mk_response(200, {"original": None, "modified": "hi\n"})
    )
    with patch.object(git, "get_client", return_value=fake_client):
        r = client.get(
            "/api/runs/r1/git/diff",
            params={
                "file_path": "src/a.py",
                "workspace_path": "/workspace/runs/pending",
            },
        )
    assert r.status_code == 200
    called_path, _ = fake_client.get.await_args
    # The two path parts must appear joined by exactly one slash.
    assert "workspace/runs/pending/src/a.py" in called_path[0].replace("%2F", "/")


def test_diff_trims_double_slashes_when_joining() -> None:
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=_mk_response(200, {"original": "", "modified": ""}))
    with patch.object(git, "get_client", return_value=fake_client):
        client.get(
            "/api/runs/r1/git/diff",
            params={"file_path": "/src/a.py", "workspace_path": "/ws/"},
        )
    # workspace_path ends with /, file_path starts with / after strip — must not double up
    called_path, _ = fake_client.get.await_args
    joined = called_path[0].replace("%2F", "/")
    assert "//src" not in joined
    assert "/ws/src/a.py" in joined


def test_diff_returns_null_sides_verbatim() -> None:
    """Deleted files return {original: <text>, modified: null} — we must
    surface that faithfully so the frontend can render 'deleted'."""
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        return_value=_mk_response(200, {"original": "goodbye\n", "modified": None})
    )
    with patch.object(git, "get_client", return_value=fake_client):
        r = client.get("/api/runs/r1/git/diff", params={"file_path": "/x/y.py"})
    assert r.status_code == 200
    assert r.json()["data"]["modified"] is None
    assert r.json()["data"]["original"] == "goodbye\n"
