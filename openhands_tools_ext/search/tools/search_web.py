"""``search_web`` OpenHands tool — Stage 6.1 live caller of Forge-OH's SearXNG adapter.

Contract (docs/reconciliation-plan-stage-6.md §6.1):

* Agent calls the tool with ``{query, num_results?, language?, engines?}``.
* Executor drives ``SearchPort.search`` via the composed SearXNG adapter
  (``get_searxng_adapter``). Empty result sets are allowed; the adapter
  never raises on backend failure (returns empty results with provenance).
* On success (any result count, including zero) the executor POSTs to the
  BFF's ``/api/search/emit`` endpoint so the frontend timeline gets a
  ``web_search`` marker. Emit is best-effort — a failing BFF never breaks
  the tool call. This mirrors the ADR-024 D6 process-boundary bridge used
  by ``consult_memory``: the tool runs inside agent-server (:8090) and
  the BFF (:8081) owns Socket.IO, so a plain HTTP call is the only path.
* Executor is synchronous per SDK v1.40.0 ``ToolExecutor.__call__``. The
  underlying SearchPort is fully async, so we drive it via ``asyncio.run``.
  We never share a loop across invocations; each call is self-contained.

The tool is registered at import time via ``register_tool``; add
``--import-modules openhands_tools_ext.search.tools.search_web`` to the
agent-server launch (see ``scripts/forge-up.sh``).
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

    Mirrors ``openhands_tools_ext.memory.tools.consult_memory``.
    """
    if conversation is None:
        return None
    for attr in ("id", "conversation_id"):
        raw = getattr(conversation, attr, None)
        if raw:
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


class SearchWebAction(Action):
    """Run a web search via the composed SearXNG adapter."""

    query: str = Field(
        description=(
            "Natural-language web-search query. Sent verbatim to SearXNG "
            "(with ``format=json``)."
        )
    )
    num_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of ranked results to return (1..50).",
    )
    language: str = Field(
        default="en",
        description="ISO-639-1 language code hint forwarded to SearXNG.",
    )
    engines: list[str] | None = Field(
        default=None,
        description=(
            "Optional list of SearXNG engine names to restrict to "
            "(e.g. ['duckduckgo', 'brave']). Adapter may ignore if the "
            "engine is not configured on the local instance."
        ),
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("🔍 ", style="cyan")
        content.append("Search web ", style="bold cyan")
        content.append(self.query, style="italic")
        return content


class SearchWebObservation(Observation):
    """Result of a web-search consultation returned to the agent."""

    query: str
    result_count: int = Field(ge=0)
    provenance: str
    latency_ms: int = Field(ge=0)
    results: list[dict[str, Any]] = Field(default_factory=list)
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
        content.append("Web searched: ", style="bold cyan")
        content.append(f'"{self.query}" ', style="italic")
        content.append(f"— {self.result_count} result(s)", style="dim")
        return content


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


async def _run_search(
    query: str,
    num_results: int,
    language: str,
    engines: list[str] | None,
) -> tuple[list[dict[str, Any]], str, int]:
    """Drive the composed SearXNG adapter and project hits.

    Kept as a module-level coroutine so tests can patch it directly with
    ``monkeypatch.setattr`` without instantiating the executor.

    Returns:
        (projected_hits, provenance, latency_ms)
    """
    from openhands_tools_ext.search.adapters.searxng import get_searxng_adapter

    adapter = get_searxng_adapter()
    resp = await adapter.search(
        query,
        num_results=num_results,
        language=language,
        engines=engines,
    )
    projected: list[dict[str, Any]] = [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "engine": r.engine,
            "score": r.score,
        }
        for r in resp.results
    ]
    return projected, resp.provenance, resp.latency_ms


def _emit_to_bff(
    *,
    conversation_id: str,
    query: str,
    result_count: int,
    provenance: str,
    latency_ms: int,
) -> bool:
    """Best-effort HTTP POST to ``/api/search/emit``.

    Never raises. Returns True iff the BFF confirmed 2xx.
    """
    url = f"{_bff_url()}/api/search/emit"
    payload = {
        "runId": conversation_id,
        "query": query,
        "resultCount": result_count,
        "provenance": provenance,
        "latencyMs": latency_ms,
    }
    try:
        with httpx.Client(timeout=_EMIT_TIMEOUT_S) as client:
            resp = client.post(url, json=payload)
    except Exception as exc:  # pragma: no cover - network noise
        logger.warning(
            "search_web: emit to BFF failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        return False
    if resp.status_code // 100 != 2:
        logger.warning(
            "search_web: emit to BFF returned %s: %s",
            resp.status_code,
            resp.text[:200],
        )
        return False
    return True


class SearchWebExecutor(ToolExecutor):
    """Synchronous SDK executor that drives the async SearchPort."""

    def __call__(
        self,
        action: SearchWebAction,
        conversation: "BaseConversation | None" = None,
    ) -> SearchWebObservation:
        # Drive the port synchronously via asyncio.run. The SDK dispatches
        # tool calls from a synchronous worker frame so this is the correct
        # primitive (see consult_memory for the same pattern).
        hits, provenance, latency_ms = asyncio.run(
            _run_search(
                action.query,
                action.num_results,
                action.language,
                action.engines,
            )
        )
        result_count = len(hits)

        conversation_id = _resolve_conversation_id(conversation)
        emitted = False
        if conversation_id:
            emitted = _emit_to_bff(
                conversation_id=conversation_id,
                query=action.query,
                result_count=result_count,
                provenance=provenance,
                latency_ms=latency_ms,
            )
        else:
            logger.info(
                "search_web: no conversation id available; skipping "
                "timeline emit (result_count=%d)",
                result_count,
            )

        return SearchWebObservation(
            query=action.query,
            result_count=result_count,
            provenance=provenance,
            latency_ms=latency_ms,
            results=hits,
            emitted=emitted,
        )


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------


SEARCH_WEB_DESCRIPTION = """Search the web via Forge-OH's local SearXNG instance.

Use when you need current information from the open web (documentation,
news, forum threads, package metadata) that is not in your training data
or the local memory. The tool queries the local SearXNG at
``FORGE_SEARXNG_BASE_URL`` (default ``http://127.0.0.1:18888``) and
returns ranked results with URL, title, snippet, and provenance.

Parameters:
- query:       natural-language search query (required)
- num_results: max hits (1..50, default 10)
- language:    ISO-639-1 code (default "en")
- engines:     optional restriction list (e.g. ["duckduckgo", "brave"])

Returns {query, result_count, provenance, latency_ms, results[]}. Each
result is {title, url, snippet, engine, score}. Provenance is
"searxng:<base_url>" and MUST be forwarded verbatim when writing search
findings into MemoryPort.
"""


class SearchWebTool(ToolDefinition[SearchWebAction, SearchWebObservation]):
    """OpenHands tool wrapper for Forge-OH's local SearXNG web search."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,  # noqa: ARG003
        **params: Any,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(
                "SearchWebTool does not accept factory parameters "
                f"(got {sorted(params)})"
            )
        return [
            cls(
                action_type=SearchWebAction,
                observation_type=SearchWebObservation,
                description=SEARCH_WEB_DESCRIPTION,
                executor=SearchWebExecutor(),
                annotations=ToolAnnotations(
                    title="search_web",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=False,
                    openWorldHint=True,
                ),
            )
        ]


# Import-time side effect — the SDK's tool registry keys tools by name;
# the agent-server preloads this module via ``--import-modules`` so the
# name is resolvable before any conversation starts.
register_tool("search_web", SearchWebTool)
