"""``write_note`` — Stage 6.3 synthetic state-changing tool.

Purpose: exercise the exactly-once idempotency ledger on a real
side-effecting code path.  Writes a single plain-text note to
``data/notes/<slug>.txt`` under the Forge-OH data directory.

Design:
  * Extends ``IdempotentToolExecutor`` — every call is gated through
    the ledger; a replayed call with identical arguments is returned
    from cache and does NOT re-write the file.
  * Deterministic filename: ``sha256(title)[:16] + '.txt'`` under
    ``data/notes/``.  This keeps replay-safety honest: even if the
    ledger were bypassed, two identical calls would target the same
    file rather than accumulate separate copies (belt-and-braces).
  * Body is written atomically via ``os.replace`` of a tempfile so a
    crash mid-write leaves either the old file or no file, never a
    partial one.

Registration:
  ``register_tool("write_note", WriteNoteTool)`` at import time.  Add
  ``--import-modules openhands_tools_ext.write.tools.write_note`` to
  the agent-server launch line.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field

from openhands.sdk.tool.registry import register_tool
from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
)

from openhands_tools_ext.common.idempotent_executor import IdempotentToolExecutor


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation
    from openhands.sdk.conversation.state import ConversationState


logger = logging.getLogger(__name__)


NOTES_DIR_ENV = "FORGE_NOTES_DIR"
NOTES_DIR_DEFAULT = "data/notes"


def _notes_dir() -> Path:
    return Path(os.environ.get(NOTES_DIR_ENV, NOTES_DIR_DEFAULT))


def _slug(title: str) -> str:
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Action / Observation
# ---------------------------------------------------------------------------


class WriteNoteAction(Action):
    """Persist a short plain-text note under the Forge-OH data directory."""

    title: str = Field(
        min_length=1,
        max_length=200,
        description="Note title (used to derive the filename slug).",
    )
    body: str = Field(
        default="",
        max_length=100_000,
        description="Note body.  UTF-8 plain text; up to 100k chars.",
    )


class WriteNoteObservation(Observation):
    title: str
    path: str
    bytes_written: int
    idempotent_replay: bool = False

    @property
    def agent_observation(self) -> Sequence[Any]:  # pragma: no cover
        # SDK convention: the value the agent sees is a compact string.
        # Return an empty sequence — SDK falls back to ``str(self)``.
        return ()


# ---------------------------------------------------------------------------
# Executor (idempotent)
# ---------------------------------------------------------------------------


class WriteNoteExecutor(
    IdempotentToolExecutor[WriteNoteAction, WriteNoteObservation]
):
    """Synchronous executor for ``write_note``.

    All idempotency is handled by ``IdempotentToolExecutor``; this class
    only supplies the four subclass hooks.
    """

    TOOL_NAME = "write_note"

    def _execute(
        self,
        action: WriteNoteAction,
        conversation: "BaseConversation | None",
    ) -> WriteNoteObservation:
        notes_dir = _notes_dir()
        notes_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{_slug(action.title)}.txt"
        target = notes_dir / filename
        payload = action.body.encode("utf-8")

        # Atomic write via tempfile + os.replace.  Prevents partial-file
        # observations after a crash-and-resume mid-write.
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(notes_dir),
            prefix=".tmp-",
            suffix=".txt",
            delete=False,
        ) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, target)

        return WriteNoteObservation(
            title=action.title,
            path=str(target),
            bytes_written=len(payload),
            idempotent_replay=False,
        )

    def _observation_from_cached(self, cached_json: Any) -> WriteNoteObservation:
        # Reconstruct the observation from the cached JSON payload;
        # flip idempotent_replay=True so callers can tell this call
        # was served from the ledger.
        assert isinstance(cached_json, dict), (
            "write_note ledger cache: expected dict, got "
            f"{type(cached_json).__name__}"
        )
        return WriteNoteObservation(
            title=str(cached_json.get("title", "")),
            path=str(cached_json.get("path", "")),
            bytes_written=int(cached_json.get("bytes_written", 0)),
            idempotent_replay=True,
        )

    def _result_summary(self, observation: WriteNoteObservation) -> str:
        return (
            f"wrote {observation.bytes_written} bytes to {observation.path}"
        )[:500]

    def _observation_to_cached_json(
        self, observation: WriteNoteObservation
    ) -> Any:
        return {
            "title": observation.title,
            "path": observation.path,
            "bytes_written": observation.bytes_written,
        }


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------


WRITE_NOTE_DESCRIPTION = """Persist a short plain-text note to disk.

Use for durable side-effect testing and small durable artifacts under
``data/notes/``.  This tool is gated by Forge-OH's exactly-once
idempotency ledger: a replayed call with the same ``title`` + ``body``
in the same conversation and at the same event-timeline leaf returns
the cached result WITHOUT re-writing the file.

Parameters:
- title: 1..200-char note title (used to derive filename).
- body:  UTF-8 body (default empty; max 100k chars).

Returns {title, path, bytes_written, idempotent_replay}.
``idempotent_replay=true`` indicates the ledger served the result.
"""


class WriteNoteTool(ToolDefinition[WriteNoteAction, WriteNoteObservation]):
    """OpenHands tool wrapper for the durable-note write path."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,  # noqa: ARG003
        **params: Any,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(
                "WriteNoteTool does not accept factory parameters "
                f"(got {sorted(params)})"
            )
        return [
            cls(
                action_type=WriteNoteAction,
                observation_type=WriteNoteObservation,
                description=WRITE_NOTE_DESCRIPTION,
                executor=WriteNoteExecutor(),
                annotations=ToolAnnotations(
                    title="write_note",
                    readOnlyHint=False,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


register_tool("write_note", WriteNoteTool)
