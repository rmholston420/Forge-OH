"""``consult_memory`` OpenHands tool — Stage 5.6b live caller of Forge-OH's
semantic memory tier.

Contract (ADR-024 follow-up, plan §5.6.1/§5.6.4):

* Agent calls the tool with ``{tier, query, limit?}``.
* Executor drives ``MemoryPort.search_semantic`` for the ``semantic`` tier;
  ``temporal`` and ``episodic`` tiers raise ``NotImplementedError`` with a
  clear defer-to-later-stage message.
* On success (any result count, including zero) the executor POSTs to the
  BFF's ``/api/memory/emit-consultation`` endpoint so the frontend timeline
  gets a ``memory_consultation`` marker. Emit is best-effort — a failing
  BFF never breaks the tool call. This is the process-boundary bridge
  ADR-024 D6 anticipates: the tool runs inside agent-server (:8090) and
  the BFF (:8081) owns Socket.IO, so a plain HTTP call is the only path.
* Executor is synchronous per SDK v1.40.0 ``ToolExecutor.__call__``. The
  underlying MemoryPort is fully async, so we drive it via ``asyncio.run``.
  We never share a loop across invocations; each call is self-contained.

The tool is registered at import time via ``register_tool``; add
``--import-modules openhands_tools_ext.memory.tools.consult_memory`` to
the agent-server launch (see ``scripts/forge-up.sh``).
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Self

import httpx
from pydantic import Field
from rich.text import Text

from openhands.sdk.tool.registry import register_tool
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
# Configuration
# ---------------------------------------------------------------------------

_SUPPORTED_TIERS = frozenset({"semantic"})
"""Tiers this tool currently supports. See module docstring for defer scope."""

_BFF_URL_ENV = "FORGE_BFF_URL"
_BFF_URL_DEFAULT = "http://127.0.0.1:8081"
_EMIT_TIMEOUT_S = 2.0
"""Total budget for the best-effort emit POST. Short — the tool result is
what matters; the timeline marker is a UI convenience."""


def _bff_url() -> str:
    """Resolve the BFF base URL from env with a Colossus-friendly default."""
    return os.environ.get(_BFF_URL_ENV, _BFF_URL_DEFAULT).rstrip("/")


def _resolve_conversation_id(conversation: "BaseConversation | None") -> str | None:
    """Best-effort extraction of the conversation ID for the emit payload.

    Different SDK versions have exposed the id under different attribute
    names (``id``, ``conversation_id``, ``state.id``). We try each in turn
    and return ``None`` if none are usable — the emit is skipped rather
    than failing.
    """
    if conversation is None:
        return None
    for attr in ("id", "conversation_id"):
        raw = getattr(conversation, attr, None)
        if raw:
            # Some SDKs use uuid.UUID; force to str for the wire.
            return str(raw)
    state = getattr(conversation, "state", None)
    if state is not None:
        for attr in ("id", "conversation_id"):
            raw = getattr(state, attr, None)
            if raw:
                return str(raw)
    return None


# ---------------------------------------------------------------------------
# Action / Observation
# ---------------------------------------------------------------------------


class ConsultMemoryAction(Action):
    """Query one memory tier and surface results to the agent."""

    tier: str = Field(
        description=(
            "Memory tier to consult. Currently only 'semantic' is supported "
            "(vector-similarity retrieval via DozerDB + Qdrant + Ollama "
            "embeddings). Future tiers: 'temporal', 'episodic'."
        )
    )
    query: str = Field(
        description=(
            "Natural-language query. For the semantic tier the string is "
            "embedded and used for nearest-neighbour retrieval."
        )
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of memory hits to return (1..50).",
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("🧠 ", style="magenta")
        content.append("Consult memory ", style="bold magenta")
        content.append(f"[{self.tier}] ", style="dim")
        content.append(self.query, style="italic")
        return content


class ConsultMemoryObservation(Observation):
    """Result of a memory consultation returned to the agent."""

    tier: str
    query: str
    result_count: int = Field(ge=0)
    hits: list[dict[str, Any]] = Field(default_factory=list)
    emitted: bool = Field(
        default=False,
        description=(
            "Whether the timeline emit POST to the BFF succeeded. "
            "False is non-fatal — the tool result is authoritative."
        ),
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append(
            f"Memory consulted ({self.tier}): ", style="bold magenta"
        )
        content.append(f'"{self.query}" ', style="italic")
        content.append(
            f"— {self.result_count} result(s)", style="dim"
        )
        return content


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


async def _run_semantic(query: str, limit: int) -> list[dict[str, Any]]:
    """Drive the composed MemoryPort's semantic tier and project hits.

    Kept as a module-level coroutine so tests can patch it directly with
    ``monkeypatch.setattr`` without instantiating the executor.
    """
    from openhands_tools_ext.memory.composition import make_memory_adapter

    port = make_memory_adapter()
    try:
        hits = await port.search_semantic(query, limit=limit)
    finally:
        await port.close()
    projected: list[dict[str, Any]] = []
    for h in hits:
        projected.append(
            {
                "id": h.id,
                "score": h.score,
                "payload": dict(h.payload) if h.payload else {},
            }
        )
    return projected


def _emit_to_bff(
    *,
    conversation_id: str,
    tier: str,
    query: str,
    result_count: int,
) -> bool:
    """Best-effort HTTP POST to ``/api/memory/emit-consultation``.

    Never raises. Returns True iff the BFF confirmed 2xx.
    """
    url = f"{_bff_url()}/api/memory/emit-consultation"
    payload = {
        "runId": conversation_id,
        "tier": tier,
        "query": query,
        "resultCount": result_count,
    }
    try:
        with httpx.Client(timeout=_EMIT_TIMEOUT_S) as client:
            resp = client.post(url, json=payload)
    except Exception as exc:  # pragma: no cover - network noise
        logger.warning(
            "consult_memory: emit to BFF failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        return False
    if resp.status_code // 100 != 2:
        logger.warning(
            "consult_memory: emit to BFF returned %s: %s",
            resp.status_code,
            resp.text[:200],
        )
        return False
    return True


class ConsultMemoryExecutor(ToolExecutor):
    """Synchronous SDK executor that drives the async MemoryPort."""

    def __call__(
        self,
        action: ConsultMemoryAction,
        conversation: "BaseConversation | None" = None,
    ) -> ConsultMemoryObservation:
        tier = action.tier
        if tier not in _SUPPORTED_TIERS:
            raise NotImplementedError(
                f"consult_memory: tier '{tier}' is not supported yet. "
                f"Supported tiers: {sorted(_SUPPORTED_TIERS)}. "
                "Temporal and episodic tiers are planned for a later stage."
            )

        # Semantic tier — drive the port synchronously via asyncio.run.
        # asyncio.run raises RuntimeError if a loop is already running in
        # this thread; the SDK dispatches tool calls from a synchronous
        # worker frame so this is the correct primitive.
        hits = asyncio.run(_run_semantic(action.query, action.limit))
        result_count = len(hits)

        conversation_id = _resolve_conversation_id(conversation)
        emitted = False
        if conversation_id:
            emitted = _emit_to_bff(
                conversation_id=conversation_id,
                tier=tier,
                query=action.query,
                result_count=result_count,
            )
        else:
            logger.info(
                "consult_memory: no conversation id available; skipping "
                "timeline emit (result_count=%d)",
                result_count,
            )

        return ConsultMemoryObservation(
            tier=tier,
            query=action.query,
            result_count=result_count,
            hits=hits,
            emitted=emitted,
        )


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------


CONSULT_MEMORY_DESCRIPTION = """Consult Forge-OH's memory subsystem for prior knowledge.

