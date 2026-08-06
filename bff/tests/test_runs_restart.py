"""Tests for POST /api/runs/{run_id}/restart and bff.services.restart.

Stage 6.4c step 1d (ADR-026 §Storage).  Covers the ordered composition
in ``restart_from_here`` and the HTTP mapping in the router.

Ledger + agent-server interactions are mocked via the same
``_FakeUpstream`` pattern used by ``test_runs_sha_capture.py`` — two-tier
match (longest suffix first, longest substring fallback) so more-specific
patterns like ``/events/search`` beat their prefixes.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import runs as runs_router
from bff.services.restart import (
    RestartError,
    RestartResult,
    _extract_message_text,
    restart_from_here,
)


# ---------------------------------------------------------------------------
# Fake upstream (copy of the pattern in test_runs_sha_capture.py)
# ---------------------------------------------------------------------------


def _mk_response(status_code: int, body: Any) -> httpx.Response:
    """Return an httpx.Response with a JSON body."""
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("GET", "http://testserver"),
    )


class _FakeUpstream:
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
        clean = url.split("?", 1)[0]
        suffix_matches = [(p, r) for p, r in table if clean.endswith(p)]
        if suffix_matches:
            suffix_matches.sort(key=lambda pr: len(pr[0]), reverse=True)
            return suffix_matches[0][1]
        substring_matches = [(p, r) for p, r in table if p in clean]
        if substring_matches:
            substring_matches.sort(key=lambda pr: len(pr[0]), reverse=True)
            return substring_matches[0][1]
        return _mk_response(404, {"detail": f"unmocked {url}"})

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


def _build_app(ledger_ready: bool = True) -> FastAPI:
    """Fresh FastAPI app with the runs router mounted, ledger-marked ready."""
    app = FastAPI()
    app.include_router(runs_router.router, prefix="/api")
    app.state.event_commit_db = object() if ledger_ready else None
    return app


# Common source-conversation shape used across most tests.
_SOURCE_CONV_BODY = {
    "id": "run-source-1",
    "title": "src",
    "workspace": {"working_dir": "/tmp/src-wd", "kind": "LocalWorkspace"},
    "agent": {"llm": {"model": "m", "base_url": "http://x"}, "tools": []},
}
_USER_EV = {
    "id": "ev-user-1",
    "kind": "MessageEvent",
    "source": "user",
    "content": [{"type": "text", "text": "hello world"}],
}
_ASSISTANT_EV = {
    "id": "ev-assistant-1",
    "kind": "MessageEvent",
    "source": "agent",
    "content": [{"type": "text", "text": "hi back"}],
}


def _wire_source(upstream: _FakeUpstream, *, events_items: list[dict]) -> None:
    """Wire the two GETs restart_from_here needs on every happy path."""
    upstream.on_get(
        "/api/conversations/run-source-1",
        _mk_response(200, _SOURCE_CONV_BODY),
    )
    upstream.on_get(
        "/events/search",
        _mk_response(200, {"items": events_items}),
    )


# =========================================================================
# TestExtractMessageText — pure helper, no ledger/agent-server involved
# =========================================================================


class TestExtractMessageText:
    def test_content_list_with_text(self) -> None:
        assert _extract_message_text(
            {"content": [{"type": "text", "text": "hi"}]}
        ) == "hi"

    def test_falls_back_to_message_field(self) -> None:
        assert _extract_message_text({"message": "yo"}) == "yo"

    def test_falls_back_to_text_field(self) -> None:
        assert _extract_message_text({"text": "sup"}) == "sup"

    def test_empty_content_returns_empty(self) -> None:
        assert _extract_message_text({"content": []}) == ""

    def test_whitespace_only_content_returns_empty(self) -> None:
        assert _extract_message_text(
            {"content": [{"type": "text", "text": "   "}]}
        ) == ""

    def test_missing_shape_returns_empty(self) -> None:
        assert _extract_message_text({"kind": "MessageEvent"}) == ""

    def test_llm_message_content_extracted(self) -> None:
        """Real agent-server 1.40 stores user text under
        ``llm_message.content[*].text`` (verified live on Colossus
        2026-08-06).  Step 1e follow-up must find it there."""
        ev = {
            "id": "ev-1",
            "kind": "MessageEvent",
            "source": "user",
            "llm_message": {
                "role": "user",
                "content": [
                    {"cache_prompt": False, "type": "text", "text": "probe user text"}
                ],
                "thinking_blocks": [],
            },
            "activated_skills": [],
            "extended_content": [],
        }
        assert _extract_message_text(ev) == "probe user text"

    def test_llm_message_takes_precedence_over_top_content(self) -> None:
        """If both llm_message.content and top-level content are present,
        prefer the agent-server storage form."""
        ev = {
            "llm_message": {"content": [{"type": "text", "text": "real"}]},
            "content": [{"type": "text", "text": "stale"}],
        }
        assert _extract_message_text(ev) == "real"


# =========================================================================
# TestRestartFromHereService — direct calls to the service (bypass HTTP)
# =========================================================================


class TestRestartFromHereService:
    """Direct unit tests against ``restart_from_here``.  Each test builds a
    minimal fake upstream + ledger and calls the coroutine directly."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_result_and_stamps_seed(self) -> None:
        upstream = _FakeUpstream()
        _wire_source(upstream, events_items=[_USER_EV])
        # POST /api/conversations returns the new cid.
        upstream.on_post(
            "/api/conversations",
            _mk_response(200, {"id": "run-new-1"}),
        )
        # POST /events on the new cid (seed).
        upstream.on_post("/events", _mk_response(200, {"success": True}))
        # Follow-up GET on the new cid's events/search returns the seeded event.
        # (Same /events/search suffix as the source scan — /events beats it
        # for the POST because /events/search doesn't apply to POST.  Fine.)

        app = _build_app()
        bulk = AsyncMock(return_value={"ev-user-1": "a" * 40})
        record = AsyncMock()
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart._resolve_source_repo_for_worktree",
                return_value=None,  # forces fallback to working_dir
            ),
            patch(
                "bff.services.restart.provision_worktree",
                return_value=type(
                    "W", (), {"path": "/tmp/new-wd"}
                )(),
            ),
            patch("bff.services.restart.head_sha", return_value="b" * 40),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
            patch(
                "bff.services.restart.event_commit_ledger.record_sha",
                record,
            ),
        ):
            result = await restart_from_here(
                app,
                source_run_id="run-source-1",
                anchor_event_id="ev-user-1",
            )
        assert isinstance(result, RestartResult)
        assert result.restarted_run_id == "run-new-1"
        assert result.source_run_id == "run-source-1"
        assert result.from_event_id == "ev-user-1"
        assert result.reset_to_sha == "a" * 40
        assert result.worktree_path == "/tmp/new-wd"
        assert result.message_text == "hello world"
        # Ledger stamped both bulk-lookup AND the follow-up seed capture.
        bulk.assert_awaited_once()
        # record was awaited for the seed sha (best-effort).
        record.assert_awaited()

    @pytest.mark.asyncio
    async def test_source_not_found_raises(self) -> None:
        upstream = _FakeUpstream()
        upstream.on_get(
            "/api/conversations/run-source-1",
            _mk_response(404, {"detail": "not found"}),
        )
        app = _build_app()
        with patch("bff.services.restart.get_client", return_value=upstream):
            with pytest.raises(RestartError) as exc_info:
                await restart_from_here(
                    app,
                    source_run_id="run-source-1",
                    anchor_event_id="ev-user-1",
                )
        assert exc_info.value.code == "source_not_found"

    @pytest.mark.asyncio
    async def test_no_sha_anchor_raises(self) -> None:
        upstream = _FakeUpstream()
        _wire_source(upstream, events_items=[_USER_EV])
        app = _build_app()
        bulk = AsyncMock(return_value={})  # ledger has no row
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
        ):
            with pytest.raises(RestartError) as exc_info:
                await restart_from_here(
                    app,
                    source_run_id="run-source-1",
                    anchor_event_id="ev-user-1",
                )
        assert exc_info.value.code == "no_sha_anchor"

    @pytest.mark.asyncio
    async def test_anchor_event_not_in_run_raises(self) -> None:
        upstream = _FakeUpstream()
        # Source exists but the events/search page doesn't contain ev-user-1.
        _wire_source(upstream, events_items=[_ASSISTANT_EV])
        app = _build_app()
        bulk = AsyncMock(return_value={"ev-user-1": "a" * 40})
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
        ):
            with pytest.raises(RestartError) as exc_info:
                await restart_from_here(
                    app,
                    source_run_id="run-source-1",
                    anchor_event_id="ev-user-1",
                )
        assert exc_info.value.code == "anchor_not_found"

    @pytest.mark.asyncio
    async def test_unknown_event_id_returns_anchor_not_found_not_no_sha(
        self,
    ) -> None:
        """Step 1e follow-up: unknown event id must yield 404
        (anchor_not_found) even though the ledger also has no row for it.
        Previous ordering did ledger-check first and returned 409
        no_sha_anchor for genuine typos — misleading and hard to debug."""
        upstream = _FakeUpstream()
        # Source exists, events page is empty.
        _wire_source(upstream, events_items=[])
        app = _build_app()
        # Ledger also has no row (typical for a completely unknown id).
        bulk = AsyncMock(return_value={})
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
        ):
            with pytest.raises(RestartError) as exc_info:
                await restart_from_here(
                    app,
                    source_run_id="run-source-1",
                    anchor_event_id="ev-does-not-exist",
                )
        assert exc_info.value.code == "anchor_not_found"
        # Ledger should not have been consulted — event check happens first.
        bulk.assert_not_called()

    @pytest.mark.asyncio
    async def test_anchor_is_assistant_message_raises(self) -> None:
        upstream = _FakeUpstream()
        # Assistant event carries the anchor id — should still be rejected.
        assistant_with_target_id = dict(_ASSISTANT_EV, id="ev-user-1")
        _wire_source(upstream, events_items=[assistant_with_target_id])
        app = _build_app()
        bulk = AsyncMock(return_value={"ev-user-1": "a" * 40})
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
        ):
            with pytest.raises(RestartError) as exc_info:
                await restart_from_here(
                    app,
                    source_run_id="run-source-1",
                    anchor_event_id="ev-user-1",
                )
        assert exc_info.value.code == "not_user_message"

    @pytest.mark.asyncio
    async def test_worktree_provision_failure_raises_502(self) -> None:
        upstream = _FakeUpstream()
        _wire_source(upstream, events_items=[_USER_EV])
        app = _build_app()
        bulk = AsyncMock(return_value={"ev-user-1": "a" * 40})
        from bff.services.worktree import WorktreeError as _WE
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart._resolve_source_repo_for_worktree",
                return_value=None,
            ),
            patch(
                "bff.services.restart.provision_worktree",
                side_effect=_WE("not a git repo"),
            ),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
        ):
            with pytest.raises(RestartError) as exc_info:
                await restart_from_here(
                    app,
                    source_run_id="run-source-1",
                    anchor_event_id="ev-user-1",
                )
        assert exc_info.value.code == "worktree_failed"

    @pytest.mark.asyncio
    async def test_create_conversation_failure_rolls_back_worktree(
        self,
    ) -> None:
        upstream = _FakeUpstream()
        _wire_source(upstream, events_items=[_USER_EV])
        upstream.on_post(
            "/api/conversations",
            _mk_response(500, {"detail": "boom"}),
        )
        app = _build_app()
        bulk = AsyncMock(return_value={"ev-user-1": "a" * 40})
        remove = MagicMock()
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart._resolve_source_repo_for_worktree",
                return_value=None,
            ),
            patch(
                "bff.services.restart.provision_worktree",
                return_value=type("W", (), {"path": "/tmp/new-wd"})(),
            ),
            patch("bff.services.restart.remove_worktree", remove),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
        ):
            with pytest.raises(RestartError) as exc_info:
                await restart_from_here(
                    app,
                    source_run_id="run-source-1",
                    anchor_event_id="ev-user-1",
                )
        assert exc_info.value.code == "create_failed"
        remove.assert_called_once()
        # rollback ran with the minted id + missing_ok=True.
        args, kwargs = remove.call_args
        assert args[0].startswith("run-")
        assert kwargs.get("missing_ok") is True

    @pytest.mark.asyncio
    async def test_seed_failure_rolls_back_worktree(self) -> None:
        upstream = _FakeUpstream()
        _wire_source(upstream, events_items=[_USER_EV])
        upstream.on_post(
            "/api/conversations",
            _mk_response(200, {"id": "run-new-1"}),
        )
        # Seed POST fails.
        upstream.on_post(
            "/events",
            _mk_response(500, {"detail": "kaboom"}),
        )
        app = _build_app()
        bulk = AsyncMock(return_value={"ev-user-1": "a" * 40})
        remove = MagicMock()
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart._resolve_source_repo_for_worktree",
                return_value=None,
            ),
            patch(
                "bff.services.restart.provision_worktree",
                return_value=type("W", (), {"path": "/tmp/new-wd"})(),
            ),
            patch("bff.services.restart.remove_worktree", remove),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
        ):
            with pytest.raises(RestartError) as exc_info:
                await restart_from_here(
                    app,
                    source_run_id="run-source-1",
                    anchor_event_id="ev-user-1",
                )
        assert exc_info.value.code == "seed_failed"
        remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_ledger_stamp_failure_does_not_fail_outer(self) -> None:
        """Seed-event sha capture is best-effort — a raise on record_sha
        must not turn the successful restart into a failure."""
        upstream = _FakeUpstream()
        _wire_source(upstream, events_items=[_USER_EV])
        upstream.on_post(
            "/api/conversations",
            _mk_response(200, {"id": "run-new-1"}),
        )
        upstream.on_post("/events", _mk_response(200, {"success": True}))

        app = _build_app()
        bulk = AsyncMock(return_value={"ev-user-1": "a" * 40})
        record = AsyncMock(side_effect=RuntimeError("ledger down"))
        with (
            patch("bff.services.restart.get_client", return_value=upstream),
            patch(
                "bff.services.restart._resolve_source_repo_for_worktree",
                return_value=None,
            ),
            patch(
                "bff.services.restart.provision_worktree",
                return_value=type("W", (), {"path": "/tmp/new-wd"})(),
            ),
            patch("bff.services.restart.head_sha", return_value="b" * 40),
            patch(
                "bff.services.restart.event_commit_ledger.bulk_get_shas",
                bulk,
            ),
            patch(
                "bff.services.restart.event_commit_ledger.record_sha",
                record,
            ),
        ):
            result = await restart_from_here(
                app,
                source_run_id="run-source-1",
                anchor_event_id="ev-user-1",
            )
        assert result.restarted_run_id == "run-new-1"


