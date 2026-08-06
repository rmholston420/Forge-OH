"""Stage 6.4c (ADR-026 §Storage) — event_normalize sha_lookup kwarg.

Verifies :func:`bff.services.event_normalize.normalize_event` (and its
plural :func:`normalize_events`) stamp ``commit_sha_at_time_of_event`` on
user ``MessageEvent`` outputs when the caller passes ``sha_lookup=`` and
the lookup returns a value.

Covers:
  * user MessageEvent + sha hit → key present with correct value
  * user MessageEvent + sha miss (returns None) → key absent
  * assistant MessageEvent + sha hit → key absent (source guard)
  * agent MessageEvent + sha hit → key absent (source guard, alt label)
  * ActionEvent + sha hit → key absent (kind guard)
  * user MessageEvent with empty id → sha_lookup not called
  * sha_lookup=None (default) → pre-ADR-026 shape unchanged
  * normalize_events threads sha_lookup to every element
  * normalize_events filters non-dict items but still stamps valid ones
"""

from __future__ import annotations

from typing import Any

from bff.services import event_normalize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_msg(event_id: str = "evt-user-1", text: str = "hi") -> dict[str, Any]:
    """Minimal user MessageEvent shape (matches trace_reconstruction fixtures)."""
    return {
        "id": event_id,
        "kind": "MessageEvent",
        "source": "user",
        "timestamp": "2026-08-06T08:00:00Z",
        "llm_message": {
            "role": "user",
            "content": [{"type": "text", "text": text}],
        },
    }


def _assistant_msg(event_id: str = "evt-a-1") -> dict[str, Any]:
    return {
        "id": event_id,
        "kind": "MessageEvent",
        "source": "assistant",
        "timestamp": "2026-08-06T08:00:01Z",
        "llm_message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "hello back"}],
        },
    }


def _action(event_id: str = "evt-act-1") -> dict[str, Any]:
    return {
        "id": event_id,
        "kind": "ActionEvent",
        "source": "agent",
        "timestamp": "2026-08-06T08:00:02Z",
        "tool_name": "run_bash",
    }


# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------


class TestStampsCommitSha:
    def test_user_message_with_sha_hit_stamped(self):
        out = event_normalize.normalize_event(
            _user_msg("evt-user-1"),
            sha_lookup=lambda eid: "deadbeef" if eid == "evt-user-1" else None,
        )
        assert out["commit_sha_at_time_of_event"] == "deadbeef"
        # Other fields unchanged.
        assert out["id"] == "evt-user-1"
        assert out["type"] == "message"
        assert out["source"] == "user"

    def test_user_message_with_sha_miss_omits_key(self):
        out = event_normalize.normalize_event(
            _user_msg("evt-user-2"),
            sha_lookup=lambda eid: None,  # every lookup misses
        )
        assert "commit_sha_at_time_of_event" not in out

    def test_default_sha_lookup_none_keeps_shape_unchanged(self):
        # Baseline: no sha_lookup passed → pre-ADR-026 output shape.
        out = event_normalize.normalize_event(_user_msg("evt-user-3"))
        assert "commit_sha_at_time_of_event" not in out


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


class TestGuards:
    def test_assistant_message_never_stamped(self):
        out = event_normalize.normalize_event(
            _assistant_msg("evt-a-1"),
            sha_lookup=lambda eid: "would-be-wrong",
        )
        assert "commit_sha_at_time_of_event" not in out

    def test_agent_source_message_never_stamped(self):
        # Some fixtures use source="agent" instead of "assistant"; guard both.
        raw = _assistant_msg("evt-agent-1")
        raw["source"] = "agent"
        out = event_normalize.normalize_event(
            raw, sha_lookup=lambda eid: "would-be-wrong"
        )
        assert "commit_sha_at_time_of_event" not in out

    def test_action_event_never_stamped(self):
        out = event_normalize.normalize_event(
            _action("evt-act-1"),
            sha_lookup=lambda eid: "would-be-wrong",
        )
        assert "commit_sha_at_time_of_event" not in out

    def test_empty_event_id_skips_lookup(self):
        calls: list[str] = []

        def spy(eid: str) -> str | None:
            calls.append(eid)
            return "should-not-be-used"

        raw = _user_msg("")  # empty id
        out = event_normalize.normalize_event(raw, sha_lookup=spy)
        assert calls == [], f"sha_lookup was called with: {calls!r}"
        assert "commit_sha_at_time_of_event" not in out


# ---------------------------------------------------------------------------
# Plural form
# ---------------------------------------------------------------------------


class TestNormalizeEventsPlural:
    def test_batch_threads_lookup_and_stamps_only_user_msgs(self):
        sha_map = {
            "evt-user-A": "sha-A",
            "evt-user-B": "sha-B",
            "evt-a-1": "sha-should-be-ignored",  # assistant
            "evt-act-1": "sha-should-be-ignored",  # action
        }
        items = [
            _user_msg("evt-user-A"),
            _assistant_msg("evt-a-1"),
            _action("evt-act-1"),
            _user_msg("evt-user-B", text="second"),
        ]
        out = event_normalize.normalize_events(items, sha_lookup=sha_map.get)
        assert len(out) == 4
        assert out[0]["commit_sha_at_time_of_event"] == "sha-A"
        assert "commit_sha_at_time_of_event" not in out[1]
        assert "commit_sha_at_time_of_event" not in out[2]
        assert out[3]["commit_sha_at_time_of_event"] == "sha-B"

    def test_batch_filters_non_dict_items(self):
        items: list[Any] = [_user_msg("evt-user-C"), "not-a-dict", 42, None]
        out = event_normalize.normalize_events(
            items, sha_lookup=lambda eid: "sha-C"
        )
        assert len(out) == 1
        assert out[0]["commit_sha_at_time_of_event"] == "sha-C"

    def test_batch_default_sha_lookup_none_keeps_shape(self):
        out = event_normalize.normalize_events([_user_msg("evt-user-D")])
        assert len(out) == 1
        assert "commit_sha_at_time_of_event" not in out[0]
