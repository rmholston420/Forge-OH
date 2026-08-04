"""CLI entry point for the self-eval harness. Invoked by the systemd .timer.

Usage::

    python -m openhands_tools_ext.selfeval.cli \\
        --manifest openhands_tools_ext/selfeval/manifest.toml \\
        --limit 3 --sample head \\
        --bff-url http://127.0.0.1:8081 \\
        --summary-dir docs/selfeval

Environment overrides (CLI flags win):
- ``FORGE_SELFEVAL_LIMIT`` — integer default for ``--limit``.
- ``FORGE_SELFEVAL_SAMPLE`` — default for ``--sample`` (``head``, ``random``,
  ``tag:<name>``).
- ``FORGE_SELFEVAL_BFF_URL`` — default for ``--bff-url``.
- ``FORGE_SELFEVAL_TIMEOUT_SEC`` — per-task timeout override.
- ``FORGE_SELFEVAL_SEED`` — RNG seed for ``--sample random`` (int).

Exit codes:
- ``0``: harness completed. Non-passing outcomes are NOT an error at this
  layer — the whole point is to surface them via proposals.
- ``2``: manifest error, invalid CLI arguments, or catastrophic transport
  failure (all tasks errored before starting).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from openhands_tools_ext.selfeval import (
    SELFEVAL_DEFAULT_LIMIT,
    SELFEVAL_DEFAULT_MANIFEST,
    SELFEVAL_TASK_TIMEOUT_SEC,
)
from openhands_tools_ext.selfeval.harness import run_selfeval
from openhands_tools_ext.selfeval.manifest import (
    ManifestError,
    load_manifest,
    select_tasks,
)
from openhands_tools_ext.selfeval.proposer import dump_summary, propose_fixes

log = logging.getLogger("forge_oh_selfeval")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("selfeval: env %s=%r not an int; using default %d", name, raw, default)
        return default


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="forge-oh-selfeval",
        description="Run the Forge-OH self-eval harness.",
    )
    p.add_argument(
        "--manifest",
        type=Path,
        default=Path(os.environ.get("FORGE_SELFEVAL_MANIFEST", SELFEVAL_DEFAULT_MANIFEST)),
        help="Path to manifest.toml (default: %(default)s)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=_env_int("FORGE_SELFEVAL_LIMIT", SELFEVAL_DEFAULT_LIMIT),
        help="Max tasks per run (default: %(default)d, env: FORGE_SELFEVAL_LIMIT)",
    )
    p.add_argument(
        "--sample",
        default=os.environ.get("FORGE_SELFEVAL_SAMPLE", "head"),
        help="Selection strategy: head | random | tag:<name> (default: %(default)s)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=_env_int("FORGE_SELFEVAL_SEED", 0) or None,
        help="RNG seed for --sample random (default: OS entropy)",
    )
    p.add_argument(
        "--bff-url",
        default=os.environ.get("FORGE_SELFEVAL_BFF_URL", "http://127.0.0.1:8081"),
        help="Forge-OH BFF base URL (default: %(default)s)",
    )
    p.add_argument(
        "--task-timeout-sec",
        type=int,
        default=_env_int("FORGE_SELFEVAL_TIMEOUT_SEC", SELFEVAL_TASK_TIMEOUT_SEC),
        help="Per-task wall-clock cap (default: %(default)ds)",
    )
    p.add_argument(
        "--summary-dir",
        type=Path,
        default=Path(os.environ.get("FORGE_SELFEVAL_SUMMARY_DIR", "docs/selfeval")),
        help="Directory for JSON run summaries (default: %(default)s)",
    )
    p.add_argument(
        "--proposal-dir",
        type=Path,
        default=Path(os.environ.get("FORGE_SELFEVAL_PROPOSAL_DIR", "docs/proposals")),
        help="Directory for LLM fix proposals (default: %(default)s)",
    )
    p.add_argument(
        "--no-propose",
        action="store_true",
        help="Skip the LLM proposer stage (harness runs; failures logged but no fix drafts).",
    )
    p.add_argument(
        "--preset-id",
        default=os.environ.get("FORGE_SELFEVAL_PRESET_ID"),
        help=(
            "Agent preset id to attach to each POST /api/runs. "
            "Defaults to whichever preset the BFF flags as isDefault "
            "(env: FORGE_SELFEVAL_PRESET_ID)."
        ),
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return p


async def _amain(args: argparse.Namespace) -> int:
    try:
        all_tasks = load_manifest(args.manifest)
    except (ManifestError, FileNotFoundError) as exc:
        log.error("selfeval: manifest error: %s", exc)
        return 2

    try:
        selected = select_tasks(
            all_tasks,
            limit=args.limit,
            strategy=args.sample,
            seed=args.seed,
        )
    except ValueError as exc:
        log.error("selfeval: selection error: %s", exc)
        return 2

    if not selected:
        log.warning(
            "selfeval: no tasks matched (manifest has %d, strategy=%r)",
            len(all_tasks),
            args.sample,
        )
        return 0

    log.info(
        "selfeval: manifest=%s selected=%d/%d strategy=%s bff=%s",
        args.manifest,
        len(selected),
        len(all_tasks),
        args.sample,
        args.bff_url,
    )

    summary = await run_selfeval(
        selected,
        bff_base_url=args.bff_url,
        manifest_path=str(args.manifest),
        selection_strategy=args.sample,
        task_timeout_sec=args.task_timeout_sec,
        preset_id=args.preset_id,
    )

    now = datetime.now(timezone.utc)
    summary_path = args.summary_dir / f"{now:%Y-%m-%d}-selfeval.json"
    dump_summary(summary, summary_path)
    log.info("selfeval: summary → %s", summary_path)

    log.info(
        "selfeval: results — passed=%d failed=%d timeout=%d error=%d",
        summary.tasks_passed,
        summary.tasks_failed,
        summary.tasks_timed_out,
        summary.tasks_errored,
    )

    if args.no_propose:
        log.info("selfeval: --no-propose set, skipping fix proposals")
        return 0

    written = propose_fixes(summary.outcomes, proposal_dir=args.proposal_dir, now=now)
    if written:
        log.info("selfeval: wrote %d proposal(s):", len(written))
        for p in written:
            log.info("  %s", p)
    else:
        log.info("selfeval: no proposals needed (all tasks passed)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        log.warning("selfeval: interrupted")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
