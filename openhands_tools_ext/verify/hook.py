"""Command-line adapter that lets ``VerifyLoop`` be wired in as a STOP hook.

Invoked as::

    python -m openhands_tools_ext.verify.hook

The OpenHands SDK's ``HookType.COMMAND`` contract runs a subprocess with:

* The :class:`openhands.sdk.hooks.types.HookEvent` payload on stdin as
  JSON.
* ``OPENHANDS_PROJECT_DIR`` in the environment (the workspace path).
* ``OPENHANDS_SESSION_ID`` in the environment (used as the run key).

Semantics (matching Claude Code's hook contract, echoed in
``openhands.sdk.hooks.executor.HookResult``):

* **Exit 0** with structured JSON on stdout → success. If ``decision``
  is ``"block"``, the agent will not stop and must retry.
* **Exit 2** → hard block regardless of stdout body.
* **Any other non-zero** → non-blocking error.

Because the SDK spawns a fresh subprocess per STOP event, retry state
is persisted to ``$OPENHANDS_PROJECT_DIR/.forge-oh/verify-state.json``
keyed by session id.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openhands_tools_ext.verify.loop import DEFAULT_MAX_ITERATIONS, VerifyLoop

STATE_DIR = ".forge-oh"
STATE_FILE = "verify-state.json"


def _state_path(workspace: Path) -> Path:
    return workspace / STATE_DIR / STATE_FILE


def _load_state(workspace: Path, session_id: str) -> dict[str, Any]:
    path = _state_path(workspace)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    session_state = raw.get(session_id)
    if not isinstance(session_state, dict):
        return {}
    return session_state


def _save_state(workspace: Path, session_id: str, state: dict[str, Any]) -> None:
    path = _state_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            loaded = {}
        if isinstance(loaded, dict):
            existing = loaded
    existing[session_id] = state
    path.write_text(json.dumps(existing, indent=2, sort_keys=True))


def _hook_event_edited_files(event: dict[str, Any]) -> list[Path]:
    """Best-effort extraction of edited files from the STOP hook event.

    The SDK does not (yet) attach a file-change list to the STOP event,
    so this reads a companion sidecar written by the agent-server
    integration. If the sidecar is absent, we fall back to the empty
    list — the E.2 selector will then use ``select_targets`` with no
    edited-file hints and typically produce a SKIPPED verdict.
    """
    metadata = event.get("metadata") or {}
    files = metadata.get("edited_files") or []
    if isinstance(files, list):
        return [Path(f) for f in files if isinstance(f, str)]
    return []


def main(argv: list[str] | None = None) -> int:
    del argv  # unused; signature kept for testability
    raw = sys.stdin.read().strip()
    if not raw:
        sys.stderr.write("verify-hook: empty stdin (expected HookEvent JSON)\n")
        return 1
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"verify-hook: bad JSON on stdin: {exc}\n")
        return 1

    if event.get("event_type") != "Stop":
        # Not a STOP event — no-op success.
        print(json.dumps({"reason": "verify-hook: non-STOP event ignored"}))
        return 0

    workspace_str = os.environ.get("OPENHANDS_PROJECT_DIR") or os.environ.get(
        "OPENHANDS_WORKING_DIR"
    )
    if not workspace_str:
        sys.stderr.write("verify-hook: OPENHANDS_PROJECT_DIR not set\n")
        return 1
    workspace = Path(workspace_str)

    session_id = os.environ.get("OPENHANDS_SESSION_ID") or event.get("session_id") or ""
    if not session_id:
        sys.stderr.write("verify-hook: no session id available\n")
        return 1

    max_iterations = int(
        os.environ.get("FORGE_OH_VERIFY_MAX_ITERATIONS", str(DEFAULT_MAX_ITERATIONS))
    )

    saved = _load_state(workspace, session_id)
    loop = VerifyLoop(
        workspace=workspace,
        max_iterations=max_iterations,
        _iterations_used=int(saved.get("iterations_used", 0)),
        edited_files_since_last_verify=[Path(p) for p in saved.get("edited_files", [])],
    )
    for f in _hook_event_edited_files(event):
        loop.note_edit(f)

    decision = loop.on_stop()

    _save_state(
        workspace,
        session_id,
        {
            "iterations_used": loop._iterations_used,
            "edited_files": [str(p) for p in loop.edited_files_since_last_verify],
            "last_reason": decision.reason,
            # step.verdict is already the string form because
            # VerificationStep uses use_enum_values=True.
            "last_verdict": (decision.step.verdict if decision.step else "no-step"),
        },
    )

    print(json.dumps(decision.to_hook_json()))
    # Structured "block" is signalled via decision JSON on stdout with
    # exit 0; the SDK executor respects that. Exit 2 is reserved for
    # hard-fail scenarios where we could not even run the loop.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
