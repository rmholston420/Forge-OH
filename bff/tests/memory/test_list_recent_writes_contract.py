"""Contract tests for MemoryPort.list_recent_writes (Stage 5.6a / ADR-024).

Uses the in-memory backends (same fixture shape as
``test_ace_curation_contract.py``) so no live infra is required. The
adapter is exercised via the ``MemoryPort`` surface only \u2014 no direct
graph-backend calls \u2014 to lock the contract at the port layer.
"""

from __future__ import annotations

import asyncio
import pytest

from openhands_tools_ext.memory.adapters.dozerdb.adapter import (
    DozerDbMemoryAdapter,
    InMemoryGraphBackend,
    InMemoryTemporalIndex,
    NoOpAmgPolicy,
)
from openhands_tools_ext.memory.ports.memory import (
    MemoryEventRecord,
    MemoryPort,
)


def _fresh_adapter() -> DozerDbMemoryAdapter:
    return DozerDbMemoryAdapter(
        graph=InMemoryGraphBackend(),
        amg=NoOpAmgPolicy(),
        temporal=InMemoryTemporalIndex(),
    )


@pytest.mark.asyncio
async def test_list_recent_writes_returns_empty_on_fresh_adapter():
    adapter = _fresh_adapter()
    try:
        out = await adapter.list_recent_writes()
        assert out == []
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_list_recent_writes_projects_written_event_to_record():
    adapter = _fresh_adapter()
    try:
        await adapter.write_event(
            "colossus",
            "runs",
            "dozerdb",
            provenance="agent",
            confidence=0.9,
            source_citation="build log",
            pii_tier="Public",
        )
        rows = await adapter.list_recent_writes()
        assert len(rows) == 1
        r = rows[0]
        assert isinstance(r, MemoryEventRecord)
        assert r.subject == "colossus"
        assert r.predicate == "runs"
        assert r.object == "dozerdb"
        assert r.provenance == "agent"
        assert r.confidence == pytest.approx(0.9)
        assert r.source_citation == "build log"
        assert r.pii_tier == "Public"
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_list_recent_writes_sorts_newest_first():
    adapter = _fresh_adapter()
    try:
        # Three writes; sleep so ISO timestamps strictly increase even under
        # coarse clocks. asyncio.sleep(0) yields control but doesn't advance
        # the wall clock, so use a real (tiny) delay.
        for triple in (
            ("a", "p", "b"),
            ("c", "p", "d"),
            ("e", "p", "f"),
        ):
            await adapter.write_event(
                *triple, provenance="agent", confidence=0.5
            )
            await asyncio.sleep(0.001)
        rows = await adapter.list_recent_writes()
        assert [r.subject for r in rows] == ["e", "c", "a"]
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_list_recent_writes_respects_limit():
    adapter = _fresh_adapter()
    try:
        for i in range(5):
            await adapter.write_event(
                f"s{i}", "p", "o", provenance="agent", confidence=0.5
            )
            await asyncio.sleep(0.001)
        rows = await adapter.list_recent_writes(limit=2)
        assert len(rows) == 2
        assert [r.subject for r in rows] == ["s4", "s3"]
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_list_recent_writes_rejects_non_positive_limit():
    adapter = _fresh_adapter()
    try:
        with pytest.raises(ValueError, match="positive int"):
            await adapter.list_recent_writes(limit=0)
        with pytest.raises(ValueError, match="positive int"):
            await adapter.list_recent_writes(limit=-1)
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_list_recent_writes_returns_empty_after_close():
    adapter = _fresh_adapter()
    await adapter.write_event(
        "s", "p", "o", provenance="agent", confidence=0.5
    )
    await adapter.close()
    # After close, contract says return empty rather than raise.
    out = await adapter.list_recent_writes()
    assert out == []


@pytest.mark.asyncio
async def test_adapter_still_satisfies_memory_port_protocol():
    """Adding list_recent_writes must not break MemoryPort structural check."""
    adapter = _fresh_adapter()
    try:
        assert isinstance(adapter, MemoryPort)
    finally:
        await adapter.close()
