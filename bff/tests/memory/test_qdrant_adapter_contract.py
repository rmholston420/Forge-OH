"""Contract tests for :class:`QdrantVectorAdapter` (ADR-026).

Backend-agnostic — runs against :class:`InMemoryQdrantBackend`. A live
Qdrant smoke test lives outside the contract suite (added when the
Docker Compose Qdrant service lands).
"""

from __future__ import annotations

import asyncio

import pytest

from openhands_tools_ext.memory.adapters.vector.qdrant import (
    InMemoryQdrantBackend,
    QdrantBackend,
    QdrantVectorAdapter,
)
from openhands_tools_ext.memory.adapters.vector.qdrant.adapter import _to_point_id
from openhands_tools_ext.memory.ports.vector import (
    REQUIRED_PAYLOAD_KEYS,
    SnapshotHandle,
    VectorHit,
    VectorPort,
    validate_zero_trust_payload,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _adapter() -> QdrantVectorAdapter:
    return QdrantVectorAdapter(backend=InMemoryQdrantBackend())


def _ok_payload(**extra: object) -> dict[str, object]:
    return {"provenance": "test://payload", "confidence": 0.9, **extra}


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_adapter_satisfies_vector_port_protocol() -> None:
    assert isinstance(_adapter(), VectorPort)


def test_backend_satisfies_qdrant_backend_protocol() -> None:
    assert isinstance(InMemoryQdrantBackend(), QdrantBackend)


def test_required_payload_keys_are_provenance_and_confidence() -> None:
    assert REQUIRED_PAYLOAD_KEYS == frozenset({"provenance", "confidence"})


# ---------------------------------------------------------------------------
# Zero-trust payload validation (ADR-026 Q1)
# ---------------------------------------------------------------------------


def test_validate_zero_trust_payload_accepts_valid_payload() -> None:
    validate_zero_trust_payload({"provenance": "http://x", "confidence": 0.5})


def test_validate_zero_trust_payload_rejects_missing_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        validate_zero_trust_payload({"confidence": 0.9})


def test_validate_zero_trust_payload_rejects_missing_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        validate_zero_trust_payload({"provenance": "x"})


def test_validate_zero_trust_payload_rejects_empty_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        validate_zero_trust_payload({"provenance": "", "confidence": 0.5})


def test_validate_zero_trust_payload_rejects_bool_confidence() -> None:
    with pytest.raises(ValueError, match="float"):
        validate_zero_trust_payload({"provenance": "x", "confidence": True})


def test_validate_zero_trust_payload_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        validate_zero_trust_payload({"provenance": "x", "confidence": 1.5})
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        validate_zero_trust_payload({"provenance": "x", "confidence": -0.1})


def test_validate_zero_trust_payload_rejects_non_dict() -> None:
    with pytest.raises(ValueError, match="dict"):
        validate_zero_trust_payload("not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# upsert enforces zero-trust at the port layer
# ---------------------------------------------------------------------------


def test_upsert_rejects_payload_without_provenance() -> None:
    a = _adapter()

    async def _run() -> None:
        with pytest.raises(ValueError, match="provenance"):
            await a.upsert("c", "p1", [0.1, 0.2], {"confidence": 0.5})

    asyncio.run(_run())


def test_upsert_rejects_payload_without_confidence() -> None:
    a = _adapter()

    async def _run() -> None:
        with pytest.raises(ValueError, match="confidence"):
            await a.upsert("c", "p1", [0.1, 0.2], {"provenance": "x"})

    asyncio.run(_run())


def test_upsert_rejects_empty_vector() -> None:
    a = _adapter()

    async def _run() -> None:
        with pytest.raises(ValueError, match="vector"):
            await a.upsert("c", "p1", [], _ok_payload())

    asyncio.run(_run())


def test_upsert_rejects_non_numeric_vector_element() -> None:
    a = _adapter()

    async def _run() -> None:
        with pytest.raises(ValueError, match="floats"):
            await a.upsert("c", "p1", [0.1, "nope"], _ok_payload())  # type: ignore[list-item]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# upsert / search round-trip
# ---------------------------------------------------------------------------


def test_upsert_then_search_returns_stored_point() -> None:
    a = _adapter()

    async def _run() -> None:
        await a.upsert("c", "p1", [1.0, 0.0, 0.0], _ok_payload(text="alpha"))
        hits = await a.search("c", [1.0, 0.0, 0.0], limit=5)
        assert len(hits) == 1
        assert isinstance(hits[0], VectorHit)
        assert hits[0].score == pytest.approx(1.0)
        assert hits[0].payload["text"] == "alpha"
        assert hits[0].payload["provenance"] == "test://payload"
        assert hits[0].payload["confidence"] == 0.9

    asyncio.run(_run())


def test_search_orders_by_similarity_descending() -> None:
    a = _adapter()

    async def _run() -> None:
        await a.upsert("c", "p1", [1.0, 0.0], _ok_payload(label="close"))
        await a.upsert("c", "p2", [0.0, 1.0], _ok_payload(label="far"))
        hits = await a.search("c", [0.9, 0.1], limit=2)
        assert [h.payload["label"] for h in hits] == ["close", "far"]
        assert hits[0].score > hits[1].score

    asyncio.run(_run())


def test_search_respects_limit() -> None:
    a = _adapter()

    async def _run() -> None:
        for i in range(5):
            await a.upsert("c", f"p{i}", [float(i), 0.0], _ok_payload(i=i))
        hits = await a.search("c", [4.0, 0.0], limit=2)
        assert len(hits) == 2

    asyncio.run(_run())


def test_search_applies_filter() -> None:
    a = _adapter()

    async def _run() -> None:
        await a.upsert("c", "p1", [1.0, 0.0], _ok_payload(tier="high"))
        await a.upsert("c", "p2", [1.0, 0.0], _ok_payload(tier="low"))
        hits = await a.search("c", [1.0, 0.0], limit=10, filter={"tier": "high"})
        assert len(hits) == 1
        assert hits[0].payload["tier"] == "high"

    asyncio.run(_run())


def test_search_returns_empty_for_unknown_collection() -> None:
    a = _adapter()

    async def _run() -> None:
        assert await a.search("nope", [1.0, 0.0]) == []

    asyncio.run(_run())


def test_search_rejects_zero_or_negative_limit() -> None:
    a = _adapter()

    async def _run() -> None:
        with pytest.raises(ValueError, match="limit"):
            await a.search("c", [1.0, 0.0], limit=0)
        with pytest.raises(ValueError, match="limit"):
            await a.search("c", [1.0, 0.0], limit=-1)

    asyncio.run(_run())


def test_search_with_empty_vector_returns_empty_list() -> None:
    """ADR-056 §D3 (STATUS AMENDMENT 2026-08-01): empty query_vector is a
    spec-legal no-op that returns [] without raising.

    Zetesis Stage 6.3 (proper) wiring calls
    ``search(collection=..., query_vector=[], limit=1)`` as a no-op binding
    proof and ignores the result. This test locks that behavior at the
    adapter contract layer.
    """
    a = _adapter()

    async def _run() -> None:
        hits = await a.search("c", [])
        assert hits == []

    asyncio.run(_run())


def test_search_rejects_non_list_query_vector() -> None:
    a = _adapter()

    async def _run() -> None:
        with pytest.raises(ValueError, match="query_vector"):
            await a.search("c", "not-a-list")  # type: ignore[arg-type]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Point-id normalization (donor QdrantClaimUpserter pattern)
# ---------------------------------------------------------------------------


def test_free_form_ids_are_hashed_to_stable_uuidv5() -> None:
    a = _to_point_id("claim-01")
    b = _to_point_id("claim-01")
    c = _to_point_id("claim-02")
    assert a == b  # stable
    assert a != c


def test_valid_uuid_input_returns_canonical_form() -> None:
    u = "12345678-1234-5678-1234-567812345678"
    assert _to_point_id(u) == u


def test_upsert_and_delete_use_same_id_mapping() -> None:
    """delete(id) must remove the point that upsert(id) inserted."""
    a = _adapter()

    async def _run() -> None:
        await a.upsert("c", "claim-01", [1.0, 0.0], _ok_payload())
        # search finds it
        assert len(await a.search("c", [1.0, 0.0])) == 1
        # delete using the same free-form id
        await a.delete("c", "claim-01")
        assert await a.search("c", [1.0, 0.0]) == []

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# delete semantics
# ---------------------------------------------------------------------------


def test_delete_is_noop_for_unknown_collection() -> None:
    a = _adapter()

    async def _run() -> None:
        # Must not raise.
        await a.delete("nope", "p1")

    asyncio.run(_run())


def test_delete_is_noop_for_unknown_id() -> None:
    a = _adapter()

    async def _run() -> None:
        await a.upsert("c", "p1", [1.0, 0.0], _ok_payload())
        await a.delete("c", "unknown")  # must not raise
        # Original point still there.
        assert len(await a.search("c", [1.0, 0.0])) == 1

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# snapshot()
# ---------------------------------------------------------------------------


def test_snapshot_returns_typed_handle() -> None:
    a = _adapter()

    async def _run() -> None:
        await a.upsert("c", "p1", [1.0, 0.0], _ok_payload())
        h = await a.snapshot("c")
        assert isinstance(h, SnapshotHandle)
        assert h.collection == "c"
        assert h.name.startswith("c-")
        assert h.path.endswith(".snapshot")
        assert h.created_at.endswith("Z")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# is_healthy() / close() (ADR-023 rule 5 + idempotence)
# ---------------------------------------------------------------------------


def test_is_healthy_reports_backend_state() -> None:
    good = QdrantVectorAdapter(backend=InMemoryQdrantBackend(healthy=True))
    bad = QdrantVectorAdapter(backend=InMemoryQdrantBackend(healthy=False))
    assert good.is_healthy() is True
    assert bad.is_healthy() is False


def test_is_healthy_never_raises_when_backend_throws() -> None:
    class _ExplodingBackend(InMemoryQdrantBackend):
        def is_healthy(self) -> bool:
            raise RuntimeError("qdrant unreachable")

    a = QdrantVectorAdapter(backend=_ExplodingBackend())
    assert a.is_healthy() is False


def test_close_is_idempotent_and_marks_backend_closed() -> None:
    backend = InMemoryQdrantBackend()
    a = QdrantVectorAdapter(backend=backend)

    async def _run() -> None:
        await a.close()
        await a.close()
        await a.close()

    asyncio.run(_run())
    assert backend.is_healthy() is False  # closed


def test_close_swallows_backend_errors() -> None:
    class _CloseBoomBackend(InMemoryQdrantBackend):
        async def close(self) -> None:
            raise RuntimeError("qdrant 503 on shutdown")

    a = QdrantVectorAdapter(backend=_CloseBoomBackend())

    async def _run() -> None:
        await a.close()  # must not raise

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Collection lifecycle
# ---------------------------------------------------------------------------


def test_first_upsert_creates_collection_at_vector_dimension() -> None:
    backend = InMemoryQdrantBackend()
    a = QdrantVectorAdapter(backend=backend)

    async def _run() -> None:
        await a.upsert("c", "p1", [0.1, 0.2, 0.3], _ok_payload())

    asyncio.run(_run())
    assert "c" in backend._collections
    assert backend._collections["c"].dim == 3


def test_dimension_mismatch_on_same_collection_is_rejected() -> None:
    a = _adapter()

    async def _run() -> None:
        await a.upsert("c", "p1", [0.1, 0.2, 0.3], _ok_payload())
        with pytest.raises(ValueError, match="dim"):
            await a.upsert("c", "p2", [0.1, 0.2], _ok_payload())

    asyncio.run(_run())
