"""Stage 5.5 verification: plan §5.5.3 duplicate-discard check adapted
to Forge-OH's triple-shaped write path (per ADR-023 D1).

The plan sketch used a free-string ``curated_write('The build uses CUDA
12.8...', 'agent-observation', 0.85)`` call. ADR-023 D1 pins the cycle
as triple-shaped because ``:MemoryEvent`` (ADR-021) is triple-shaped;
free-string observations must be lifted to a triple by the caller.

This script:

1. Wires a ``DozerDbMemoryAdapter`` with in-memory backends + fake
   embeddings + in-memory Qdrant (no live infra).
2. Calls ``curated_write`` twice with an identical triple.
3. Asserts the first call ``keep``s and the second ``discard``s.
4. Asserts the underlying graph holds exactly one ``:MemoryEvent``
   after both calls.
5. Also confirms zero-trust floor is preserved (empty provenance →
   ``ValueError``).

Exit 0 iff every assertion holds. Intended for the .oh-venv on
Colossus (or any sandbox with the Forge-OH package importable) — same
invocation pattern as the Stage 5.4 verifier:

    cd ~/dev/forge-oh && PYTHONPATH=. python scripts/verify_stage_5_5_curation.py
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any


def _adapter():
    """Match the contract-test wiring: full DozerDbMemoryAdapter with
    all four lanes in-memory. Kept local to this script so the verifier
    doesn't import test fixtures."""
    from openhands_tools_ext.memory.adapters.dozerdb import (
        DozerDbMemoryAdapter,
        InMemoryGraphBackend,
        InMemoryTemporalIndex,
        NoOpAmgPolicy,
    )
    from openhands_tools_ext.memory.adapters.vector.qdrant.adapter import (
        InMemoryQdrantBackend,
        QdrantVectorAdapter,
    )

    @dataclass
    class _FakeEmbeddings:
        calls: list[list[str]] = field(default_factory=list)

        async def embed(
            self, *, texts: list[str], model: str | None = None
        ) -> list[list[float]]:
            self.calls.append(list(texts))
            out: list[list[float]] = []
            for t in texts:
                h = abs(hash(t))
                out.append(
                    [
                        ((h >> 0) & 0xFFFF) / 65535.0,
                        ((h >> 16) & 0xFFFF) / 65535.0,
                        ((h >> 32) & 0xFFFF) / 65535.0,
                        ((h >> 48) & 0xFFFF) / 65535.0,
                    ]
                )
            return out

        def dimensions(self, model: str | None = None) -> int:
            return 4

        def is_healthy(self) -> bool:
            return True

        async def close(self) -> None:
            return None

    return DozerDbMemoryAdapter(
        graph=InMemoryGraphBackend(),
        amg=NoOpAmgPolicy(),
        temporal=InMemoryTemporalIndex(),
        embeddings=_FakeEmbeddings(),
        vector=QdrantVectorAdapter(backend=InMemoryQdrantBackend()),
        default_corpus="stage-5-5-verify",
    )


def _count_memory_events(adapter: Any) -> int:
    graph = adapter._graph  # noqa: SLF001
    return sum(
        1
        for node in graph._nodes.values()  # noqa: SLF001
        if getattr(node, "label", None) == "MemoryEvent"
        or (isinstance(node, dict) and node.get("label") == "MemoryEvent")
    )


async def _main() -> int:
    from openhands_tools_ext.memory.curation import curated_write

    print("=" * 72)
    print("Stage 5.5 verification — plan §5.5.3 duplicate-discard")
    print("Target: openhands_tools_ext.memory.curation.curated_write (ADR-023)")
    print("=" * 72)

    checks: list[bool] = []

    adapter = _adapter()

    # Triple-shaped equivalent of the plan's free-string observation.
    triple = dict(
        subject="Colossus",
        predicate="usesToolchain",
        object="CUDA 12.8",
        provenance="agent-observation",
        confidence=0.85,
    )

    r1 = await curated_write(adapter, **triple)
    count_after_first = _count_memory_events(adapter)
    print(f"first call:  action={r1.action}  reason={r1.reason!r}")
    print(f"             :MemoryEvent count = {count_after_first}")
    if r1.action == "keep" and count_after_first == 1:
        print("PASS: first identical write persisted with action='keep'")
        checks.append(True)
    else:
        print("FAIL: first write did not persist as 'keep'")
        checks.append(False)

    r2 = await curated_write(adapter, **triple)
    count_after_second = _count_memory_events(adapter)
    print(f"second call: action={r2.action}  reason={r2.reason!r}")
    print(f"             :MemoryEvent count = {count_after_second}")
    if (
        r2.action == "discard"
        and r2.final_event is None
        and count_after_second == count_after_first
    ):
        print("PASS: second identical write discarded (no duplicate persisted)")
        checks.append(True)
    else:
        print("FAIL: second identical write was NOT discarded")
        checks.append(False)

    # Zero-trust floor preservation (ADR-023 D3). Use a distinct triple
    # on a fresh adapter so the write_event path is actually reached
    # (a duplicate triple would short-circuit via 'discard' before the
    # port-level guard runs).
    zt_adapter = _adapter()
    empty_prov = dict(
        subject="Colossus",
        predicate="needsValidation",
        object="zero-trust floor",
        provenance="",
        confidence=0.85,
    )
    try:
        await curated_write(zt_adapter, **empty_prov)
    except ValueError as e:
        print(f"PASS: curated_write preserved zero-trust floor — {e}")
        checks.append(True)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: wrong exception on empty provenance — {type(e).__name__}: {e}")
        checks.append(False)
    else:
        print("FAIL: curated_write accepted empty provenance (zero-trust floor broken)")
        checks.append(False)

    passed = sum(1 for c in checks if c)
    total = len(checks)
    print("-" * 72)
    print(f"Stage 5.5 verification: {passed}/{total} checks passed")
    if passed == total:
        print("STAGE 5.5 DoD: SATISFIED.")
        return 0
    print("STAGE 5.5 DoD: NOT SATISFIED.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