# =========================================================================
# TestFetchEventPagination — agent-server limit<=100 + next_page_id follow
# =========================================================================


class TestFetchEventPagination:
    """Step 1e regression: agent-server's ``search_conversation_events``
    asserts ``limit <= 100`` — exceeding is a HTTP 500 AssertionError.
    _fetch_event must page via ``next_page_id`` instead of asking for a
    single window >100.  Verified live on Colossus 2026-08-06."""

    @pytest.mark.asyncio
    async def test_never_requests_limit_over_100(self) -> None:
        from bff.services.restart import _fetch_event

        upstream = _FakeUpstream()
        upstream.on_get(
            "/events/search",
            _mk_response(200, {"items": [_USER_EV]}),
        )
        # Even if the caller asks for a huge page, we must clamp to 100.
        with patch("bff.services.restart.get_client", return_value=upstream):
            found = await _fetch_event(
                upstream, "run-source-1", "ev-user-1", page_size=500
            )
        assert found is not None
        # Every events/search call must have limit <= 100.
        search_calls = [
            call for call in upstream.calls
            if call[0] == "GET" and "/events/search" in call[1]
        ]
        assert search_calls, "expected at least one events/search call"
        for _method, _url, params in search_calls:
            assert params.get("limit", 0) <= 100, params

    @pytest.mark.asyncio
    async def test_follows_next_page_id(self) -> None:
        """Anchor lives on page 2 — fetch must page past page 1."""
        from bff.services.restart import _fetch_event

        upstream = _FakeUpstream()

        # Two responses: first without our target + next_page_id set;
        # second with our target.  _FakeUpstream returns the LONGEST
        # matching suffix, so both share the same suffix and we need to
        # sequence them by side-effect.  Easiest: swap the handler.
        page1 = _mk_response(
            200,
            {
                "items": [_ASSISTANT_EV],
                "next_page_id": "cursor-2",
            },
        )
        page2 = _mk_response(200, {"items": [_USER_EV]})

        state = {"page": 0}

        async def fake_get(url: str, *, params: dict[str, Any] | None = None, **_: Any) -> httpx.Response:
            upstream.calls.append(("GET", url, params or {}))
            state["page"] += 1
            return page2 if state["page"] > 1 else page1

        upstream.get = fake_get  # type: ignore[method-assign]

        found = await _fetch_event(upstream, "run-source-1", "ev-user-1")
        assert found is not None
        assert (found.get("id") or found.get("event_id")) == "ev-user-1"

        # Second call must have carried page_id=cursor-2
        search_calls = [
            call for call in upstream.calls
            if call[0] == "GET" and "/events/search" in call[1]
        ]
        assert len(search_calls) == 2
        assert search_calls[1][2].get("page_id") == "cursor-2"


