"""bff/deps/memory_port.py — lazy MemoryPort singleton for BFF routers.

Stage 5.6a (ADR-024 K1). Provides the memory-inspector router (and any
future memory-consuming router) with a single shared ``DozerDbMemoryAdapter``
instance composed lazily from env vars via
``openhands_tools_ext.memory.composition.make_memory_adapter``.

Design constraints:
- Lazy: BFF must boot cleanly on machines without NEO4J_PASSWORD (dev
  laptops, CI). ``get_memory_port()`` returns ``None`` in that case and
  the router 503s.
- Singleton: one adapter per BFF process. The composition builds an
  ``AsyncGraphDatabase`` driver pool which we must not multiply.
- Cheap teardown: ``close_memory_port()`` is idempotent and safe to call
  in lifespan shutdown even when the port was never initialised.
- Test-friendly: ``reset_memory_port()`` clears the singleton so tests
  can inject their own adapter.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from openhands_tools_ext.memory.ports.memory import MemoryPort

logger = logging.getLogger(__name__)

_port: Optional[MemoryPort] = None
_init_error: Optional[str] = None


def get_memory_port() -> Optional[MemoryPort]:
    """Return the shared MemoryPort, composing it on first call.

    Returns None when NEO4J_PASSWORD is unset (dev boot without memory
    infra); callers should treat None as "memory service unavailable"
    and reply 503.
    """
    global _port, _init_error
    if _port is not None:
        return _port
    if _init_error is not None:
        # Already tried and failed this process; don't hammer.
        return None

    if not os.getenv("NEO4J_PASSWORD"):
        logger.info(
            "MemoryPort requested but NEO4J_PASSWORD is unset; "
            "returning None (populate ~/dev/forge-oh/.env.neo4j)"
        )
        return None

    try:
        from openhands_tools_ext.memory.composition import make_memory_adapter

        _port = make_memory_adapter()
        logger.info("MemoryPort initialised via composition.make_memory_adapter")
        return _port
    except Exception as exc:
        _init_error = f"{type(exc).__name__}: {exc}"
        logger.exception("Failed to compose MemoryPort: %s", exc)
        return None


async def close_memory_port() -> None:
    """Idempotent teardown. Safe to call in lifespan shutdown."""
    global _port, _init_error
    port = _port
    _port = None
    _init_error = None
    if port is None:
        return
    try:
        await port.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("MemoryPort close swallowed error: %s", exc)


def reset_memory_port(injected: Optional[MemoryPort] = None) -> None:
    """Test helper. Replace or clear the singleton without going through env."""
    global _port, _init_error
    _port = injected
    _init_error = None
