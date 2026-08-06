"""
bff/services/mcp_bootstrap.py — idempotent MCP-server registration on
BFF startup. Currently registers Serena when SERENA_ENABLED=true.

Rationale (ADR-018):
- Reuses the existing production wire (POST /api/mcp) rather than
  building a startup-only registry. If the passthrough works for the
  UI, it must work for us.
- Idempotent: check GET /api/mcp first, no-op if id="serena" exists.
- Best-effort: any failure logs a warning and lets BFF finish booting.
  Missing Serena must not sink the rest of the app.
- No language gate: Serena upstream already refuses unsupported files.
  See ADR-018 § "language-allowlist rejected".

Serena launch verb (canonical, per upstream README as of pin sha):
    uvx --from git+https://github.com/oraios/serena@<sha> \\
        serena start-mcp-server --context ide-assistant \\
        --project <workspace>

The plan doc's `python3 -m serena start-mcp-server --workspace <ws>`
example is wrong. See ADR-018 § "spec corrections".
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from bff.settings import Settings

logger = logging.getLogger(__name__)

SERENA_SERVER_ID = "serena"
SERENA_GITHUB_URL = "git+https://github.com/oraios/serena"


def _build_serena_registration_body(settings: Settings) -> dict[str, Any]:
    """Build the RegisterMcpRequest-shaped body used by POST /api/mcp.

    Matches bff.routers.mcp.RegisterMcpRequest field-for-field so the
    router's own validation is our contract test.
    """
    pinned_source = f"{SERENA_GITHUB_URL}@{settings.serena_pin_sha}"
    return {
        "name": SERENA_SERVER_ID,
        "transport": "stdio",
        "command": "uvx",
        "args": [
            "--from",
            pinned_source,
            "serena",
            "start-mcp-server",
            "--context",
            "ide-assistant",
            "--project",
            settings.serena_workspace_default,
        ],
        "enabled": True,
        "description": (
            f"Serena LSP MCP server (Stage 4.4). Pinned to "
            f"{settings.serena_pin_sha[:8]}. Workspace: "
            f"{settings.serena_workspace_default}."
        ),
    }


async def _bff_client(bff_base_url: str) -> httpx.AsyncClient:
    """Small httpx client scoped to BFF's own /api surface.

    We call BFF's own /api/mcp endpoint rather than reaching directly
    into agent-server so the passthrough's reshape + upstream posting
    is exercised at boot too. If the passthrough is broken, we want
    to know at startup, not at first user click.
    """
    return httpx.AsyncClient(base_url=bff_base_url, timeout=10.0)


async def register_serena_if_missing(
    settings: Settings,
    *,
    bff_base_url: str | None = None,
) -> str:
    """Register Serena via POST /api/mcp if not already registered.

    Returns one of: "disabled", "already_registered", "registered",
    "error:<summary>". Never raises — all failures are logged and swallowed
    so BFF startup remains resilient.

    `bff_base_url` defaults to http://<bff_host>:<bff_port> so tests can
    override with a mock server URL.
    """
    if not settings.serena_enabled:
        logger.info("Serena registration skipped (SERENA_ENABLED=false).")
        return "disabled"

    base = bff_base_url or f"http://{settings.bff_host}:{settings.bff_port}"

    try:
        async with await _bff_client(base) as client:
            list_resp = await client.get("/api/mcp")
            if list_resp.status_code >= 400:
                logger.warning(
                    "Serena registration: GET /api/mcp returned %s; skipping.",
                    list_resp.status_code,
                )
                return f"error:list-{list_resp.status_code}"

            existing = list_resp.json() or []
            if any(
                isinstance(s, dict) and s.get("id") == SERENA_SERVER_ID
                for s in existing
            ):
                logger.info("Serena already registered upstream; no-op.")
                return "already_registered"

            body = _build_serena_registration_body(settings)
            post_resp = await client.post("/api/mcp", json=body)
            if post_resp.status_code >= 400:
                logger.warning(
                    "Serena registration: POST /api/mcp returned %s: %s",
                    post_resp.status_code,
                    post_resp.text[:200],
                )
                return f"error:post-{post_resp.status_code}"

            logger.info(
                "Serena registered via POST /api/mcp (pin sha %s).",
                settings.serena_pin_sha[:8],
            )
            return "registered"
    except Exception as exc:  # noqa: BLE001 — startup must never crash
        logger.warning("Serena registration failed (%s); continuing.", exc)
        return f"error:exception-{type(exc).__name__}"


__all__ = [
    "SERENA_SERVER_ID",
    "SERENA_GITHUB_URL",
    "register_serena_if_missing",
    "_build_serena_registration_body",  # exposed for tests
]