# =========================================================================
# TestRestartEndpoint — full HTTP path through TestClient
# =========================================================================


class TestRestartEndpoint:
    """End-to-end tests through the FastAPI TestClient.  Verifies HTTP
    status mapping in _RESTART_CODE_TO_STATUS + response body shape."""

    def test_happy_path_returns_200_and_shape(self) -> None:
        app = _build_app()
        cli = TestClient(app)
        fake = RestartResult(
            restarted_run_id="run-new-1",
            source_run_id="run-source-1",
            from_event_id="ev-user-1",
            reset_to_sha="a" * 40,
            worktree_path="/tmp/new-wd",
            message_text="hi",
        )
        with patch(
            "bff.routers.runs.restart_from_here",
            AsyncMock(return_value=fake),
        ):
            r = cli.post(
                "/api/runs/run-source-1/restart",
                json={"from_event_id": "ev-user-1"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["restarted_run_id"] == "run-new-1"
        assert body["source_run_id"] == "run-source-1"
        assert body["from_event_id"] == "ev-user-1"
        assert body["reset_to_sha"] == "a" * 40
        assert body["worktree_path"] == "/tmp/new-wd"

    def test_source_not_found_maps_to_404(self) -> None:
        app = _build_app()
        cli = TestClient(app)
        with patch(
            "bff.routers.runs.restart_from_here",
            AsyncMock(side_effect=RestartError("source_not_found", "gone")),
        ):
            r = cli.post(
                "/api/runs/run-source-1/restart",
                json={"from_event_id": "ev-user-1"},
            )
        assert r.status_code == 404

    def test_no_sha_anchor_maps_to_409(self) -> None:
        app = _build_app()
        cli = TestClient(app)
        with patch(
            "bff.routers.runs.restart_from_here",
            AsyncMock(side_effect=RestartError("no_sha_anchor", "no row")),
        ):
            r = cli.post(
                "/api/runs/run-source-1/restart",
                json={"from_event_id": "ev-user-1"},
            )
        assert r.status_code == 409

    def test_not_user_message_maps_to_409(self) -> None:
        app = _build_app()
        cli = TestClient(app)
        with patch(
            "bff.routers.runs.restart_from_here",
            AsyncMock(side_effect=RestartError("not_user_message", "no")),
        ):
            r = cli.post(
                "/api/runs/run-source-1/restart",
                json={"from_event_id": "ev-user-1"},
            )
        assert r.status_code == 409

    def test_worktree_failed_maps_to_502(self) -> None:
        app = _build_app()
        cli = TestClient(app)
        with patch(
            "bff.routers.runs.restart_from_here",
            AsyncMock(side_effect=RestartError("worktree_failed", "bad")),
        ):
            r = cli.post(
                "/api/runs/run-source-1/restart",
                json={"from_event_id": "ev-user-1"},
            )
        assert r.status_code == 502

    def test_missing_from_event_id_maps_to_422(self) -> None:
        """Pydantic validation gate on RestartRunRequest."""
        app = _build_app()
        cli = TestClient(app)
        r = cli.post("/api/runs/run-source-1/restart", json={})
        assert r.status_code == 422

    def test_unknown_error_code_falls_back_to_502(self) -> None:
        app = _build_app()
        cli = TestClient(app)
        with patch(
            "bff.routers.runs.restart_from_here",
            AsyncMock(side_effect=RestartError("mystery", "?")),
        ):
            r = cli.post(
                "/api/runs/run-source-1/restart",
                json={"from_event_id": "ev-user-1"},
            )
        assert r.status_code == 502
