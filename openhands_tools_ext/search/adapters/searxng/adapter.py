# Ported from https://github.com/rmholston420/kosmos/blob/c455165bca0d645f0d43572d0c286dca7033d31d/adapters/search/searxng/adapter.py
# SPDX-License-Identifier: Apache-2.0
# Modifications:
#   - Import path rewritten (ports.search -> openhands_tools_ext.search.ports.search).
#   - Env var renamed KOSMOS_SEARXNG_BASE_URL -> FORGE_SEARXNG_BASE_URL.
#   - Default base URL 127.0.0.1:8888 -> 127.0.0.1:18888 (avoids Kosmos ADR-010 port collision).
#   - User-Agent rewritten KosmosSearchAdapter -> ForgeOHSearchAdapter.
"""Consolidated SearXNG adapter — Forge-OH Stage 6.1 (ported from Kosmos ADR-012 + ADR-021).

Implements SearchPort. Merges two donor sources (via Kosmos):

- Rigpa-LMS/backend/src/rigpa/domains/integrations/searxng.py  (JSON-only, typed response, engine list, language param)
- axiom/packages/axiom_providers/searxng.py                    (HTML fallback for 403, User-Agent, follow_redirects)

Design rules locked in by Kosmos ADR-021 and honored here verbatim:
    - provenance is mandatory on every SearchResponse
    - keyword-only kwargs on search()
    - HTML-fallback is adapter-internal (not part of the port contract)
    - Callers depend on SearchPort, not on this module
"""

from __future__ import annotations

import logging
import os
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import httpx

from openhands_tools_ext.search.ports.search import SearchResponse, SearchResult

log = logging.getLogger(__name__)

_USER_AGENT = "ForgeOHSearchAdapter/0.1 (+local; rmholston420/Forge-OH)"


def _default_base_url() -> str:
    return os.environ.get("FORGE_SEARXNG_BASE_URL", "http://127.0.0.1:18888").rstrip("/")


# ---------------------------------------------------------------------------
# HTML fallback parser (from axiom donor, minor cleanup)
# ---------------------------------------------------------------------------

class _SearxHTMLParser(HTMLParser):
    """Parse SearXNG's HTML result page when JSON is forbidden (HTTP 403)."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.results: list[SearchResult] = []
        self._in_result = False
        self._in_link = False
        self._in_content = False
        self._href = ""
        self._title_parts: list[str] = []
        self._content_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        class_attr = attrs_dict.get("class") or ""

        if tag == "article" and "result" in class_attr.split():
            self._in_result = True
            self._href = ""
            self._title_parts = []
            self._content_parts = []

        if not self._in_result:
            return

        if tag == "a" and "result__url" not in class_attr:
            href = attrs_dict.get("href")
            if href and not self._href:
                self._in_link = True
                self._href = urljoin(self.base_url, href)

        if tag in {"p", "div"} and (
            "content" in class_attr
            or "result-content" in class_attr
            or "result__content" in class_attr
        ):
            self._in_content = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._in_link = False
        if tag in {"p", "div"}:
            self._in_content = False
        if tag == "article" and self._in_result:
            title = " ".join(" ".join(self._title_parts).split())
            snippet = " ".join(" ".join(self._content_parts).split())
            if self._href and title:
                self.results.append(
                    SearchResult(title=title, url=self._href, snippet=snippet)
                )
            self._in_result = False

    def handle_data(self, data: str) -> None:
        if self._in_result and self._in_link:
            self._title_parts.append(data)
        elif self._in_result and self._in_content:
            self._content_parts.append(data)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class SearxngAdapter:
    """Async SearXNG search adapter implementing SearchPort."""

    def __init__(self, *, base_url: str | None = None, timeout_seconds: float = 30.0) -> None:
        self._base_url = (base_url or _default_base_url()).rstrip("/")
        self._timeout = timeout_seconds
        self._headers = {
            "User-Agent": _USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        }

    @property
    def provenance(self) -> str:
        """Provenance string forwarded verbatim into MemoryPort."""
        return f"searxng:{self._base_url}"

    async def search(
        self,
        query: str,
        *,
        num_results: int = 10,
        language: str = "en",
        engines: list[str] | None = None,
    ) -> SearchResponse:
        """Run a SearXNG search; on backend failure return an empty response."""
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "language": language,
            "pageno": 1,
        }
        if engines:
            params["engines"] = ",".join(engines)

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=self._headers, follow_redirects=True
            ) as client:
                resp = await client.get(f"{self._base_url}/search", params=params)

                # HTML fallback for public SearXNG instances that block format=json.
                if resp.status_code == 403:
                    log.warning(
                        "searxng_json_forbidden_falling_back_to_html",
                        extra={"base_url": self._base_url},
                    )
                    html_params = {"q": query, "language": language}
                    html_resp = await client.get(
                        f"{self._base_url}/search", params=html_params
                    )
                    html_resp.raise_for_status()
                    parser = _SearxHTMLParser(self._base_url)
                    parser.feed(html_resp.text)
                    hits = parser.results[:num_results]
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    return SearchResponse(
                        query=query,
                        results=hits,
                        total=len(hits),
                        provenance=self.provenance,
                        latency_ms=latency_ms,
                    )

                resp.raise_for_status()
                data = resp.json()

        except Exception as exc:  # noqa: BLE001
            log.warning("searxng_search_failed", extra={"error": str(exc)})
            latency_ms = int((time.perf_counter() - started) * 1000)
            return SearchResponse(
                query=query,
                results=[],
                total=0,
                provenance=self.provenance,
                latency_ms=latency_ms,
            )

        hits = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", "") or "",
                engine=r.get("engine"),
                score=r.get("score"),
            )
            for r in data.get("results", [])[:num_results]
        ]
        latency_ms = int((time.perf_counter() - started) * 1000)
        return SearchResponse(
            query=query,
            results=hits,
            total=len(hits),
            provenance=self.provenance,
            latency_ms=latency_ms,
        )

    async def is_healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=self._headers) as client:
                resp = await client.get(f"{self._base_url}/healthz")
                if resp.status_code == 200:
                    return True
                # Some SearXNG deployments lack /healthz; fall back to root
                resp = await client.get(f"{self._base_url}/")
                return resp.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_adapter: SearxngAdapter | None = None


def get_searxng_adapter() -> SearxngAdapter:
    global _adapter
    if _adapter is None:
        _adapter = SearxngAdapter()
    return _adapter
