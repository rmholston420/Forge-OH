"""Stage 6.3 — ``IdempotentToolExecutor`` mixin.

Wraps ``ToolExecutor.__call__`` with the Forge-OH exactly-once ledger.
Subclasses override ``_execute(action, conversation) -> ObservationT``;
the base ``__call__`` handles:

  1. Resolving ``conversation.id`` and ``conversation.state.leaf_event_id``.
  2. Calling ``POST /api/idempotency/check`` on the BFF.
  3. If already completed: return the cached observation (reconstructed
     from ``cached.result_json``) without invoking ``_execute``.
  4. Otherwise: run ``_execute``, then call ``POST /api/idempotency/mark``.

Design notes:

* We use a synchronous ``httpx.Client`` because SDK ``ToolExecutor.__call__``
  is synchronous per SDK v1.40.0.  This mirrors the ``_emit_to_bff``
  primitive in ``search_web`` and ``consult_memory``.
* Best-effort semantics on the ledger's HTTP side: a network failure
  when contacting BFF must NOT block execution — that would break the
  agent when BFF is temporarily down.  We log and proceed with
  execution (fail-open).  A crash after ``_execute`` but before ``mark``
  is still safe because ``INSERT OR IGNORE`` protects the second attempt
  once BFF is back.
* Reconstructing the observation from cached JSON requires the subclass
  to provide ``_observation_from_cached(cached_json)``.  Default
  behaviour reconstructs via the tool's declared ``ObservationT`` model.
* If ``conversation`` is None (e.g. an SDK unit-test invocation without
  a live conversation), the mixin bypasses the ledger and just calls
  ``_execute``.  Idempotency without a stable conversation id is
  meaningless.

The mixin does not know the ``tool_name`` — subclasses must expose it
via the class attribute ``TOOL_NAME``.  This keeps the mixin decoupled
from ``ToolDefinition.name`` (which lives on the tool, not the
executor).
"""

from __future__ import annotations

import logging
import os
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

import httpx

from openhands.sdk.tool.tool import ToolExecutor


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation


logger = logging.getLogger(__name__)


_BFF_URL_ENV = "FORGE_BFF_URL"
_BFF_URL_DEFAULT = "http://127.0.0.1:8081"
_LEDGER_TIMEOUT_S = 2.0


ActionT = TypeVar("ActionT")
ObservationT = TypeVar("ObservationT")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bff_url() -> str:
    return os.environ.get(_BFF_URL_ENV, _BFF_URL_DEFAULT).rstrip("/")


