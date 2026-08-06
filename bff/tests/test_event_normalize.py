"""Tests for bff.services.event_normalize.

Stage 3.1 adds security_risk surfacing on ActionEvents. Only known
SecurityRisk enum values (UNKNOWN/LOW/MEDIUM/HIGH) are passed through;
absent/invalid values are dropped so the frontend can hide the badge.
"""

from bff.services.event_normalize import normalize_event, normalize_events


def _action(**extra):
    """Minimal ActionEvent-shaped dict."""
    base = {
        "id": "e1",
        "kind": "ActionEvent",
        "timestamp": "2026-08-05T22:00:00Z",
        "source": "agent",
        "summary": "run rm -rf /tmp/x",
        "tool_name": "terminal",
        "action": {"command": "rm -rf /tmp/x"},
    }
    base.update(extra)
    return base


class TestNormalizeEvent:
    def test_actionevent_without_security_risk_omits_key(self):
        out = normalize_event(_action())
        assert "securityRisk" not in out

    def test_actionevent_with_high_risk(self):
        out = normalize_event(_action(security_risk="HIGH"))
        assert out["securityRisk"] == "HIGH"
        assert out["type"] == "action"

    def test_actionevent_with_low_risk(self):
        out = normalize_event(_action(security_risk="LOW"))
        assert out["securityRisk"] == "LOW"

    def test_actionevent_with_medium_risk(self):
        out = normalize_event(_action(security_risk="MEDIUM"))
        assert out["securityRisk"] == "MEDIUM"

    def test_actionevent_with_unknown_risk_passes_through(self):
        """UNKNOWN is a valid enum value; frontend decides to hide the badge."""
        out = normalize_event(_action(security_risk="UNKNOWN"))
        assert out["securityRisk"] == "UNKNOWN"

    def test_actionevent_with_invalid_risk_string_dropped(self):
        out = normalize_event(_action(security_risk="CATASTROPHIC"))
        assert "securityRisk" not in out

    def test_actionevent_with_enum_valued_object(self):
        """Some SDK paths may emit the raw enum member; we accept its .value."""

        class _FakeEnum:
            value = "HIGH"

        out = normalize_event(_action(security_risk=_FakeEnum()))
        assert out["securityRisk"] == "HIGH"

    def test_messageevent_does_not_get_security_risk_even_if_present(self):
        """security_risk only makes sense on ActionEvents."""
        msg = {
            "id": "m1",
            "kind": "MessageEvent",
            "timestamp": "2026-08-05T22:00:00Z",
            "security_risk": "HIGH",  # ignored — wrong event kind
            "llm_message": {"content": [{"text": "hi"}]},
        }
        out = normalize_event(msg)
        assert "securityRisk" not in out

    def test_non_dict_input(self):
        assert normalize_event("not a dict")["type"] == "unknown"  # type: ignore[arg-type]

    def test_normalize_events_filters_non_dicts(self):
        items = [_action(security_risk="LOW"), "junk", None, _action()]
        out = normalize_events(items)  # type: ignore[arg-type]
        assert len(out) == 2
        assert out[0]["securityRisk"] == "LOW"
        assert "securityRisk" not in out[1]