Use when you need to check what has already been recorded about a topic,
entity, or decision before answering. The tool queries the semantic memory
tier by embedding your query and returning the most similar stored triples
with their provenance and confidence.

Parameters:
- tier:  "semantic" (only supported tier at the moment)
- query: natural-language string
- limit: max hits to return (1..50, default 5)

Returns a list of {id, score, payload} objects. Payload includes the
stored triple (subject/predicate/object), provenance, and confidence.
"""


class ConsultMemoryTool(
    ToolDefinition[ConsultMemoryAction, ConsultMemoryObservation]
):
    """OpenHands tool wrapper for Forge-OH's semantic memory consultation."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,  # noqa: ARG003
        **params: Any,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(
                "ConsultMemoryTool does not accept factory parameters "
                f"(got {sorted(params)})"
            )
        return [
            cls(
                action_type=ConsultMemoryAction,
                observation_type=ConsultMemoryObservation,
                description=CONSULT_MEMORY_DESCRIPTION,
                executor=ConsultMemoryExecutor(),
                annotations=ToolAnnotations(
                    title="consult_memory",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


# Import-time side effect — the SDK's tool registry keys tools by name; the
# agent-server preloads this module via ``--import-modules`` so the name is
# resolvable before any conversation starts.
register_tool("consult_memory", ConsultMemoryTool)
