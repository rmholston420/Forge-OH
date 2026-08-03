"""
bff/routers/repograph.py

RepoGraph HTTP surface for the code knowledge graph (Slice D, Recommendation
#1 from the improvement research report).

Endpoints land in slices:
  D.1: GET  /api/repograph/health      \u2014 verify Neo4j connectivity
  D.4: POST /api/repograph/index       \u2014 build/refresh graph for a workspace
       GET  /api/repograph/search      \u2014 symbol search
       GET  /api/repograph/callers
       GET  /api/repograph/callees
       GET  /api/repograph/co_changed
       POST /api/repograph/context_bundle

Every endpoint respects the `repograph_enabled` setting; when disabled, the
router returns 503 without contacting Neo4j so a misconfigured deploy fails
loudly instead of silently.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from bff.deps.neo4j_driver import get_default_database, get_neo4j_driver
from bff.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repograph", tags=["repograph"])


class HealthResponse(BaseModel):
    """Result of `GET /api/repograph/health`."""

    enabled: bool
    reachable: bool
    bolt_uri: str
    database: str
    neo4j_version: str | None = None
    neo4j_edition: str | None = None
    error: str | None = None


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Verify Neo4j reachability for the RepoGraph subsystem",
)
def repograph_health() -> HealthResponse:
    """Return whether Neo4j is reachable and the configured database is online.

    Always returns 200 (even on failure) so the caller can distinguish
    "endpoint exists but Neo4j is down" from "endpoint missing".
    """
    settings = get_settings()
    if not settings.repograph_enabled:
        return HealthResponse(
            enabled=False,
            reachable=False,
            bolt_uri=settings.neo4j_bolt_uri,
            database=settings.neo4j_database,
            error="repograph_enabled=False (set REPOGRAPH_ENABLED=true after verifying Neo4j)",
        )

    driver = get_neo4j_driver()
    if driver is None:
        return HealthResponse(
            enabled=True,
            reachable=False,
            bolt_uri=settings.neo4j_bolt_uri,
            database=settings.neo4j_database,
            error="driver init failed \u2014 check NEO4J_PASSWORD in ~/dev/forge-oh/.env.neo4j",
        )

    database = get_default_database()
    try:
        with driver.session(database=database) as session:
            # `CALL dbms.components()` returns rows like
            # (name='Neo4j Kernel', versions=['5.26.27'], edition='community')
            record = session.run(
                "CALL dbms.components() YIELD name, versions, edition "
                "WHERE name = 'Neo4j Kernel' RETURN versions[0] AS version, edition"
            ).single()
            version = record["version"] if record else None
            edition = record["edition"] if record else None
            return HealthResponse(
                enabled=True,
                reachable=True,
                bolt_uri=settings.neo4j_bolt_uri,
                database=database,
                neo4j_version=version,
                neo4j_edition=edition,
            )
    except Exception as exc:
        logger.exception("Neo4j health check failed")
        return HealthResponse(
            enabled=True,
            reachable=False,
            bolt_uri=settings.neo4j_bolt_uri,
            database=database,
            error=f"{type(exc).__name__}: {exc}",
        )


# --- D.4 endpoints land here in a follow-up slice ------------------------------


def _reject_if_disabled() -> None:
    """Common guard for D.4 endpoints. Raises 503 if the subsystem is off."""
    if not get_settings().repograph_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RepoGraph is disabled. Set REPOGRAPH_ENABLED=true after verifying Neo4j.",
        )
