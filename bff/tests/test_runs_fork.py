"""Stage 6.4 tests — POST /runs/{run_id}/fork.

The critical contract these tests defend is:

    The BFF must forward ``from_event_id`` to agent-server with THAT EXACT
    KEY NAME.  A live probe on 2026-08-06 05:53 EDT showed agent-server
    silently ignores unknown keys (``at_event_id``, ``from_event``,
    ``event_id``, ``leaf_event_id``) and returns HTTP 201 with
    ``forked_from_event_id: null`` — i.e. a full-fork masquerading as a
    revert.  Losing that key at any layer of the client stack is a silent
    correctness bug.  These tests fail loudly if that regresses.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import runs

app = FastAPI()
app.include_router(runs.router, prefix="/api")
client = TestClient(app)


def _mk_response(status_code: int, json_body: Any) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        request=httpx.Request("POST", "http://upstream/"),
    )


class _FakeUpstream:
    """Minimal stand-in for the agent-server httpx client."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def post(
        self, url: str, *, json: dict[str, Any] | None = None, **_: Any
    ) -> httpx.Response:
        # Mirror what the real client does — record the outbound JSON payload
        # so tests can assert on the exact wire-level body.
        self.calls.append((url, json or {}))
        return self._response


def _mk_ok_upstream(
    forked_id: str = "fork-1", from_event_id: str | None = None
) -> _FakeUpstream:
    body: dict[str, Any] = {"id": forked_id}
    if from_event_id is not None:
        body["forked_from_event_id"] = from_event_id
    return _FakeUpstream(_mk_response(201, body))


# ---------------------------------------------------------------------------
# Full-fork path (no body)
# ---------------------------------------------------------------------------


class TestFullFork:
    def test_no_body_full_forks_and_sends_empty_payload(self) -> None:
        fake = _mk_ok_upstream(forked_id="fork-A")
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.post("/api/runs/src-1/fork")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {
            "ok": True,
            "run_id": "src-1",
            "forked_id": "fork-A",
            "from_event_id": None,
        }
        # Wire body must be an empty dict — don't drift into sending null
        # values that a stricter agent-server release might 422 on.
        assert fake.calls == [("/api/conversations/src-1/fork", {})]

    def test_empty_body_object_is_treated_as_full_fork(self) -> None:
        fake = _mk_ok_upstream(forked_id="fork-B")
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.post("/api/runs/src-1/fork", json={})
        assert r.status_code == 200
        assert r.json()["from_event_id"] is None
        assert fake.calls == [("/api/conversations/src-1/fork", {})]

    def test_null_from_event_id_is_treated_as_full_fork(self) -> None:
        fake = _mk_ok_upstream(forked_id="fork-C")
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.post("/api/runs/src-1/fork", json={"from_event_id": None})
        assert r.status_code == 200
        assert r.json()["from_event_id"] is None
        # None must NOT be forwarded — agent-server treats missing == full fork.
        assert fake.calls == [("/api/conversations/src-1/fork", {})]


# ---------------------------------------------------------------------------
# Fork-from-here path (with from_event_id)
# ---------------------------------------------------------------------------


class TestForkFromEvent:
    def test_from_event_id_is_forwarded_with_exact_wire_key(self) -> None:
        """Regression against silent-full-fork.

        Wire key MUST be ``from_event_id``.  This is the single most
        important test in this file — it defends the contract discovered
        in the 2026-08-06 05:53 EDT live agent-server probe.
        """
        fake = _mk_ok_upstream(forked_id="fork-D", from_event_id="ev-42")
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.post(
                "/api/runs/src-1/fork",
                json={"from_event_id": "ev-42"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {
            "ok": True,
            "run_id": "src-1",
            "forked_id": "fork-D",
            "from_event_id": "ev-42",
        }
        # THE contract assertion — exact wire body, exact key spelling.
        assert fake.calls == [
            ("/api/conversations/src-1/fork", {"from_event_id": "ev-42"})
        ]

    def test_alias_keys_are_not_forwarded_as_from_event_id(self) -> None:
        """Client-side guard against silent-full-fork via alias keys.

        Pydantic ignores extras by default, which is the correct behavior
        here — the important guarantee is that ``at_event_id`` etc. do
        NOT reach agent-server as ``from_event_id``.
        """
        fake = _mk_ok_upstream()
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.post(
                "/api/runs/src-1/fork",
                json={"at_event_id": "ev-42"},
            )
        # 200 is fine as long as it was a full-fork (documented behavior).
        assert r.status_code == 200
        assert r.json()["from_event_id"] is None
        # Wire payload must be empty — the alias key must NOT be forwarded.
        assert fake.calls == [("/api/conversations/src-1/fork", {})]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestForkErrors:
    def test_upstream_404_is_surfaced_as_404(self) -> None:
        fake = _FakeUpstream(_mk_response(404, {"detail": "not found"}))
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.post("/api/runs/nonexistent/fork")
        assert r.status_code == 404

    def test_upstream_400_on_unknown_from_event_id_becomes_400(self) -> None:
        fake = _FakeUpstream(
            _mk_response(400, {"detail": "unknown from_event_id 'ev-bad'"})
        )
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.post(
                "/api/runs/src-1/fork",
                json={"from_event_id": "ev-bad"},
            )
        assert r.status_code == 400
        assert "from_event_id" in r.json()["detail"]
        assert "ev-bad" in r.json()["detail"]

    def test_upstream_network_error_becomes_502(self) -> None:
        class _Bomb:
            async def post(self, *a: Any, **kw: Any) -> httpx.Response:
                raise httpx.ConnectError("connection refused")

        with patch("bff.routers.runs.get_client", return_value=_Bomb()):
            r = client.post("/api/runs/src-1/fork")
        assert r.status_code == 502

    def test_upstream_response_missing_id_becomes_502(self) -> None:
        fake = _FakeUpstream(_mk_response(201, {"something_else": "x"}))
        with patch("bff.routers.runs.get_client", return_value=fake):
            r = client.post("/api/runs/src-1/fork")
        assert r.status_code == 502
        assert "missing id" in r.json()["detail"]


# Silence flake8's F401 on AsyncMock — kept in imports for future extension
# (currently unused because _FakeUpstream is sync-friendly with async def).
_ = AsyncMock
