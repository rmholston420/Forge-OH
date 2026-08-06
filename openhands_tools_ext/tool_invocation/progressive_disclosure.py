"""Progressive-disclosure SDK tools: ``list_tool_stubs`` and ``get_tool_schema``.

Rationale (see ADR 013): at session start the agent only needs to know
*what tools exist* (name + one-line description) — the full JSON schemas
are dead weight until the agent decides to call a specific tool.  Loading
schemas lazily is a materially large context-window win on tool-heavy
runs.

Design:
  * ``list_tool_stubs`` returns ``[(name, description_first_line), …]`` for
    every currently-registered tool.  Cheap: a single pass over the SDK's
    global registry with a text-truncation step.
  * ``get_tool_schema`` resolves one registered tool by name and returns
    its canonical MCP schema (via ``ToolDefinition.to_mcp_tool``), giving
    the agent everything it needs to construct a valid call.
  * Both tools are read-only against the tool registry.  No side effects.

Registration is at module import — the agent-server preloads this module
via ``--import-modules``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field

from openhands.sdk.tool.registry import (
    list_registered_tools,
    register_tool,
    resolve_tool,
)
from openhands.sdk.tool.spec import Tool
from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation
    from openhands.sdk.conversation.state import ConversationState


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers (also used by unit tests)
# ---------------------------------------------------------------------------


def _first_line(text: str, max_chars: int = 200) -> str:
    """Return the first non-empty line of ``text``, capped at ``max_chars``."""
    if not text:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:max_chars]
    return ""


def _resolve_one(
    name: str, conv_state: "ConversationState | None"
) -> ToolDefinition | None:
    """Resolve a single registered tool name to its first ToolDefinition.

    Returns None if the tool is not registered or its resolver fails.
    ``conv_state=None`` is tolerated: the SDK resolver signature requires a
    ``ConversationState`` but most stateless tools ignore it.  Callers who
    hit resolver failure log-and-skip.
    """
    try:
        # The resolver signature is (params, conv_state) -> Sequence[Tool].
        # We use empty params.
        tools = resolve_tool(Tool(name=name), conv_state)  # type: ignore[arg-type]
    except KeyError:
        return None
    except Exception as exc:  # noqa: BLE001 — narrow catch would miss a lot
        logger.warning(
            "progressive_disclosure: resolver for %s raised %s; skipping",
            name,
            type(exc).__name__,
        )
        return None
    return tools[0] if tools else None


# ---------------------------------------------------------------------------
# list_tool_stubs
# ---------------------------------------------------------------------------


class ListToolStubsAction(Action):
    """No parameters.  Returns every registered tool as (name, one-liner)."""


class ListToolStubsObservation(Observation):
    stubs: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of {name, description} rows.",
    )

    @property
    def agent_observation(self) -> Sequence[Any]:  # pragma: no cover
        return ()


class ListToolStubsExecutor(ToolExecutor[ListToolStubsAction, ListToolStubsObservation]):
    """Enumerate the SDK tool registry with truncated descriptions."""

    def __call__(
        self,
        action: ListToolStubsAction,
        conversation: "BaseConversation | None" = None,
    ) -> ListToolStubsObservation:
        conv_state = getattr(conversation, "state", None) if conversation else None

        rows: list[dict[str, str]] = []
        for name in list_registered_tools():
            tool = _resolve_one(name, conv_state)
            if tool is None:
                # Registered but unresolvable — surface the name only so the
                # agent knows it exists.
                rows.append({"name": name, "description": ""})
                continue
            rows.append(
                {
                    "name": name,
                    "description": _first_line(tool.description or ""),
                }
            )

        rows.sort(key=lambda r: r["name"])
        return ListToolStubsObservation(stubs=rows)


LIST_TOOL_STUBS_DESCRIPTION = """List every registered tool as (name, one-line-description).

Use this at the start of a session — or whenever you're unsure which tool
solves a subproblem — to discover tool names cheaply. Full JSON schemas
are NOT included; call ``get_tool_schema`` for the tools you actually
plan to invoke.

Parameters: none.

Returns {stubs: [{name, description}, …]}, sorted by name.
"""


class ListToolStubsTool(ToolDefinition[ListToolStubsAction, ListToolStubsObservation]):
    """SDK tool wrapper for :class:`ListToolStubsExecutor`."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,  # noqa: ARG003
        **params: Any,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(
                "ListToolStubsTool does not accept factory parameters "
                f"(got {sorted(params)})"
            )
        return [
            cls(
                action_type=ListToolStubsAction,
                observation_type=ListToolStubsObservation,
                description=LIST_TOOL_STUBS_DESCRIPTION,
                executor=ListToolStubsExecutor(),
                annotations=ToolAnnotations(
                    title="list_tool_stubs",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


# ---------------------------------------------------------------------------
# get_tool_schema
# ---------------------------------------------------------------------------


class GetToolSchemaAction(Action):
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Registered tool name to load the full schema for.",
    )


class GetToolSchemaObservation(Observation):
    name: str
    found: bool
    description: str = ""
    mcp_schema: dict[str, Any] = Field(default_factory=dict)

    @property
    def agent_observation(self) -> Sequence[Any]:  # pragma: no cover
        return ()


class GetToolSchemaExecutor(ToolExecutor[GetToolSchemaAction, GetToolSchemaObservation]):
    """Return the canonical MCP schema for one registered tool."""

    def __call__(
        self,
        action: GetToolSchemaAction,
        conversation: "BaseConversation | None" = None,
    ) -> GetToolSchemaObservation:
        conv_state = getattr(conversation, "state", None) if conversation else None
        tool = _resolve_one(action.name, conv_state)
        if tool is None:
            return GetToolSchemaObservation(name=action.name, found=False)
        return GetToolSchemaObservation(
            name=action.name,
            found=True,
            description=tool.description or "",
            mcp_schema=tool.to_mcp_tool(),
        )


GET_TOOL_SCHEMA_DESCRIPTION = """Load the full JSON schema for one registered tool.

Use this AFTER ``list_tool_stubs`` when you've picked the tool you want
to invoke and need its parameter names, types, and descriptions.  Load
schemas on demand — pulling the full schema for every tool at session
start burns tokens on schemas you never use.

Parameters:
- name: The exact registered name of the tool (from ``list_tool_stubs``).

Returns {name, found, description, mcp_schema}.  ``found=false`` and an
empty schema mean the tool is not currently registered.
"""


class GetToolSchemaTool(ToolDefinition[GetToolSchemaAction, GetToolSchemaObservation]):
    """SDK tool wrapper for :class:`GetToolSchemaExecutor`."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,  # noqa: ARG003
        **params: Any,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(
                "GetToolSchemaTool does not accept factory parameters "
                f"(got {sorted(params)})"
            )
        return [
            cls(
                action_type=GetToolSchemaAction,
                observation_type=GetToolSchemaObservation,
                description=GET_TOOL_SCHEMA_DESCRIPTION,
                executor=GetToolSchemaExecutor(),
                annotations=ToolAnnotations(
                    title="get_tool_schema",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


register_tool("list_tool_stubs", ListToolStubsTool)
register_tool("get_tool_schema", GetToolSchemaTool)
