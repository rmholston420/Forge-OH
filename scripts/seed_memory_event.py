"""scripts/seed_memory_event.py — deterministic MemoryEvent seed for Stage 5.6a Playwright pass.

Writes one canonical MemoryEvent to whichever backend
``openhands_tools_ext.memory.composition.make_memory_adapter()`` composes
from the current process env. On Colossus with .env.neo4j sourced this
targets the live DozerDB instance in the ``kosmos-dozerdb`` container /
``forgeoh`` database. In the sandbox (no NEO4J_PASSWORD) it exits 0
without writing so the CI path doesn't need infra.

Idempotency: uses ``write_event`` which appends a MemoryEvent node. Safe
to invoke repeatedly; each call adds one row. The Playwright spec only
requires ``len(recent_writes) > 0``.
"""

from __future__ import annotations

import asyncio
import os
import sys


async def _main() -> int:
    if not os.getenv("NEO4J_PASSWORD"):
        print(
            "[seed] NEO4J_PASSWORD unset; skipping seed. "
            "(BFF will also 503 without it.)",
            file=sys.stderr,
        )
        return 0

    from openhands_tools_ext.memory.composition import make_memory_adapter

    port = make_memory_adapter()
    try:
        event_id = await port.write_event(
            "colossus",
            "runs",
            "dozerdb",
            provenance="playwright-seed",
            confidence=0.95,
            source_citation="scripts/seed_memory_event.py",
            pii_tier="Public",
        )
        print(f"[seed] wrote MemoryEvent id={event_id}", file=sys.stderr)
        return 0
    finally:
        await port.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
