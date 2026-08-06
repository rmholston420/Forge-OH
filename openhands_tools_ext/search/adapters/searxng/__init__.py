# Ported from https://github.com/rmholston420/kosmos/blob/c455165bca0d645f0d43572d0c286dca7033d31d/adapters/search/searxng/__init__.py
# SPDX-License-Identifier: Apache-2.0
# Modifications: import path rewritten to openhands_tools_ext.search.adapters.searxng
"""Consolidated SearXNG adapter for SearchPort (ported from Kosmos ADR-012 + ADR-021)."""

from openhands_tools_ext.search.adapters.searxng.adapter import (
    SearxngAdapter,
    get_searxng_adapter,
)

__all__ = ["SearxngAdapter", "get_searxng_adapter"]
