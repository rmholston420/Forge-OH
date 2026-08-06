"""Tests for ``openhands_tools_ext.search.tools.search_web`` (Stage 6.1).

Behavioural contract:

* ``SearchWebTool.create()`` yields one instance with the correct
  action/observation types and read-only annotations.
* ``SearchWebExecutor`` returns hits from the SearXNG adapter via the
  patched ``_run_search`` coroutine (no live SearXNG is booted during tests).
* Emit to the BFF is best-effort: a failing POST leaves ``emitted=False``
  but the observation still carries the hits and provenance.
* The tool is registered in the SDK registry at import time under the
  name ``search_web``.
"""

from __future__ import annotations

import types
from typing import Any

import pytest

from openhands_tools_ext.search.tools import search_web as sw


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _FakeConversation:
    def __init__(self, conv_id: str) -> None:
        self.id = conv_id


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class _FakeHttpxClient:
    """Context-manager stub matching ``httpx.Client`` well enough for emit."""

    calls: list[dict[str, Any]] = []
    status_code: int = 200
    raises: Exception | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        pass

    def __enter__(self) -> "_FakeHttpxClient":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:  # noqa: A002
        if _FakeHttpxClient.raises is not None:
            raise _FakeHttpxClient.raises
        _FakeHttpxClient.calls.append({"url": url, "json": json})
        return _FakeResponse(status_code=_FakeHttpxClient.status_code)


@pytest.fixture(autouse=True)
def _reset_fake_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeHttpxClient.calls = []
    _FakeHttpxClient.status_code = 200
    _FakeHttpxClient.raises = None
    monkeypatch.setattr(sw.httpx, "Client", _FakeHttpxClient)


def _patch_search(
    monkeypatch: pytest.MonkeyPatch,
    hits: list[dict[str, Any]],
    provenance: str = "searxng:http://127.0.0.1:18888",
    latency_ms: int = 42,
) -> None:
    async def _fake_run_search(
        query: str,
        num_results: int,
        language: str,
        engines: list[str] | None,
    ) -> tuple[list[dict[str, Any]], str, int]:
        assert isinstance(query, str)
        assert isinstance(num_results, int) and num_results >= 1
        assert isinstance(language, str)
        assert engines is None or isinstance(engines, list)
        return hits, provenance, latency_ms

    monkeypatch.setattr(sw, "_run_search", _fake_run_search)


# ---------------------------------------------------------------------------
# Registration + factory shape
# ---------------------------------------------------------------------------


def test_tool_is_registered_under_search_web_name() -> None:
    from openhands.sdk.tool import registry as reg

    registry_dict = getattr(reg, "_REG", None)
    assert isinstance(registry_dict, dict), (
        "openhands.sdk.tool.registry._REG is not a dict — SDK internals "
        "changed shape; update the probe."
    )
    assert "search_web" in registry_dict, (
        "search_web is not in openhands.sdk.tool.registry._REG after "
        "importing openhands_tools_ext.search.tools.search_web — "
        "register_tool did not run at import time."
    )
    resolved = registry_dict["search_web"]
    assert callable(resolved) or resolved is sw.SearchWebTool, (
        f"unexpected registry value for search_web: {resolved!r}"
    )


def test_create_yields_single_tool_with_correct_shape() -> None:
    tools = list(sw.SearchWebTool.create())
    assert len(tools) == 1
    tool = tools[0]
    assert tool.action_type is sw.SearchWebAction
    assert tool.observation_type is sw.SearchWebObservation
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.openWorldHint is True
    assert isinstance(tool.executor, sw.SearchWebExecutor)


def test_create_rejects_unknown_factory_params() -> None:
    with pytest.raises(ValueError, match="does not accept factory parameters"):
        sw.SearchWebTool.create(unexpected="value")


# ---------------------------------------------------------------------------
# Executor happy path
# ---------------------------------------------------------------------------


