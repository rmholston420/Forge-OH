"""
bff/deps/neo4j_driver.py

Lazy Neo4j driver dependency for the RepoGraph subsystem.

Design:
- The driver is created on first use, not at import time, so the BFF starts
  cleanly even if Neo4j is offline.
- The driver is a singleton — one connection pool per process, per
  Neo4j's own recommendation.
- Callers `close_neo4j_driver()` on FastAPI shutdown to flush the pool.
- If the RepoGraph subsystem is disabled or unconfigured, `get_neo4j_driver`
  returns None so routers can short-circuit with 503.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from neo4j import Driver, GraphDatabase

from bff.settings import get_settings

logger = logging.getLogger(__name__)

# Module-level singleton. Populated by `get_neo4j_driver()` on first successful
# connection and reused across requests. We do not use `@lru_cache` on the
# constructor itself because we want the ability to reset it in tests via
# `reset_neo4j_driver()`.
_driver: Driver | None = None


def get_neo4j_driver() -> Driver | None:
    """Return the shared Neo4j driver, creating it lazily on first call.

    Returns None if the RepoGraph subsystem is disabled or no password is
    configured; callers should treat None as "service unavailable".
    """
    global _driver
    if _driver is not None:
        return _driver

    settings = get_settings()
    if not settings.repograph_enabled:
        logger.debug("Neo4j driver requested but repograph_enabled=False")
        return None
    if not settings.neo4j_password:
        logger.warning(
            "Neo4j driver requested but neo4j_password is empty; populate ~/dev/forge-oh/.env.neo4j"
        )
        return None

    try:
        _driver = GraphDatabase.driver(
            settings.neo4j_bolt_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            # Keep the pool small — single-user local workstation, not a
            # server-side workload.
            max_connection_pool_size=10,
            connection_acquisition_timeout=15,
        )
        logger.info(
            "Neo4j driver initialised: uri=%s database=%s",
            settings.neo4j_bolt_uri,
            settings.neo4j_database,
        )
        return _driver
    except Exception as exc:
        logger.exception("Failed to initialise Neo4j driver: %s", exc)
        _driver = None
        return None


def close_neo4j_driver() -> None:
    """Close the shared driver on shutdown. Idempotent."""
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        finally:
            _driver = None


def reset_neo4j_driver() -> None:
    """Clear the singleton (test helper only)."""
    global _driver
    _driver = None


@lru_cache(maxsize=1)
def _get_default_database() -> str:
    return get_settings().neo4j_database


def get_default_database() -> str:
    """Return the configured Neo4j database name for RepoGraph writes."""
    return _get_default_database()
