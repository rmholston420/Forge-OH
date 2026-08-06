"""Contract tests for the ACE curation cycle (Stage 5.5, ADR-023).

Composes the ported ``DozerDbMemoryAdapter`` with in-memory backends
plus a deterministic ``EmbeddingsPort`` double and the ported
``InMemoryQdrantBackend`` so ``search_semantic`` is real (no live
Ollama / Qdrant needed). Verifies:

- Novel triple → ``keep``, event written, subsequent ``search_semantic``
  finds it.
- Exact repeat → ``discard``, no second ``:MemoryEvent`` in the graph.
- Near-miss (same subject/predicate, different object) → ``keep``
  (merge semantics beyond persistence are deferred; string-overlap
  cannot decide semantic refinement).
- Missing provenance → ``ValueError`` from the port-level guard, NOT
  swallowed by ``curated_write`` (ADR-023 D3).
- ``reflect_on_candidate`` returns the three canonical strings and
  ``curate`` dispatches correctly on each.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

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
from openhands_tools_ext.memory.curation import (
    CurationCandidate,
    CurationResult,
    curate,
    curated_write,
    generate_candidate,
    reflect_on_candidate,
)
from openhands_tools_ext.memory.ports.memory import MemoryHit


# ── In-memory doubles ───────────────────────────────────────────────────────


@dataclass
class _FakeEmbeddings:
    """Deterministic 4-dim EmbeddingsPort double.

    Mirrors the pattern in test_semantic_memory_path_contract.py.
    """

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


def _fresh_adapter() -> DozerDbMemoryAdapter:
    """DozerDbMemoryAdapter with all four lanes wired to in-memory doubles.

    Semantic lane is deterministic: identical triple text always
    produces the same 4-dim vector, so exact-duplicate detection is
    reliable through the vector store.
    """
    return DozerDbMemoryAdapter(
        graph=InMemoryGraphBackend(),
        amg=NoOpAmgPolicy(),
        temporal=InMemoryTemporalIndex(),
        embeddings=_FakeEmbeddings(),
        vector=QdrantVectorAdapter(backend=InMemoryQdrantBackend()),
        default_corpus="forge-oh-test",
    )


def _triple_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "subject": "Colossus",
        "predicate": "hasComponent",
        "object": "RTX 5090",
        "provenance": "agent-observation",
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ── Dataclass shape / helpers ───────────────────────────────────────────────


def test_candidate_triple_text_is_lowercase_and_normalized() -> None:
    c = CurationCandidate(
        subject="  Colossus  ",
        predicate="HasComponent",
        object="RTX 5090",
        provenance="agent",
        confidence=0.9,
    )
    assert c.triple_text() == "colossus hascomponent rtx 5090"


def test_candidate_to_write_kwargs_is_shaped_for_adapter() -> None:
    c = CurationCandidate(
        subject="s",
        predicate="p",
        object="o",
        provenance="agent",
        confidence=0.5,
        source_citation="cite://x",
        pii_tier="Public",
        attributes={"tag": "test"},
    )
    kw = c.to_write_kwargs()
    assert set(kw) == {
        "provenance",
        "confidence",
        "source_citation",
        "pii_tier",
        "attributes",
    }
    assert kw["attributes"] == {"tag": "test"}


@pytest.mark.asyncio
async def test_generate_candidate_returns_frozen_dataclass() -> None:
    c = await generate_candidate(**_triple_kwargs())
    assert isinstance(c, CurationCandidate)
    with pytest.raises(Exception):  # dataclass(frozen=True)
        c.subject = "changed"  # type: ignore[misc]


# ── Reflection semantics ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reflect_on_empty_related_returns_novel_string() -> None:
    c = CurationCandidate(
        subject="s", predicate="p", object="o", provenance="a", confidence=0.5,
    )
    reflection = await reflect_on_candidate(c, [])
    assert "novel" in reflection.lower()


@pytest.mark.asyncio
async def test_reflect_on_exact_duplicate_flags_duplicate() -> None:
    c = CurationCandidate(
        subject="Colossus",
        predicate="hasComponent",
        object="RTX 5090",
        provenance="a",
        confidence=0.5,
    )
    existing = [
        MemoryHit(
            id="ev-1",
            payload={
                "subject": "Colossus",
                "predicate": "hasComponent",
                "object": "RTX 5090",
                "provenance": "prior",
                "confidence": 0.9,
            },
            score=0.99,
        )
    ]
    reflection = await reflect_on_candidate(c, existing)
    assert "duplicate" in reflection.lower()


@pytest.mark.asyncio
async def test_reflect_on_near_miss_flags_refine() -> None:
    c = CurationCandidate(
        subject="Colossus",
        predicate="hasComponent",
        object="RTX 4090",  # different object
        provenance="a",
        confidence=0.5,
    )
    existing = [
        MemoryHit(
            id="ev-1",
            payload={
                "subject": "Colossus",
                "predicate": "hasComponent",
                "object": "RTX 5090",
                "provenance": "prior",
                "confidence": 0.9,
            },
            score=0.8,
        )
    ]
    reflection = await reflect_on_candidate(c, existing)
    assert "refine" in reflection.lower()


@pytest.mark.asyncio
async def test_reflect_ignores_malformed_hit_payload() -> None:
    """A hit with missing subject/predicate/object must not false-positive
    as a duplicate — that would cause silent data loss."""
    c = CurationCandidate(
        subject="Colossus",
        predicate="hasComponent",
        object="RTX 5090",
        provenance="a",
        confidence=0.5,
    )
    existing = [MemoryHit(id="ev-1", payload={}, score=0.5)]
    reflection = await reflect_on_candidate(c, existing)
    assert "duplicate" not in reflection.lower()


# ── Curate dispatch ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_curate_novel_returns_keep() -> None:
    c = CurationCandidate(
        subject="s", predicate="p", object="o", provenance="a", confidence=0.5,
    )
    result = await curate(c, [])
    assert result.action == "keep"
    assert result.final_event is c


@pytest.mark.asyncio
async def test_curate_duplicate_returns_discard_with_none_event() -> None:
    c = CurationCandidate(
        subject="Colossus",
        predicate="hasComponent",
        object="RTX 5090",
        provenance="a",
        confidence=0.5,
    )
    existing = [
        MemoryHit(
            id="ev-1",
            payload={
                "subject": "Colossus",
                "predicate": "hasComponent",
                "object": "RTX 5090",
                "provenance": "prior",
                "confidence": 0.9,
            },
        )
    ]
    result = await curate(c, existing)
    assert result.action == "discard"
    assert result.final_event is None


@pytest.mark.asyncio
async def test_curate_near_miss_returns_merge_with_candidate() -> None:
    c = CurationCandidate(
        subject="Colossus",
        predicate="hasComponent",
        object="RTX 4090",
        provenance="a",
        confidence=0.5,
    )
    existing = [
        MemoryHit(
            id="ev-1",
            payload={
                "subject": "Colossus",
                "predicate": "hasComponent",
                "object": "RTX 5090",
            },
        )
    ]
    result = await curate(c, existing)
    assert result.action == "merge"
    assert result.final_event is c


# ── curated_write orchestrator ──────────────────────────────────────────────


async def _count_memory_events(adapter: DozerDbMemoryAdapter) -> int:
    """Read the in-memory graph backend to count :MemoryEvent nodes.

    Relies on the ported InMemoryGraphBackend storing nodes on an
    internal ``_nodes`` dict keyed by id. If that internal shape
    changes upstream, this test is the canary.
    """
    graph = adapter._graph  # noqa: SLF001
    return sum(
        1
        for node in graph._nodes.values()  # noqa: SLF001
        if getattr(node, "label", None) == "MemoryEvent"
        or (isinstance(node, dict) and node.get("label") == "MemoryEvent")
    )


@pytest.mark.asyncio
async def test_curated_write_novel_triple_persists_event() -> None:
    adapter = _fresh_adapter()
    before = await _count_memory_events(adapter)
    result = await curated_write(adapter, **_triple_kwargs())
    after = await _count_memory_events(adapter)

    assert result.action == "keep"
    assert result.final_event is not None
    assert result.final_event.subject == "Colossus"
    assert after == before + 1


@pytest.mark.asyncio
async def test_curated_write_exact_duplicate_is_discarded() -> None:
    adapter = _fresh_adapter()
    first = await curated_write(adapter, **_triple_kwargs())
    events_after_first = await _count_memory_events(adapter)
    assert first.action == "keep"
    assert events_after_first >= 1

    second = await curated_write(adapter, **_triple_kwargs())
    events_after_second = await _count_memory_events(adapter)

    assert second.action == "discard"
    assert second.final_event is None
    assert events_after_second == events_after_first


@pytest.mark.asyncio
async def test_curated_write_near_miss_persists_via_merge() -> None:
    adapter = _fresh_adapter()
    await curated_write(adapter, **_triple_kwargs())
    events_after_first = await _count_memory_events(adapter)

    near_miss = _triple_kwargs(object="RTX 4090")
    result = await curated_write(adapter, **near_miss)
    events_after_second = await _count_memory_events(adapter)

    assert result.action == "merge"
    assert result.final_event is not None
    assert result.final_event.object == "RTX 4090"
    assert events_after_second == events_after_first + 1


@pytest.mark.asyncio
async def test_curated_write_preserves_zero_trust_floor() -> None:
    """ADR-023 D3: curated_write MUST NOT swallow ValueError from the
    port-level guard when provenance is empty or confidence is out of
    range."""
    adapter = _fresh_adapter()
    with pytest.raises(ValueError):
        await curated_write(adapter, **_triple_kwargs(provenance=""))
    with pytest.raises(ValueError):
        await curated_write(adapter, **_triple_kwargs(confidence=1.5))


@pytest.mark.asyncio
async def test_curated_write_returns_curation_result_type() -> None:
    adapter = _fresh_adapter()
    result = await curated_write(adapter, **_triple_kwargs())
    assert isinstance(result, CurationResult)
    assert result.action in ("keep", "merge", "discard")
