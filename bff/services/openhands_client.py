"""
bff/services/openhands_client.py

Backward-compatibility shim.

The canonical OpenHands HTTP client lives at bff/openhands_client.py
(module-level singleton with startup/shutdown lifecycle helpers).

This file previously contained a class-based duplicate (OpenHandsClient)
that maintained its own httpx.AsyncClient per-instance, bypassing the
shared lifespan-managed connection and hardcoding port 8080.

All new code should import from bff.openhands_client directly:
    from bff.openhands_client import get_client, startup, shutdown

This shim re-exports the essentials so any existing import of
bff.services.openhands_client continues to resolve without errors.
"""
from bff.openhands_client import get_client, startup, shutdown  # noqa: F401

__all__ = ["get_client", "startup", "shutdown"]
