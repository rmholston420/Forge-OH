"""Contract test for OllamaEmbeddingsAdapter (ADR-073).

Two tiers:

- **Fast tier (no network):** patches ``httpx.AsyncClient`` to return a
  canned ``/api/embed`` response; asserts the adapter parses it and
  raises ``EmbeddingError`` on malformed responses.
- **Live tier (Colossus):** exercised only when ``FORGE_MEMORY_LIVE=1``
  and Ollama is reachable at ``KOSMOS_OLLAMA_BASE_URL``. Asserts a real
  ``nomic-embed-text`` embedding is 768-dim.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from openhands_tools_ext.memory.adapters.embeddings.ollama.adapter import OllamaEmbeddingsAdapter
from openhands_tools_ext.memory.ports.embeddings import EmbeddingError, EmbeddingsPort


# ── Fast tier ─────────────────────────────────────────────────────────────


def _make_response(json_body: dict[str, Any], status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_adapter_satisfies_embeddings_port() -> None:
    adapter = OllamaEmbeddingsAdapter(base_url="http://localhost:11434")
    assert isinstance(adapter, EmbeddingsPort)


def test_embed_returns_vectors_from_canned_response(monkeypatch) -> None:
    # Pin the model explicitly so the assertion is stable regardless of
    # the ambient OLLAMA_EMBED_MODEL env var (e.g. during a 4B A/B run).
    adapter = OllamaEmbeddingsAdapter(
        base_url="http://localhost:11434",
        default_model="qwen3-embedding:0.6b",
    )

    fake_client = MagicMock(spec=httpx.AsyncClient)
    fake_client.post = AsyncMock(
        return_value=_make_response(
            {
                "model": "qwen3-embedding:0.6b",
                "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            }
        )
    )
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    result = asyncio.run(adapter.embed(texts=["a", "b"]))
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    fake_client.post.assert_awaited_once()
    call_args = fake_client.post.await_args
    assert call_args.args == ("/api/embed",)
    # Forge-OH default: ADR-020 (qwen3-embedding:0.6b) — was upstream Kosmos nomic-embed-text.
    assert call_args.kwargs["json"]["model"] == "qwen3-embedding:0.6b"
    assert call_args.kwargs["json"]["input"] == ["a", "b"]


def test_embed_empty_list_short_circuits_without_http_call(monkeypatch) -> None:
    adapter = OllamaEmbeddingsAdapter(base_url="http://localhost:11434")
    called = False

    def _get_client():
        nonlocal called
        called = True
        return MagicMock()

    monkeypatch.setattr(adapter, "_get_client", _get_client)
    result = asyncio.run(adapter.embed(texts=[]))
    assert result == []
    assert called is False


def test_embed_wrong_count_raises_embedding_error(monkeypatch) -> None:
    adapter = OllamaEmbeddingsAdapter(base_url="http://localhost:11434")
    fake_client = MagicMock(spec=httpx.AsyncClient)
    fake_client.post = AsyncMock(
        return_value=_make_response(
            {"embeddings": [[0.1, 0.2]]}  # only 1 vector for 2 inputs
        )
    )
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    with pytest.raises(EmbeddingError, match="malformed"):
        asyncio.run(adapter.embed(texts=["a", "b"]))


def test_embed_http_error_wrapped_in_embedding_error(monkeypatch) -> None:
    adapter = OllamaEmbeddingsAdapter(base_url="http://localhost:11434")
    fake_client = MagicMock(spec=httpx.AsyncClient)
    fake_client.post = AsyncMock(
        side_effect=httpx.ConnectError("nope", request=MagicMock())
    )
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    with pytest.raises(EmbeddingError, match="ConnectError"):
        asyncio.run(adapter.embed(texts=["a"]))


def test_dimensions_uses_static_table_without_probe(monkeypatch) -> None:
    adapter = OllamaEmbeddingsAdapter(
        base_url="http://localhost:11434", default_model="nomic-embed-text"
    )

    def _forbid_client() -> Any:
        raise AssertionError("dimensions() should not call the backend for a known model")

    monkeypatch.setattr(adapter, "_get_client", _forbid_client)

    dim = asyncio.run(adapter.dimensions())
    assert dim == 768


def test_dimensions_probes_unknown_model(monkeypatch) -> None:
    adapter = OllamaEmbeddingsAdapter(base_url="http://localhost:11434")
    fake_client = MagicMock(spec=httpx.AsyncClient)
    fake_client.post = AsyncMock(
        return_value=_make_response({"embeddings": [[0.0] * 512]})
    )
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    dim = asyncio.run(adapter.dimensions(model="future-experimental-model"))
    assert dim == 512


def test_is_healthy_returns_false_when_backend_unreachable() -> None:
    # Point at a black-hole port; is_healthy MUST NOT raise.
    adapter = OllamaEmbeddingsAdapter(base_url="http://127.0.0.1:1")
    assert adapter.is_healthy() is False


def test_close_is_idempotent() -> None:
    adapter = OllamaEmbeddingsAdapter(base_url="http://localhost:11434")

    async def _run() -> None:
        await adapter.close()
        await adapter.close()

    asyncio.run(_run())


# ── Live tier (Colossus, opt-in) ──────────────────────────────────────────


@pytest.mark.skipif(
    os.environ.get("FORGE_MEMORY_LIVE") != "1",
    reason="Live Ollama tier: set FORGE_MEMORY_LIVE=1 to run",
)
def test_live_default_embedder_matches_declared_dim() -> None:
    """Live-tier smoke: whatever OLLAMA_EMBED_MODEL resolves to (Forge-OH
    default ``qwen3-embedding:0.6b`` per ADR-020, or the ambient env-var
    override for A/B runs), the vector length must match the dimension the
    adapter declares via its ``_MODEL_DIMENSIONS`` table."""
    from openhands_tools_ext.memory.adapters.embeddings.ollama.adapter import (
        _MODEL_DIMENSIONS,
    )

    adapter = OllamaEmbeddingsAdapter()
    resolved_model = adapter._default_model
    expected_dim = _MODEL_DIMENSIONS.get(resolved_model) or _MODEL_DIMENSIONS.get(
        resolved_model.split(":", 1)[0]
    )
    assert expected_dim is not None, (
        f"model {resolved_model!r} missing from _MODEL_DIMENSIONS — add its "
        "native dim to the table before running the live smoke test"
    )

    async def _run() -> list[list[float]]:
        try:
            return await adapter.embed(texts=["hello Forge-OH"])
        finally:
            await adapter.close()

    vectors = asyncio.run(_run())
    assert len(vectors) == 1
    assert len(vectors[0]) == expected_dim, (
        f"live Ollama returned dim={len(vectors[0])} for model "
        f"{resolved_model!r} but adapter table declares {expected_dim}"
    )
