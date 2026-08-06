"""Unit tests for ``progressive_disclosure`` — list_tool_stubs + get_tool_schema.

These tests import the module (which registers the two tools as a side
effect), then exercise the executors directly against the real SDK tool
registry.  We do not depend on any specific set of registered tools
beyond the two this module itself contributes.
"""

from __future__ import annotations

import pytest

from openhands.sdk.tool.registry import list_registered_tools
from openhands_tools_ext.tool_invocation import progressive_disclosure as pd


def test_module_registers_two_tools() -> None:
    registered = set(list_registered_tools())
    assert "list_tool_stubs" in registered
    assert "get_tool_schema" in registered


def test_first_line_helper() -> None:
    assert pd._first_line("") == ""
    assert pd._first_line("   \n\n   \nhello world\nsecond") == "hello world"
    long = "x" * 500
    assert len(pd._first_line(long, max_chars=100)) == 100


def test_list_tool_stubs_executor_returns_sorted_rows_with_descriptions() -> None:
    executor = pd.ListToolStubsExecutor()
    obs = executor(pd.ListToolStubsAction(), conversation=None)

    names = [row["name"] for row in obs.stubs]
    assert names == sorted(names), "stubs must be sorted alphabetically"
    assert "list_tool_stubs" in names
    assert "get_tool_schema" in names

    # get_tool_schema is defined in this module — its own stub should be
    # non-empty (its first description line).
    schema_row = next(r for r in obs.stubs if r["name"] == "get_tool_schema")
    assert schema_row["description"].startswith("Load the full JSON schema")


def test_get_tool_schema_returns_canonical_shape_for_known_tool() -> None:
    executor = pd.GetToolSchemaExecutor()
    obs = executor(pd.GetToolSchemaAction(name="list_tool_stubs"), conversation=None)

    assert obs.found is True
    assert obs.name == "list_tool_stubs"
    assert obs.description  # non-empty
    # Canonical MCP shape from ToolDefinition.to_mcp_tool()
    assert obs.schema_json.get("name") == "list_tool_stubs"
    assert "inputSchema" in obs.schema_json
    # readOnlyHint is set True in the tool's annotations
    annotations = obs.schema_json.get("annotations")
    if annotations is not None:  # SDK may return the pydantic model or a dict
        read_only = (
            annotations.readOnlyHint
            if hasattr(annotations, "readOnlyHint")
            else annotations.get("readOnlyHint")
        )
        assert read_only is True


def test_get_tool_schema_returns_not_found_for_unknown_tool() -> None:
    executor = pd.GetToolSchemaExecutor()
    obs = executor(
        pd.GetToolSchemaAction(name="tool_that_definitely_does_not_exist_zzz"),
        conversation=None,
    )
    assert obs.found is False
    assert obs.schema_json == {}
    assert obs.description == ""


def test_get_tool_schema_rejects_empty_name() -> None:
    # Pydantic min_length=1 should reject empty strings at construction time.
    with pytest.raises(Exception):  # noqa: BLE001 — either ValidationError
        pd.GetToolSchemaAction(name="")