def test_executor_returns_hits_and_emits(monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [
        {
            "title": "Python asyncio docs",
            "url": "https://docs.python.org/3/library/asyncio.html",
            "snippet": "asyncio is a library to write concurrent code",
            "engine": "duckduckgo",
            "score": 0.91,
        },
        {
            "title": "PEP 3156",
            "url": "https://peps.python.org/pep-3156/",
            "snippet": "asyncio event loop",
            "engine": "brave",
            "score": 0.42,
        },
    ]
    _patch_search(monkeypatch, hits)

    executor = sw.SearchWebExecutor()
    action = sw.SearchWebAction(query="python asyncio", num_results=5)
    obs = executor(action, conversation=_FakeConversation("run-123"))

    assert obs.query == "python asyncio"
    assert obs.result_count == 2
    assert obs.results == hits
    assert obs.provenance == "searxng:http://127.0.0.1:18888"
    assert obs.latency_ms == 42
    assert obs.emitted is True
    assert len(_FakeHttpxClient.calls) == 1
    call = _FakeHttpxClient.calls[0]
    assert call["url"].endswith("/api/search/emit")
    assert call["json"] == {
        "runId": "run-123",
        "query": "python asyncio",
        "resultCount": 2,
        "provenance": "searxng:http://127.0.0.1:18888",
        "latencyMs": 42,
    }


def test_executor_handles_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_search(monkeypatch, [])
    executor = sw.SearchWebExecutor()
    obs = executor(
        sw.SearchWebAction(query="miss", num_results=3),
        conversation=_FakeConversation("run-empty"),
    )
    assert obs.result_count == 0
    assert obs.results == []
    assert obs.emitted is True  # emit still fires so the UI marker shows the query


def test_executor_skips_emit_without_conversation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_search(monkeypatch, [{"title": "t", "url": "u", "snippet": "s", "engine": None, "score": None}])
    executor = sw.SearchWebExecutor()

    obs = executor(sw.SearchWebAction(query="q"), conversation=None)
    assert obs.emitted is False
    assert _FakeHttpxClient.calls == []

    obs = executor(
        sw.SearchWebAction(query="q"),
        conversation=types.SimpleNamespace(),
    )
    assert obs.emitted is False
    assert _FakeHttpxClient.calls == []


def test_executor_marks_emit_failed_on_bff_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_search(monkeypatch, [{"title": "t", "url": "u", "snippet": "s", "engine": None, "score": None}])
    _FakeHttpxClient.status_code = 503

    executor = sw.SearchWebExecutor()
    obs = executor(
        sw.SearchWebAction(query="q"),
        conversation=_FakeConversation("run-503"),
    )
    assert obs.result_count == 1
    assert obs.emitted is False
    assert len(_FakeHttpxClient.calls) == 1


def test_executor_marks_emit_failed_on_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_search(monkeypatch, [{"title": "t", "url": "u", "snippet": "s", "engine": None, "score": None}])
    _FakeHttpxClient.raises = RuntimeError("boom")

    executor = sw.SearchWebExecutor()
    obs = executor(
        sw.SearchWebAction(query="q"),
        conversation=_FakeConversation("run-boom"),
    )
    assert obs.result_count == 1
    assert obs.emitted is False


def test_action_forwards_engines_and_language(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def _fake_run_search(query, num_results, language, engines):
        captured["query"] = query
        captured["num_results"] = num_results
        captured["language"] = language
        captured["engines"] = engines
        return [], "searxng:http://127.0.0.1:18888", 0

    monkeypatch.setattr(sw, "_run_search", _fake_run_search)

    executor = sw.SearchWebExecutor()
    executor(
        sw.SearchWebAction(
            query="q", num_results=3, language="es", engines=["duckduckgo", "brave"]
        ),
        conversation=_FakeConversation("run-1"),
    )
    assert captured == {
        "query": "q",
        "num_results": 3,
        "language": "es",
        "engines": ["duckduckgo", "brave"],
    }
