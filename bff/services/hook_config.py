"""Runtime hook wiring for Forge-OH conversations.

The BFF injects a ``hook_config`` block into every ``POST /api/conversations``
body so the agent-server registers two STOP hooks against every conversation
it creates:

1. ``openhands_tools_ext.verify.hook`` — VerifyLoop (Slice E).
2. ``openhands_tools_ext.trajectory.hook`` — Trajectory Memory writer (Slice F).

Both are ``HookType.COMMAND`` subprocess hooks. The SDK spawns them with
the ``HookEvent`` payload on stdin and ``OPENHANDS_PROJECT_DIR`` /
``OPENHANDS_SESSION_ID`` in the environment; both hooks already know how
to read that contract.

Hook ordering: the OpenHands SDK runs hooks in list order and does NOT
short-circuit on the ``stop`` event, so both hooks always execute. Verify
must run FIRST because the trajectory hook reads verify-state.json to
learn the run's final status. The list order below reflects that.

The Python interpreter used for the subprocess is chosen in this order:
1. ``FORGE_OH_HOOK_PYTHON`` env var (explicit override).
2. ``sys.executable`` (the interpreter running the BFF — which on Colossus
   is ``.oh-venv/bin/python``, exactly where ``openhands_tools_ext`` is
   installed).
"""

from __future__ import annotations

import os
import sys


def _hook_python() -> str:
    """Absolute Python path used to invoke ``python -m ...`` for hooks."""
    return os.environ.get("FORGE_OH_HOOK_PYTHON") or sys.executable


def build_hook_config() -> dict:
    """Return the ``hook_config`` block for ``POST /api/conversations``.

    Emitted as a plain dict (not a ``HookConfig`` instance) because the
    agent-server accepts JSON and building the Pydantic model here would
    just re-serialize it. Field names use the SDK's snake_case format.
    """
    py = _hook_python()
    return {
        "stop": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "name": "forge-oh-verify",
                        "command": f"{py} -m openhands_tools_ext.verify.hook",
                        "timeout": 120,
                    },
                    {
                        "type": "command",
                        "name": "forge-oh-trajectory",
                        "command": f"{py} -m openhands_tools_ext.trajectory.hook",
                        "timeout": 60,
                    },
                ],
            }
        ]
    }
