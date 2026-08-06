"""Tests for ``openhands_tools_ext.memory.tools.consult_memory`` (Stage 5.6b).

Behavioural contract:

* ``ConsultMemoryTool.create()`` yields one instance with the correct
  action/observation types and read-only annotations.
* ``ConsultMemoryExecutor`` returns hits from the semantic tier via the
  patched ``_run_semantic`` coroutine (no live DozerDB, Qdrant, or
  Ollama is booted during tests).
* Unsupported tiers raise ``NotImplementedError`` before any I/O.
* Emit to the BFF is best-effort: a failing POST leaves ``emitted=False``
  but the observation still carries the hits.
* The tool is registered in the SDK registry at import time under the
  name ``consult_memory``.
"""

from __future__ import annotations

import types
from typing import Any

import pytest

from openhands_tools_ext.memory.tools import consult_memory as cm


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _FakeConversation:
    """Minimal stand-in exposing ``id``, sufficient for _resolve_conversation_id."""

    def __init__(self, conv_id: str) -> None:
        self.id = conv_id


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class _FakeHttpxClient:
    """Context-manager stub matching ``httpx.Client`` well enough for the emit call."""

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
    monkeypatch.setattr(cm.httpx, "Client", _FakeHttpxClient)


# ---------------------------------------------------------------------------
# Registration + factory shape
# ---------------------------------------------------------------------------


def test_tool_is_registered_under_consult_memory_name() -> None:
    from openhands.sdk.tool.registry import resolve_tool

    resolved = resolve_tool("consult_memory")
    assert resolved is cm.ConsultMemoryTool or isinstance(
        resolved, cm.ConsultMemoryTool
    )


def test_create_yields_single_tool_with_correct_shape() -> None:
    tools = list(cm.ConsultMemoryTool.create())
    assert len(tools) == 1
    tool = tools[0]
    assert tool.action_type is cm.ConsultMemoryAction
    assert tool.observation_type is cm.ConsultMemoryObservation
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert isinstance(tool.executor, cm.ConsultMemoryExecutor)


def test_create_rejects_unknown_factory_params() -> None:
    with pytest.raises(ValueError, match="does not accept factory parameters"):
        cm.ConsultMemoryTool.create(unexpected="value")


# ---------------------------------------------------------------------------
# Executor happy path
# ---------------------------------------------------------------------------


def _patch_semantic(monkeypatch: pytest.MonkeyPatch, hits: list[dict[str, Any]]) -> None:
    async def _fake_run_semantic(query: str, limit: int) -> list[dict[str, Any]]:
        # We keep the signature so mismatches fail loudly.
        assert isinstance(query, str)
        assert isinstance(limit, int) and limit >= 1
        return hits

    monkeypatch.setattr(cm, "_run_semantic", _fake_run_semantic)


def test_executor_returns_hits_and_emits(monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [
        {"id": "m1", "score": 0.91, "payload": {"subject": "playwright-seed"}},
        {"id": "m2", "score": 0.42, "payload": {"subject": "stage-5.3b-smoke"}},
    ]
    _patch_semantic(monkeypatch, hits)

    executor = cm.ConsultMemoryExecutor()
    action = cm.ConsultMemoryAction(
        tier="semantic", query="what have we seeded?", limit=5
    )
    obs = executor(action, conversation=_FakeConversation("run-123"))

    assert obs.tier == "semantic"
    assert obs.result_count == 2
    assert obs.hits == hits
    assert obs.emitted is True
    assert len(_FakeHttpxClient.calls) == 1
    call = _FakeHttpxClient.calls[0]
    assert call["url"].endswith("/api/memory/emit-consultation")
    assert call["json"] == {
        "runId": "run-123",
        "tier": "semantic",
        "query": "what have we seeded?",
        "resultCount": 2,
    }


def test_executor_handles_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_semantic(monkeypatch, [])
    executor = cm.ConsultMemoryExecutor()
    obs = executor(
        cm.ConsultMemoryAction(tier="semantic", query="miss", limit=3),
        conversation=_FakeConversation("run-empty"),
    )
    assert obs.result_count == 0
    assert obs.hits == []
    assert obs.emitted is True  # emit still fires so the UI marker shows the query


def test_executor_skips_emit_without_conversation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_semantic(monkeypatch, [{"id": "m1", "score": 0.5, "payload": {}}])
    executor = cm.ConsultMemoryExecutor()

    # No conversation supplied.
    obs = executor(
        cm.ConsultMemoryAction(tier="semantic", query="q", limit=1),
        conversation=None,
    )
    assert obs.emitted is False
    assert _FakeHttpxClient.calls == []

    # Conversation without an id attribute.
    obs = executor(
        cm.ConsultMemoryAction(tier="semantic", query="q", limit=1),
        conversation=types.SimpleNamespace(),
    )
    assert obs.emitted is False
    assert _FakeHttpxClient.calls == []


def test_executor_marks_emit_failed_on_bff_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_semantic(monkeypatch, [{"id": "m1", "score": 0.5, "payload": {}}])
    _FakeHttpxClient.status_code = 503

    executor = cm.ConsultMemoryExecutor()
    obs = executor(
        cm.ConsultMemoryAction(tier="semantic", query="q", limit=1),
        conversation=_FakeConversation("run-503"),
    )
    assert obs.result_count == 1
    assert obs.emitted is False
    # The call still went out; failure was on the server side.
    assert len(_FakeHttpxClient.calls) == 1


def test_executor_marks_emit_failed_on_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_semantic(monkeypatch, [{"id": "m1", "score": 0.5, "payload": {}}])
    _FakeHttpxClient.raises = RuntimeError("boom")

    executor = cm.ConsultMemoryExecutor()
    obs = executor(
        cm.ConsultMemoryAction(tier="semantic", query="q", limit=1),
        conversation=_FakeConversation("run-boom"),
    )
    assert obs.result_count == 1
    assert obs.emitted is False


# ---------------------------------------------------------------------------
# Unsupported tiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", ["temporal", "episodic", "procedural", ""])
def test_unsupported_tier_raises_before_any_io(
    tier: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # If the executor accidentally reaches _run_semantic, force a loud failure.
    async def _fail(*_a: Any, **_kw: Any) -> None:
        raise AssertionError("_run_semantic must not run for unsupported tiers")

    monkeypatch.setattr(cm, "_run_semantic", _fail)

    executor = cm.ConsultMemoryExecutor()
    with pytest.raises(NotImplementedError, match="not supported"):
        executor(
            cm.ConsultMemoryAction(tier=tier or "temporal", query="q", limit=1),
            conversation=_FakeConversation("run-x"),
        )


# ---------------------------------------------------------------------------
# Conversation id resolution
# ---------------------------------------------------------------------------


def test_resolve_conversation_id_prefers_id_attribute() -> None:
    conv = types.SimpleNamespace(id="abc")
    assert cm._resolve_conversation_id(conv) == "abc"


def test_resolve_conversation_id_falls_back_to_state_id() -> None:
    conv = types.SimpleNamespace(state=types.SimpleNamespace(id="xyz"))
    assert cm._resolve_conversation_id(conv) == "xyz"


def test_resolve_conversation_id_returns_none_when_absent() -> None:
    assert cm._resolve_conversation_id(None) is None
    assert cm._resolve_conversation_id(types.SimpleNamespace()) is None
