"""Stage 6.4c step 1c tests — ADR-026 §Storage capture-point wiring.

Covers the runs router's four sha-related touch-points:

  1. ``create_run``: after ``POST /api/conversations`` succeeds, the router
     does a follow-up ``GET /events?limit=1`` to find the initial user
     MessageEvent id, then stamps ``commit_sha_at_time_of_event`` via
     ``event_commit_ledger.record_sha`` using the worktree's HEAD sha.

  2. ``send_run_message``: after ``POST /events`` succeeds, the router
     does a follow-up ``GET /events?limit=1&sort_order=CREATED_AT_DESC``
     to find the just-created user MessageEvent id and stamps its sha.

  3. ``delete_run``: after the worktree is reaped, the router calls
     ``event_commit_ledger.delete_run(app, run_id)`` to cascade-purge
     every ledger row for that run.

  4. ``get_run_events``: hydrates ``sha_lookup=sha_map.get`` via
     ``event_commit_ledger.bulk_get_shas`` and threads it through
     ``normalize_events`` so wire events carry
     ``commit_sha_at_time_of_event`` when a row exists.

Every capture point is best-effort — a failing ledger call must never
break the underlying operation (run create, message send, run delete,
events read).  These tests defend both the happy paths and the
graceful-downgrade contract.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import runs


# ---------------------------------------------------------------------------
# Fake upstream client
# ---------------------------------------------------------------------------


def _mk_response(status_code: int, json_body: Any) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        request=httpx.Request("GET", "http://upstream/"),
    )


class _FakeUpstream:
    """Route-aware fake for agent-server.

    Matches on longest-substring first so more-specific patterns
    (``/events/search``) win over their shorter parents
    (``/api/conversations/run-1``).  Unmocked routes 404 loudly.
    """

    def __init__(self) -> None:
        self._get_handlers: list[tuple[str, httpx.Response]] = []
        self._post_handlers: list[tuple[str, httpx.Response]] = []
        self._delete_handlers: list[tuple[str, httpx.Response]] = []
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def on_get(self, suffix: str, resp: httpx.Response) -> None:
        self._get_handlers.append((suffix, resp))

    def on_post(self, suffix: str, resp: httpx.Response) -> None:
        self._post_handlers.append((suffix, resp))

    def on_delete(self, suffix: str, resp: httpx.Response) -> None:
        self._delete_handlers.append((suffix, resp))

    def _match(
        self, url: str, table: list[tuple[str, httpx.Response]]
    ) -> httpx.Response:
        # Sort by suffix length descending so the most specific pattern
        # wins even when a shorter one is a strict prefix.
        matches = [
            (pat, resp) for pat, resp in table if pat in url
        ]
        if not matches:
            return _mk_response(404, {"detail": f"unmocked {url}"})
        matches.sort(key=lambda pair: len(pair[0]), reverse=True)
        return matches[0][1]

    async def get(
        self, url: str, *, params: dict[str, Any] | None = None, **_: Any
    ) -> httpx.Response:
        self.calls.append(("GET", url, params or {}))
        return self._match(url, self._get_handlers)

    async def post(
        self, url: str, *, json: dict[str, Any] | None = None, **_: Any
    ) -> httpx.Response:
        self.calls.append(("POST", url, json or {}))
        return self._match(url, self._post_handlers)

    async def delete(self, url: str, **_: Any) -> httpx.Response:
        self.calls.append(("DELETE", url, {}))
        return self._match(url, self._delete_handlers)


def _build_app_with_ledger_ready(ready: bool = True) -> FastAPI:
    """FastAPI app with (optionally) a truthy event_commit_db sentinel."""
    app = FastAPI()
    app.include_router(runs.router, prefix="/api")
    if ready:
        app.state.event_commit_db = object()  # any truthy sentinel
    return app


# ---------------------------------------------------------------------------
# 1. create_run capture path
# ---------------------------------------------------------------------------


class TestCreateRunCapturesSha:
    """POST /runs — initial user MessageEvent sha capture."""

    def _base_create_resp(self) -> httpx.Response:
        return _mk_response(
            200,
            {
                "id": "conv-1",
                "created_at": "2026-08-06T12:00:00Z",
                "workspace": {"working_dir": "/tmp/fake-wd"},
                "title": "t",
            },
        )

    def _wire_common_mocks(
        self,
        upstream: _FakeUpstream,
        *,
        events_body: Any,
    ) -> None:
        # Create conversation → success.
        upstream.on_post("/api/conversations", self._base_create_resp())
        # SecurityAnalyzer POST → success.
        upstream.on_post("/security_analyzer", _mk_response(200, {}))
        # confirmation_policy POST → success.
        upstream.on_post("/confirmation_policy", _mk_response(200, {}))
        # /run kickoff → success.
        upstream.on_post("/api/conversations/conv-1/run", _mk_response(200, {}))
        # Follow-up GET on /events/search → provides initial event.
        upstream.on_get("/events/search", _mk_response(200, events_body))

    def test_initial_user_message_stamped(self) -> None:
        upstream = _FakeUpstream()
        self._wire_common_mocks(
            upstream,
            events_body={
                "items": [
                    {
                        "id": "ev-init-1",
                        "kind": "MessageEvent",
                        "source": "user",
                    }
                ]
            },
        )
        record = AsyncMock()
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.provision_worktree",
                 return_value=type("W", (), {"path": "/tmp/fake-wd"})(),
             ), \
             patch("bff.routers.runs.head_sha", return_value="a" * 40), \
             patch("bff.routers.runs.seed_sidecar"), \
             patch("bff.routers.runs.start_relay"), \
             patch("bff.routers.runs.route_by_role") as mock_route, \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            mock_route.return_value = type(
                "R",
                (),
                {
                    "base_url": "http://x",
                    "backend": "ollama",
                    "max_tokens": 2048,
                    "model": "m",
                    "tagged": "ok",
                },
            )()
            r = cli.post(
                "/api/runs",
                json={
                    "title": "t",
                    "taskPrompt": "hi",
                    "workspaceId": "ws-1",
                    "agentPresetId": "ap-1",
                },
            )
        assert r.status_code == 200, r.text
        record.assert_awaited_once()
        kwargs = record.await_args.kwargs
        assert kwargs["run_id"] == "conv-1"
        assert kwargs["event_id"] == "ev-init-1"
        assert kwargs["commit_sha"] == "a" * 40

    def test_no_worktree_provisioned_skips_capture(self) -> None:
        upstream = _FakeUpstream()
        self._wire_common_mocks(
            upstream,
            events_body={"items": [{"id": "ev-1", "kind": "MessageEvent", "source": "user"}]},
        )
        record = AsyncMock()
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        # provision_worktree raises → worktree_provisioned stays None.
        from bff.services.worktree import WorktreeError

        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.provision_worktree",
                 side_effect=WorktreeError("no git"),
             ), \
             patch("bff.routers.runs.head_sha", return_value="a" * 40), \
             patch("bff.routers.runs.seed_sidecar"), \
             patch("bff.routers.runs.start_relay"), \
             patch("bff.routers.runs.route_by_role") as mock_route, \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            mock_route.return_value = type(
                "R",
                (),
                {
                    "base_url": "http://x",
                    "backend": "ollama",
                    "max_tokens": 2048,
                    "model": "m",
                    "tagged": "ok",
                },
            )()
            r = cli.post(
                "/api/runs",
                json={
                    "title": "t",
                    "taskPrompt": "hi",
                    "workspaceId": "ws-1",
                    "agentPresetId": "ap-1",
                },
            )
        assert r.status_code == 200
        record.assert_not_awaited()

    def test_ledger_unavailable_downgrades_silently(self) -> None:
        upstream = _FakeUpstream()
        self._wire_common_mocks(
            upstream,
            events_body={"items": [{"id": "ev-1", "kind": "MessageEvent", "source": "user"}]},
        )
        record = AsyncMock()
        app = _build_app_with_ledger_ready(ready=False)
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.provision_worktree",
                 return_value=type("W", (), {"path": "/tmp/fake-wd"})(),
             ), \
             patch("bff.routers.runs.head_sha", return_value="a" * 40), \
             patch("bff.routers.runs.seed_sidecar"), \
             patch("bff.routers.runs.start_relay"), \
             patch("bff.routers.runs.route_by_role") as mock_route, \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            mock_route.return_value = type(
                "R",
                (),
                {
                    "base_url": "http://x",
                    "backend": "ollama",
                    "max_tokens": 2048,
                    "model": "m",
                    "tagged": "ok",
                },
            )()
            r = cli.post(
                "/api/runs",
                json={
                    "title": "t",
                    "taskPrompt": "hi",
                    "workspaceId": "ws-1",
                    "agentPresetId": "ap-1",
                },
            )
        assert r.status_code == 200
        record.assert_not_awaited()

    def test_head_sha_none_skips_record(self) -> None:
        upstream = _FakeUpstream()
        self._wire_common_mocks(
            upstream,
            events_body={"items": [{"id": "ev-1", "kind": "MessageEvent", "source": "user"}]},
        )
        record = AsyncMock()
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.provision_worktree",
                 return_value=type("W", (), {"path": "/tmp/fake-wd"})(),
             ), \
             patch("bff.routers.runs.head_sha", return_value=None), \
             patch("bff.routers.runs.seed_sidecar"), \
             patch("bff.routers.runs.start_relay"), \
             patch("bff.routers.runs.route_by_role") as mock_route, \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            mock_route.return_value = type(
                "R",
                (),
                {
                    "base_url": "http://x",
                    "backend": "ollama",
                    "max_tokens": 2048,
                    "model": "m",
                    "tagged": "ok",
                },
            )()
            r = cli.post(
                "/api/runs",
                json={
                    "title": "t",
                    "taskPrompt": "hi",
                    "workspaceId": "ws-1",
                    "agentPresetId": "ap-1",
                },
            )
        assert r.status_code == 200
        record.assert_not_awaited()

    def test_assistant_first_event_skips_record(self) -> None:
        """Guard: if the first event isn't a user MessageEvent, don't capture."""
        upstream = _FakeUpstream()
        self._wire_common_mocks(
            upstream,
            events_body={"items": [{"id": "ev-1", "kind": "MessageEvent", "source": "agent"}]},
        )
        record = AsyncMock()
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.provision_worktree",
                 return_value=type("W", (), {"path": "/tmp/fake-wd"})(),
             ), \
             patch("bff.routers.runs.head_sha", return_value="a" * 40), \
             patch("bff.routers.runs.seed_sidecar"), \
             patch("bff.routers.runs.start_relay"), \
             patch("bff.routers.runs.route_by_role") as mock_route, \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            mock_route.return_value = type(
                "R",
                (),
                {
                    "base_url": "http://x",
                    "backend": "ollama",
                    "max_tokens": 2048,
                    "model": "m",
                    "tagged": "ok",
                },
            )()
            r = cli.post(
                "/api/runs",
                json={
                    "title": "t",
                    "taskPrompt": "hi",
                    "workspaceId": "ws-1",
                    "agentPresetId": "ap-1",
                },
            )
        assert r.status_code == 200
        record.assert_not_awaited()

    def test_record_sha_raises_does_not_fail_create(self) -> None:
        """Defensive: a ledger insert exception must not break run creation."""
        upstream = _FakeUpstream()
        self._wire_common_mocks(
            upstream,
            events_body={"items": [{"id": "ev-1", "kind": "MessageEvent", "source": "user"}]},
        )
        record = AsyncMock(side_effect=RuntimeError("boom"))
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.provision_worktree",
                 return_value=type("W", (), {"path": "/tmp/fake-wd"})(),
             ), \
             patch("bff.routers.runs.head_sha", return_value="a" * 40), \
             patch("bff.routers.runs.seed_sidecar"), \
             patch("bff.routers.runs.start_relay"), \
             patch("bff.routers.runs.route_by_role") as mock_route, \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            mock_route.return_value = type(
                "R",
                (),
                {
                    "base_url": "http://x",
                    "backend": "ollama",
                    "max_tokens": 2048,
                    "model": "m",
                    "tagged": "ok",
                },
            )()
            r = cli.post(
                "/api/runs",
                json={
                    "title": "t",
                    "taskPrompt": "hi",
                    "workspaceId": "ws-1",
                    "agentPresetId": "ap-1",
                },
            )
        # 200 despite the ledger blowup — defensive catch worked.
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 2. send_run_message capture path
# ---------------------------------------------------------------------------


class TestSendRunMessageCapturesSha:
    """POST /runs/{id}/message — follow-up sha capture on newest event."""

    def test_new_user_message_stamped(self) -> None:
        upstream = _FakeUpstream()
        upstream.on_post("/events", _mk_response(200, {"success": True}))
        upstream.on_get(
            "/api/conversations/run-1",
            _mk_response(200, {"workspace": {"working_dir": "/tmp/wd"}}),
        )
        upstream.on_get(
            "/events/search",
            _mk_response(
                200,
                {
                    "items": [
                        {"id": "ev-new-1", "kind": "MessageEvent", "source": "user"}
                    ]
                },
            ),
        )
        record = AsyncMock()
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch("bff.routers.runs.head_sha", return_value="b" * 40), \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            r = cli.post("/api/runs/run-1/message", json={"message": "hi"})
        assert r.status_code == 200, r.text
        record.assert_awaited_once()
        kwargs = record.await_args.kwargs
        assert kwargs["run_id"] == "run-1"
        assert kwargs["event_id"] == "ev-new-1"
        assert kwargs["commit_sha"] == "b" * 40

    def test_conversation_get_fails_downgrades(self) -> None:
        upstream = _FakeUpstream()
        upstream.on_post("/events", _mk_response(200, {"success": True}))
        upstream.on_get("/api/conversations/run-1", _mk_response(500, {"detail": "x"}))
        record = AsyncMock()
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch("bff.routers.runs.head_sha", return_value="b" * 40), \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            r = cli.post("/api/runs/run-1/message", json={"message": "hi"})
        # POST /events still succeeded → 200 to the client.
        assert r.status_code == 200
        record.assert_not_awaited()

    def test_ledger_unavailable_skips_capture(self) -> None:
        upstream = _FakeUpstream()
        upstream.on_post("/events", _mk_response(200, {"success": True}))
        record = AsyncMock()
        app = _build_app_with_ledger_ready(ready=False)
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch("bff.routers.runs.head_sha", return_value="b" * 40), \
             patch("bff.routers.runs.event_commit_ledger.record_sha", record):
            r = cli.post("/api/runs/run-1/message", json={"message": "hi"})
        assert r.status_code == 200
        record.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3. delete_run cascade
# ---------------------------------------------------------------------------


class TestDeleteRunCascadesLedger:
    """DELETE /runs/{id} — must purge event_commit_shas rows."""

    def _wire(self, upstream: _FakeUpstream) -> None:
        upstream.on_get(
            "/api/conversations/run-1",
            _mk_response(200, {"workspace": {"working_dir": "/tmp/run-abc"}}),
        )
        upstream.on_delete("/api/conversations/run-1", _mk_response(204, {}))

    def test_purges_ledger_rows(self) -> None:
        upstream = _FakeUpstream()
        self._wire(upstream)
        delete_run = AsyncMock(return_value=3)
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch("bff.routers.runs.remove_worktree"), \
             patch(
                 "bff.routers.runs.event_commit_ledger.delete_run", delete_run
             ):
            r = cli.delete("/api/runs/run-1")
        assert r.status_code == 204, r.text
        delete_run.assert_awaited_once()
        args = delete_run.await_args.args
        # (app, run_id)
        assert args[1] == "run-1"

    def test_ledger_unavailable_skips_cascade(self) -> None:
        upstream = _FakeUpstream()
        self._wire(upstream)
        delete_run = AsyncMock()
        app = _build_app_with_ledger_ready(ready=False)
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch("bff.routers.runs.remove_worktree"), \
             patch(
                 "bff.routers.runs.event_commit_ledger.delete_run", delete_run
             ):
            r = cli.delete("/api/runs/run-1")
        assert r.status_code == 204
        delete_run.assert_not_awaited()

    def test_ledger_raises_does_not_fail_delete(self) -> None:
        upstream = _FakeUpstream()
        self._wire(upstream)
        delete_run = AsyncMock(side_effect=RuntimeError("boom"))
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch("bff.routers.runs.remove_worktree"), \
             patch(
                 "bff.routers.runs.event_commit_ledger.delete_run", delete_run
             ):
            r = cli.delete("/api/runs/run-1")
        # Cascade blew up but the conversation + worktree were already reaped.
        # The HTTP delete must still succeed.
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# 4. get_run_events sha_lookup threading
# ---------------------------------------------------------------------------


class TestGetRunEventsHydratesShas:
    """GET /runs/{id}/events — bulk lookup + normalize_events wiring."""

    def _events_response(self) -> httpx.Response:
        return _mk_response(
            200,
            {
                "items": [
                    {
                        "id": "ev-1",
                        "kind": "MessageEvent",
                        "source": "user",
                        "content": [{"type": "text", "text": "hi"}],
                    },
                    {
                        "id": "ev-2",
                        "kind": "MessageEvent",
                        "source": "agent",
                        "content": [{"type": "text", "text": "ok"}],
                    },
                    {
                        "id": "ev-3",
                        "kind": "MessageEvent",
                        "source": "user",
                        "content": [{"type": "text", "text": "?"}],
                    },
                ],
                "next_page_id": None,
            },
        )

    def test_stamps_sha_on_user_message_events(self) -> None:
        upstream = _FakeUpstream()
        upstream.on_get("/events/search", self._events_response())
        bulk = AsyncMock(return_value={"ev-1": "c" * 40, "ev-3": "d" * 40})
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.event_commit_ledger.bulk_get_shas", bulk
             ):
            r = cli.get("/api/runs/run-1/events")
        assert r.status_code == 200, r.text
        body = r.json()
        # normalize_event's output key is "id" (matches the wire event schema).
        by_id = {e["id"]: e for e in body["data"]}
        assert by_id["ev-1"].get("commit_sha_at_time_of_event") == "c" * 40
        # Assistant events must never carry the key even when the lookup hits.
        assert "commit_sha_at_time_of_event" not in by_id["ev-2"]
        assert by_id["ev-3"].get("commit_sha_at_time_of_event") == "d" * 40
        # bulk_get_shas received (app, [event_ids]).
        bulk.assert_awaited_once()
        args = bulk.await_args.args
        assert set(args[1]) == {"ev-1", "ev-2", "ev-3"}

    def test_no_ledger_omits_key(self) -> None:
        upstream = _FakeUpstream()
        upstream.on_get("/events/search", self._events_response())
        bulk = AsyncMock()
        app = _build_app_with_ledger_ready(ready=False)
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.event_commit_ledger.bulk_get_shas", bulk
             ):
            r = cli.get("/api/runs/run-1/events")
        assert r.status_code == 200
        body = r.json()
        for ev in body["data"]:
            assert "commit_sha_at_time_of_event" not in ev
        bulk.assert_not_awaited()

    def test_bulk_lookup_failure_downgrades(self) -> None:
        upstream = _FakeUpstream()
        upstream.on_get("/events/search", self._events_response())
        bulk = AsyncMock(side_effect=RuntimeError("db locked"))
        app = _build_app_with_ledger_ready()
        cli = TestClient(app)
        with patch("bff.routers.runs.get_client", return_value=upstream), \
             patch(
                 "bff.routers.runs.event_commit_ledger.bulk_get_shas", bulk
             ):
            r = cli.get("/api/runs/run-1/events")
        # Endpoint still returns events even though the ledger blew up.
        assert r.status_code == 200
        body = r.json()
        for ev in body["data"]:
            assert "commit_sha_at_time_of_event" not in ev
