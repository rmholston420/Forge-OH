# Ported from https://github.com/rmholston420/kosmos/blob/c455165bca0d645f0d43572d0c286dca7033d31d/adapters/search/searxng/test_contract.py
# SPDX-License-Identifier: Apache-2.0
# Modifications: import paths rewritten (ports.search / adapters.search.searxng -> openhands_tools_ext.search.*); provenance assertion updated to Forge-OH default port.
"""Contract test — SearxngAdapter satisfies SearchPort (Forge-OH Stage 6.1)."""

from __future__ import annotations

import asyncio

import pytest

from openhands_tools_ext.search.adapters.searxng import SearxngAdapter
from openhands_tools_ext.search.ports.search import SearchPort, SearchResponse


def test_searxng_adapter_satisfies_search_port_protocol() -> None:
    """SearxngAdapter must satisfy the SearchPort runtime-checkable Protocol."""
    adapter = SearxngAdapter(base_url="http://example.invalid")
    assert isinstance(adapter, SearchPort), (
        "SearxngAdapter does not satisfy SearchPort — check method signatures"
    )


def test_search_returns_empty_response_on_backend_failure() -> None:
    """On network failure the adapter MUST return an empty SearchResponse,
    NOT raise — per SearchPort docstring."""
    adapter = SearxngAdapter(base_url="http://127.0.0.1:1")  # nothing listening
    resp = asyncio.run(adapter.search("hello world", num_results=5))

    assert isinstance(resp, SearchResponse)
    assert resp.query == "hello world"
    assert resp.results == []
    assert resp.total == 0
    assert resp.provenance == "searxng:http://127.0.0.1:1"
    assert resp.latency_ms >= 0


def test_provenance_field_is_populated() -> None:
    """ADR-021 mandates provenance on every SearchResponse."""
    adapter = SearxngAdapter(base_url="http://localhost:18888")
    assert adapter.provenance == "searxng:http://localhost:18888"


def test_is_healthy_does_not_raise_on_unreachable_backend() -> None:
    adapter = SearxngAdapter(base_url="http://127.0.0.1:1")
    result = asyncio.run(adapter.is_healthy())
    assert result is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_results": 5},
        {"num_results": 5, "language": "en"},
        {"num_results": 5, "engines": ["duckduckgo"]},
        {"num_results": 5, "language": "es", "engines": ["duckduckgo", "brave"]},
    ],
)
def test_search_accepts_documented_kwargs(kwargs: dict) -> None:
    """SearchPort.search kwargs are all keyword-only per ADR-021."""
    adapter = SearxngAdapter(base_url="http://127.0.0.1:1")
    resp = asyncio.run(adapter.search("q", **kwargs))
    assert isinstance(resp, SearchResponse)
