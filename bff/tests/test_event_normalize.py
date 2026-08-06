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


class TestSerenaLSPNormalization:
    """Stage 4.4 — ActionEvents whose tool_name matches a known Serena
    LSP tool should get their `type` promoted to `lsp_<op>` and, when no
    explicit summary is provided, a compact "Serena <op>: <symbol>" line."""

    def test_bare_find_symbol_promotes_type_to_lsp_find_symbol(self):
        ev = _action(
            summary=None,
            tool_name="find_symbol",
            action={"name_path": "MyClass/foo"},
        )
        # _action injects "summary"; nulling it forces the LSP branch.
        ev.pop("summary", None)
        out = normalize_event(ev)
        assert out["type"] == "lsp_find_symbol"
        assert out["summary"] == "Serena find_symbol: MyClass/foo"

    def test_namespaced_tool_name_still_matches(self):
        """`mcp.serena.find_referencing_symbols` matches on the tail segment."""
        ev = _action(
            tool_name="mcp.serena.find_referencing_symbols",
            action={"name_path": "foo"},
        )
        ev.pop("summary", None)
        out = normalize_event(ev)
        assert out["type"] == "lsp_find_referencing_symbols"

    def test_explicit_summary_wins_over_lsp_reformat(self):
        """If agent-server sets `summary`, we preserve it verbatim
        even for LSP tools \u2014 but the `type` is still promoted."""
        ev = _action(
            summary="Renaming foo -> bar",
            tool_name="replace_symbol_body",
            action={"name_path": "foo"},
        )
        out = normalize_event(ev)
        assert out["type"] == "lsp_replace_symbol_body"
        assert out["summary"] == "Renaming foo -> bar"

    def test_non_serena_tool_stays_generic_action(self):
        ev = _action(tool_name="terminal", action={"command": "ls"})
        out = normalize_event(ev)
        assert out["type"] == "action"

    def test_missing_tool_name_stays_generic_action(self):
        ev = _action(tool_name=None, action={})
        out = normalize_event(ev)
        assert out["type"] == "action"

    def test_lsp_summary_without_symbol_falls_back_to_op_only(self):
        ev = _action(
            tool_name="get_symbols_overview",
            action={},
        )
        ev.pop("summary", None)
        out = normalize_event(ev)
        assert out["type"] == "lsp_get_symbols_overview"
        assert out["summary"] == "Serena get_symbols_overview"


class TestMemoryConsultationNormalization:
    """Stage 5.6a / ADR-024 — memory-tier consultation event projection."""

    def _raw(self, **extra):
        base = {
            "id": "mem-1",
            "kind": "MemoryConsultationEvent",
            "timestamp": "2026-08-06T03:00:00+00:00",
            "source": "memory",
            "tier": "semantic",
            "query": "colossus",
            "result_count": 3,
        }
        base.update(extra)
        return base

    def test_kind_maps_to_memory_consultation_type(self):
        assert normalize_event(self._raw())["type"] == "memory_consultation"

    def test_summary_renders_tier_query_and_count(self):
        out = normalize_event(self._raw())
        assert out["summary"] == 'Memory consulted (semantic): "colossus" — 3 result(s)'

    def test_source_passes_through(self):
        assert normalize_event(self._raw())["source"] == "memory"

    def test_raw_preserved(self):
        out = normalize_event(self._raw())
        assert out["raw"]["tier"] == "semantic"
        assert out["raw"]["query"] == "colossus"
        assert out["raw"]["result_count"] == 3

    def test_missing_query_uses_fallback_text(self):
        raw = self._raw()
        del raw["query"]
        out = normalize_event(raw)
        assert "(query)" in out["summary"]

    def test_missing_result_count_uses_em_dash(self):
        raw = self._raw()
        del raw["result_count"]
        out = normalize_event(raw)
        assert "—" in out["summary"]

    def test_bool_result_count_rejected_as_numeric(self):
        # bool is int subclass in Python — the summary MUST NOT format it
        # as "1 result(s)"; it should render as em-dash.
        raw = self._raw(result_count=True)
        out = normalize_event(raw)
        assert "1 result(s)" not in out["summary"]
        assert "—" in out["summary"]

    def test_explicit_summary_overrides_render(self):
        raw = self._raw(summary="custom marker")
        out = normalize_event(raw)
        assert out["summary"] == "custom marker"

    def test_no_security_risk_key_added(self):
        # securityRisk is ActionEvent-only; MemoryConsultationEvent must not
        # accidentally acquire it.
        assert "securityRisk" not in normalize_event(self._raw())
