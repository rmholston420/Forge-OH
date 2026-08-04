"""Self-Eval harness for Forge-OH.

Runs a small, hand-curated manifest of coding tasks through Forge-OH end-to-end
(BFF ``POST /api/runs`` → real agent-server + vLLM), collects the per-run
verify verdict from the trajectory store, and \u2014 on any failure \u2014 asks the
planner LLM to propose one narrowly-scoped fix.

Design invariants:
- **Local-first**: talks to the Forge-OH BFF over 127.0.0.1; never leaves
  Colossus. No cloud, no auth.
- **Non-destructive**: proposals are written to disk under
  ``docs/proposals/YYYY-MM-DD-<sig>.md`` and NEVER auto-applied.
  Morning-review by the human is a hard invariant.
- **Bounded but scalable**: the manifest is the source of truth for tasks and
  is meant to grow. The CLI selects a subset per run via ``--limit N`` +
  ``--sample {head,random,tag:<name>}``, so a short weekday run and a long
  weekend run share the same manifest. Per-task timeout enforces the wall.
  Runs on a systemd .timer, no daemon.
- **Composes with existing hooks**: relies on the SDK-registered verify +
  trajectory hooks to produce the verdict. The harness itself is a thin
  orchestrator: kick off run → wait for terminal state → read verdict → done.

Not a Kosmos port. The Kosmos ``plugins/tektos/eval/harness.py`` subprocess-invokes
the ``pier`` CLI and assumes a Harbor task directory. Forge-OH tasks are just
prompts against a workspace, so we don't need Pier and we don't need Docker
per task. We DO borrow the general shape (one manifest file, one verdict per
task, aggregate summary at the end) but not the code.

Modules:
- :mod:`.manifest` \u2014 typed loader for ``manifest.toml``
- :mod:`.harness` \u2014 the orchestrator: run each task, collect verdicts
- :mod:`.proposer` \u2014 LLM-driven fix proposer (writes ``docs/proposals/*.md``)
- :mod:`.cli` \u2014 CLI entry point invoked by the systemd .timer
"""

from __future__ import annotations

__all__ = [
    "SELFEVAL_PROVENANCE",
    "SELFEVAL_TASK_TIMEOUT_SEC",
    "SELFEVAL_DEFAULT_MANIFEST",
]

SELFEVAL_PROVENANCE: str = "forge_oh_selfeval"
"""Marker written into every artifact this subsystem emits."""

SELFEVAL_TASK_TIMEOUT_SEC: int = 300
"""Per-task wall-clock cap. Kills the poll loop; does NOT stop the agent-server run."""

SELFEVAL_DEFAULT_MANIFEST: str = "openhands_tools_ext/selfeval/manifest.toml"
"""Repo-relative path to the default manifest."""

SELFEVAL_DEFAULT_LIMIT: int = 3
"""Number of tasks selected per run when neither ``--limit`` nor the env override is set.

Bumping this changes the *default* only; every invocation can still override via
``--limit`` on the CLI or ``FORGE_SELFEVAL_LIMIT`` in the environment."""