def _resolve_conversation_id(conversation: "BaseConversation | None") -> str | None:
    """Best-effort extraction of the conversation ID.

    Mirrors ``search_web._resolve_conversation_id``.  Kept as a private
    copy here rather than a cross-tool import so the mixin has no
    dependency on the search tool.
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


def _resolve_leaf_event_id(conversation: "BaseConversation | None") -> str | None:
    """Extract ``conversation.state.leaf_event_id`` if present.

    The SDK v1.40.0 ``ConversationState`` model exposes ``leaf_event_id``
    directly.  We return None if the state is missing or the leaf is
    None (fresh conversation); the ledger substitutes a "root" sentinel.
    """
    if conversation is None:
        return None
    state = getattr(conversation, "state", None)
    if state is None:
        return None
    raw = getattr(state, "leaf_event_id", None)
    if raw is None:
        return None
    return str(raw)


def _check_completed(
    conversation_id: str,
    leaf_event_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """POST /api/idempotency/check.

    Returns ``(completed, cached, key)``.  On network failure returns
    ``(False, None, None)`` (fail-open — execution proceeds).
    """
    try:
        with httpx.Client(timeout=_LEDGER_TIMEOUT_S) as client:
            resp = client.post(
                f"{_bff_url()}/api/idempotency/check",
                json={
                    "conversation_id": conversation_id,
                    "leaf_event_id": leaf_event_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning(
            "idempotency check failed for tool=%s conv=%s: %s",
            tool_name,
            conversation_id,
            exc,
        )
        return False, None, None
    if resp.status_code != 200:
        logger.warning(
            "idempotency check returned %s for tool=%s conv=%s: %s",
            resp.status_code,
            tool_name,
            conversation_id,
            resp.text[:200],
        )
        return False, None, None
    body = resp.json().get("data", {})
    return (
        bool(body.get("completed")),
        body.get("cached"),
        body.get("key"),
    )


def _mark_completed(
    conversation_id: str,
    leaf_event_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
    result_summary: str,
    result_json: Any,
) -> None:
    """POST /api/idempotency/mark.  Best-effort; logs and returns on error."""
    try:
        with httpx.Client(timeout=_LEDGER_TIMEOUT_S) as client:
            resp = client.post(
                f"{_bff_url()}/api/idempotency/mark",
                json={
                    "conversation_id": conversation_id,
                    "leaf_event_id": leaf_event_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result_summary": result_summary,
                    "result_json": result_json,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning(
            "idempotency mark failed for tool=%s conv=%s: %s",
            tool_name,
            conversation_id,
            exc,
        )
        return
    if resp.status_code != 200:
        logger.warning(
            "idempotency mark returned %s for tool=%s conv=%s: %s",
            resp.status_code,
            tool_name,
            conversation_id,
            resp.text[:200],
        )


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------


class IdempotentToolExecutor(ToolExecutor, Generic[ActionT, ObservationT]):
    """Base class for state-changing SDK tool executors.

    Subclass MUST set ``TOOL_NAME`` and implement:

      * ``_execute(action, conversation) -> ObservationT``
      * ``_observation_from_cached(cached_json) -> ObservationT``
      * ``_result_summary(observation) -> str``  (<=500 chars, no PII)
      * ``_observation_to_cached_json(observation) -> Any``  (JSON-safe)
    """

    TOOL_NAME: ClassVar[str] = ""

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abstractmethod
    def _execute(
        self, action: ActionT, conversation: "BaseConversation | None"
    ) -> ObservationT:
        """Perform the actual side effect and return an observation."""

    @abstractmethod
    def _observation_from_cached(self, cached_json: Any) -> ObservationT:
        """Reconstruct an observation from a cached JSON payload."""

    def _result_summary(self, observation: ObservationT) -> str:
        """Human-readable summary of the observation for the ledger row."""
        return str(observation)[:500]

    @abstractmethod
    def _observation_to_cached_json(self, observation: ObservationT) -> Any:
        """Serialize an observation to a JSON-safe payload for caching."""

    def _action_to_arguments(self, action: ActionT) -> dict[str, Any]:
        """Extract stable dict of arguments from the pydantic Action.

        Default: ``action.model_dump(mode='json', by_alias=False)`` for
        pydantic models; falls back to ``vars(action)`` otherwise.
        """
        dump = getattr(action, "model_dump", None)
        if callable(dump):
            return dump(mode="json", by_alias=False)
        return dict(vars(action))

    # ------------------------------------------------------------------
    # Executor entry point
    # ------------------------------------------------------------------

    def __call__(
        self,
        action: ActionT,
        conversation: "BaseConversation | None" = None,
    ) -> ObservationT:
        if not self.TOOL_NAME:
            raise RuntimeError(
                f"{type(self).__name__} did not set TOOL_NAME; refusing to "
                "run without a stable idempotency key.",
            )

        conversation_id = _resolve_conversation_id(conversation)
        if conversation_id is None:
            logger.info(
                "%s: no conversation id; bypassing idempotency ledger.",
                self.TOOL_NAME,
            )
            return self._execute(action, conversation)

        leaf_event_id = _resolve_leaf_event_id(conversation)
        arguments = self._action_to_arguments(action)

        completed, cached, _key = _check_completed(
            conversation_id=conversation_id,
            leaf_event_id=leaf_event_id,
            tool_name=self.TOOL_NAME,
            arguments=arguments,
        )
        if completed and cached is not None and cached.get("result_json") is not None:
            logger.info(
                "%s: ledger hit for conv=%s leaf=%s — returning cached observation.",
                self.TOOL_NAME,
                conversation_id,
                leaf_event_id,
            )
            return self._observation_from_cached(cached["result_json"])

        observation = self._execute(action, conversation)

        _mark_completed(
            conversation_id=conversation_id,
            leaf_event_id=leaf_event_id,
            tool_name=self.TOOL_NAME,
            arguments=arguments,
            result_summary=self._result_summary(observation),
            result_json=self._observation_to_cached_json(observation),
        )
        return observation
