"""
bff/services/mcp_bootstrap.py — idempotent MCP-server registration on
BFF startup. Currently registers Serena when SERENA_ENABLED=true.

Rationale (ADR-018, amended 2026-08-06 01:07 EDT):
- Talks DIRECTLY to agent-server via the shared `openhands_client` that
  `oh_startup()` already initialized. The earlier design of calling our
  own `POST /api/mcp` during lifespan is impossible: uvicorn hasn't bound
  the socket yet when the lifespan startup phase runs, so any attempt
  to connect to `127.0.0.1:8081` from inside the app fails with
  "All connection attempts failed". Observed on Colossus 2026-08-06 01:06 EDT.
- Idempotent: read `agent_settings.mcp_config` first, no-op if `serena`
  is already present.
- Best-effort: any failure logs a warning and lets BFF finish booting.
  Missing Serena must not sink the rest of the app.
- No language gate: Serena upstream already refuses unsupported files.
  See ADR-018 § D4.

Serena launch verb (canonical, per upstream README as of pin sha):
    uvx --from git+https://github.com/oraios/serena@<sha> \\
        serena start-mcp-server --context ide-assistant \\
        --project <workspace>

The plan doc's `python3 -m serena start-mcp-server --workspace <ws>`
example is wrong. See ADR-018 § "Context".

Upstream agent-server endpoints used (same as `bff/routers/mcp.py`):
    GET  /api/settings                       → read mcp_config
    POST /api/settings/mcp/{name}            → register a server
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from bff.settings import Settings

logger = logging.getLogger(__name__)

SERENA_SERVER_ID = "serena"
SERENA_GITHUB_URL = "git+https://github.com/oraios/serena"


def _build_serena_upstream_server(settings: Settings) -> dict[str, Any]:
    """Build the agent-server MCPServer-shaped body used by
    POST /api/settings/mcp/{name}.

    Matches the shape produced by `bff.routers.mcp._build_upstream_server`
    for a stdio server so agent-server treats us the same as a user
    registration.
    """
    pinned_source = f"{SERENA_GITHUB_URL}@{settings.serena_pin_sha}"
    return {
        "enabled": True,
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
        "description": (
            f"Serena LSP MCP server (Stage 4.4). Pinned to "
            f"{settings.serena_pin_sha[:8]}. Workspace: "
            f"{settings.serena_workspace_default}."
        ),
    }


def _mcp_config_from_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Extract mcp_config from a GET /api/settings body. Matches the
    same walk that `bff.routers.mcp._load_mcp_config` performs."""
    if not payload:
        return {}
    agent = payload.get("agent_settings") or {}
    return (agent.get("mcp_config") or {}) or {}


async def register_serena_if_missing(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Register Serena upstream if not already registered.

    Returns one of: "disabled", "already_registered", "registered",
    "error:<summary>". Never raises — all failures are logged and
    swallowed so BFF startup remains resilient.

    `client` defaults to the process-wide `openhands_client.get_client()`
    initialized by `oh_startup()`. Tests inject a MockTransport-backed
    client instead.
    """
    if not settings.serena_enabled:
        logger.info("Serena registration skipped (SERENA_ENABLED=false).")
        return "disabled"

    if client is None:
        # Local import so unit tests don't require openhands_client at
        # module import time.
        from bff.openhands_client import get_client

        try:
            client = get_client()
        except RuntimeError as exc:
            logger.warning("Serena registration: %s", exc)
            return "error:client-not-ready"

    try:
        list_resp = await client.get("/api/settings")
        if list_resp.status_code >= 400:
            logger.warning(
                "Serena registration: GET /api/settings returned %s; skipping.",
                list_resp.status_code,
            )
            return f"error:list-{list_resp.status_code}"

        existing = _mcp_config_from_settings(list_resp.json())
        if SERENA_SERVER_ID in existing:
            logger.info("Serena already registered upstream; no-op.")
            return "already_registered"

        body = _build_serena_upstream_server(settings)
        post_resp = await client.post(
            f"/api/settings/mcp/{SERENA_SERVER_ID}",
            json=body,
        )
        if post_resp.status_code >= 400:
            logger.warning(
                "Serena registration: POST /api/settings/mcp/serena "
                "returned %s: %s",
                post_resp.status_code,
                post_resp.text[:200],
            )
            return f"error:post-{post_resp.status_code}"

        logger.info(
            "Serena registered upstream (pin sha %s).",
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
    "_build_serena_upstream_server",  # exposed for tests
    "_mcp_config_from_settings",
]
