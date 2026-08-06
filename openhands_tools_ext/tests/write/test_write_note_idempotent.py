"""Stage 6.3 — write_note + IdempotentToolExecutor integration tests.

These tests exercise the full mixin path through a stubbed httpx client
so no live BFF is required.  A separate crash-and-resume smoke test
lives in ``scripts/test-crash-resume.sh`` and exercises real
BFF + agent-server + SQLite persistence.

Contract:
  * First call writes the file and posts to /api/idempotency/mark.
  * Second identical call (mocked ledger says ``completed=true``) does
    NOT re-write; observation.idempotent_replay is True.
  * Missing conversation id bypasses the ledger.
  * BFF network failure on check fails open — execution still proceeds.
  * TOOL_NAME set to the SDK-registered string ``write_note``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from openhands_tools_ext.common import idempotent_executor as ie
from openhands_tools_ext.write.tools import write_note as wn


# ---------------------------------------------------------------------------
# Fake conversation + fake BFF
# ---------------------------------------------------------------------------


class _FakeState:
    def __init__(self, leaf: str | None) -> None:
        self.leaf_event_id = leaf


class _FakeConversation:
    def __init__(self, conv_id: str, leaf: str | None = "leaf-1") -> None:
        self.id = conv_id
        self.state = _FakeState(leaf)


class _StubClient:
    """Records posts and returns pre-programmed responses."""

    def __init__(
        self,
        check_response: dict | None = None,
        check_raises: Exception | None = None,
        check_status: int = 200,
    ) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._check_response = check_response
        self._check_raises = check_raises
        self._check_status = check_status

    def __enter__(self) -> "_StubClient":
        return self

    def __exit__(self, *a: Any) -> None:  # noqa: D401
        return None

    def post(self, url: str, json: dict) -> Any:  # noqa: A002
        self.calls.append((url, json))
        if "/idempotency/check" in url:
            if self._check_raises is not None:
                raise self._check_raises
            return _StubResponse(self._check_status, self._check_response or {})
        # /idempotency/mark always succeeds in tests.
        return _StubResponse(200, {"data": {"key": "k", "recorded": True}})


class _StubResponse:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body
        self.text = "stub"

    def json(self) -> dict:
        return self._body


@pytest.fixture
def notes_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "notes"
    monkeypatch.setenv("FORGE_NOTES_DIR", str(d))
    return d


@pytest.fixture
def patched_httpx(monkeypatch: pytest.MonkeyPatch):
    """Yield a mutable holder — tests set holder['client'] to swap stubs."""
    holder: dict[str, _StubClient] = {}

    def factory(*a: Any, **kw: Any) -> _StubClient:  # noqa: ARG001
        return holder["client"]

    monkeypatch.setattr(ie.httpx, "Client", factory)
    return holder


# ---------------------------------------------------------------------------
# TOOL_NAME sanity
# ---------------------------------------------------------------------------


def test_executor_declares_tool_name():
    assert wn.WriteNoteExecutor.TOOL_NAME == "write_note"


# ---------------------------------------------------------------------------
# First call — ledger miss, real write
# ---------------------------------------------------------------------------


def test_first_call_writes_file_and_marks_ledger(
    notes_dir: Path, patched_httpx: dict
):
    patched_httpx["client"] = _StubClient(
        check_response={"data": {"completed": False, "key": "k", "cached": None}}
    )
    executor = wn.WriteNoteExecutor()
    action = wn.WriteNoteAction(title="Hello", body="World")
    conv = _FakeConversation("conv-1", "leaf-1")

    obs = executor(action, conv)

    assert obs.idempotent_replay is False
    assert obs.bytes_written == len("World")
    path = Path(obs.path)
    assert path.exists()
    assert path.read_text() == "World"

    calls = patched_httpx["client"].calls
    assert len(calls) == 2
    assert "/idempotency/check" in calls[0][0]
    assert "/idempotency/mark" in calls[1][0]
    mark_body = calls[1][1]
    assert mark_body["conversation_id"] == "conv-1"
    assert mark_body["leaf_event_id"] == "leaf-1"
    assert mark_body["tool_name"] == "write_note"
    assert mark_body["arguments"] == {"title": "Hello", "body": "World"}
    assert mark_body["result_json"] == {
        "title": "Hello",
        "path": str(path),
        "bytes_written": len("World"),
    }


# ---------------------------------------------------------------------------
# Second call — ledger hit, no re-write
# ---------------------------------------------------------------------------


def test_ledger_hit_returns_cached_without_rewriting(
    notes_dir: Path, patched_httpx: dict
):
    # Pre-existing note on disk with sentinel body.
    notes_dir.mkdir(parents=True, exist_ok=True)
    slug = wn._slug("Hello")
    target = notes_dir / f"{slug}.txt"
    target.write_text("OLD-CONTENT")

    # Ledger says: completed, and hands back the cached observation JSON.
    patched_httpx["client"] = _StubClient(
        check_response={
            "data": {
                "completed": True,
                "key": "k",
                "cached": {
                    "result_summary": "wrote 5 bytes to " + str(target),
                    "result_json": {
                        "title": "Hello",
                        "path": str(target),
                        "bytes_written": 5,
                    },
                    "completed_at": 1_700_000_000.0,
                },
            }
        }
    )
    executor = wn.WriteNoteExecutor()
    action = wn.WriteNoteAction(title="Hello", body="World-NEW")
    conv = _FakeConversation("conv-1", "leaf-1")

    obs = executor(action, conv)

    assert obs.idempotent_replay is True
    assert obs.path == str(target)
    assert obs.bytes_written == 5
    # File was NOT rewritten — content is still the sentinel.
    assert target.read_text() == "OLD-CONTENT"

    # Only /check was called; /mark must not have run.
    calls = patched_httpx["client"].calls
    assert len(calls) == 1
    assert "/idempotency/check" in calls[0][0]


# ---------------------------------------------------------------------------
# Bypass paths
# ---------------------------------------------------------------------------


def test_no_conversation_bypasses_ledger(
    notes_dir: Path, patched_httpx: dict
):
    # Even if the stub were called it would return "completed=true" —
    # the bypass path must never reach it.
    patched_httpx["client"] = _StubClient(
        check_response={
            "data": {
                "completed": True,
                "key": "k",
                "cached": {"result_json": {"title": "x", "path": "y", "bytes_written": 0}},
            }
        }
    )
    executor = wn.WriteNoteExecutor()
    action = wn.WriteNoteAction(title="Hello", body="Fresh")
    obs = executor(action, conversation=None)

    assert obs.idempotent_replay is False
    assert obs.bytes_written == len("Fresh")
    # No calls should have been made.
    assert patched_httpx["client"].calls == []


def test_check_network_failure_fails_open(
    notes_dir: Path, patched_httpx: dict
):
    patched_httpx["client"] = _StubClient(
        check_raises=httpx.ConnectError("connection refused")
    )
    executor = wn.WriteNoteExecutor()
    action = wn.WriteNoteAction(title="Hello", body="Fresh")
    conv = _FakeConversation("conv-1", "leaf-1")

    obs = executor(action, conv)

    # Ledger check failed -> fail-open -> real execution.
    assert obs.idempotent_replay is False
    assert obs.bytes_written == len("Fresh")


# ---------------------------------------------------------------------------
# Filename determinism
# ---------------------------------------------------------------------------


def test_same_title_yields_same_filename(
    notes_dir: Path, patched_httpx: dict
):
    patched_httpx["client"] = _StubClient(
        check_response={"data": {"completed": False, "key": "k", "cached": None}}
    )
    executor = wn.WriteNoteExecutor()

    obs1 = executor(
        wn.WriteNoteAction(title="Same", body="one"),
        _FakeConversation("c1", "l1"),
    )
    # Reset the stub call log for the second call.
    patched_httpx["client"].calls.clear()
    obs2 = executor(
        wn.WriteNoteAction(title="Same", body="two"),
        _FakeConversation("c2", "l2"),
    )
    assert obs1.path == obs2.path
