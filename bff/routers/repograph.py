"""
bff/routers/repograph.py

RepoGraph HTTP surface for the code knowledge graph (Slice D, Recommendation
#1 from the improvement research report).

Endpoints:
  D.1  GET  /api/repograph/health          verify Neo4j connectivity
  D.4  POST /api/repograph/index           build/refresh graph for a workspace
  D.4  GET  /api/repograph/search          symbol-name search
  D.4  GET  /api/repograph/callers         callers of a symbol
  D.4  GET  /api/repograph/callees         callees from a file
  D.4  GET  /api/repograph/co_changed      files that co-change with a target
  D.4  POST /api/repograph/context_bundle  PageRank-ranked context for seeds

Every endpoint respects ``repograph_enabled``; when disabled they return
503 without contacting Neo4j so a misconfigured deploy fails loudly.
"""

from __future__ import annotations

import logging
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from bff.deps.neo4j_driver import get_default_database, get_neo4j_driver
from bff.services import repograph_registry
from bff.settings import get_settings
from openhands_tools_ext.repograph.index import build_index
from openhands_tools_ext.repograph.store import Neo4jStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repograph", tags=["repograph"])


# --- Common response / helper types ---------------------------------------


class HealthResponse(BaseModel):
    """Result of `GET /api/repograph/health`."""

    enabled: bool
    reachable: bool
    bolt_uri: str
    database: str
    neo4j_version: str | None = None
    neo4j_edition: str | None = None
    error: str | None = None


class IndexRequest(BaseModel):
    workspace_path: str = Field(
        ...,
        description="Absolute path to the repo root to index.",
        min_length=1,
    )
    compute_pagerank: bool = Field(
        default=True,
        description="Compute PageRank scores as part of the index. Fast for "
        "small repos; disable if you don't care about ranking.",
    )


class IndexResponse(BaseModel):
    repo_key: str
    workspace_path: str
    stats: dict[str, int]


class SymbolOut(BaseModel):
    rel_path: str
    name: str
    category: str
    start_line: int
    end_line: int
    parent: str | None = None
    info: str = ""
    pagerank: float = 0.0


class CallerOut(BaseModel):
    caller_file: str
    callee_file: str
    callee: str
    callee_line: int
    call_line: int


class CalleeOut(BaseModel):
    callee_file: str
    callee: str
    category: str
    callee_line: int
    call_line: int
    pagerank: float = 0.0


class CoChangedOut(BaseModel):
    rel_path: str
    commits: int


class CoChangedResponse(BaseModel):
    target: str
    window: int
    files: list[CoChangedOut]
    available: bool = True
    error: str | None = None


class ContextBundleRequest(BaseModel):
    repo_key: str
    seeds: list[str] = Field(
        ...,
        description="Repo-relative paths of the seed files to expand from.",
        min_length=1,
    )
    limit: int = Field(default=40, ge=1, le=500)


class GraphNodeOut(BaseModel):
    id: str
    kind: Literal["file", "symbol"]
    label: str
    rel_path: str
    # symbol-only
    category: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    parent: str | None = None
    pagerank: float | None = None
    # file-only
    language: str | None = None


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    type: Literal["CONTAINS", "CALLS"]
    line: int | None = None


class GraphStatsOut(BaseModel):
    nodes: int
    symbols: int
    files: int
    edges: int


class FullGraphResponse(BaseModel):
    repo_key: str
    nodes: list[GraphNodeOut]
    links: list[GraphEdgeOut]
    stats: GraphStatsOut


# --- Guards ---------------------------------------------------------------


def _reject_if_disabled() -> None:
    """503 if the subsystem is off. Every D.4 endpoint calls this first."""
    if not get_settings().repograph_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RepoGraph is disabled. Set REPOGRAPH_ENABLED=true after verifying Neo4j.",
        )


def _get_store() -> Neo4jStore:
    """Return a live Neo4jStore or raise 503."""
    driver = get_neo4j_driver()
    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j driver unavailable. Check NEO4J_PASSWORD in ~/dev/forge-oh/.env.neo4j.",
        )
    return Neo4jStore(driver=driver, database=get_default_database())


# --- Health ---------------------------------------------------------------


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


# --- D.4 endpoints --------------------------------------------------------


@router.post(
    "/index",
    response_model=IndexResponse,
    summary="Build (or refresh) the structural graph for a workspace",
)
def repograph_index(req: IndexRequest) -> IndexResponse:
    """Index a workspace path into Neo4j.

    Idempotent: subsequent calls with the same workspace_path replace the
    previous graph for that repo (DETACH DELETE + MERGE). Also registers
    the workspace so subsequent endpoints (``co_changed``) can find the
    on-disk repo.
    """
    _reject_if_disabled()

    path = Path(req.workspace_path).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"workspace_path is not a directory: {path}",
        )

    logger.info("indexing repograph workspace: %s", path)
    idx = build_index(path, compute_pagerank=req.compute_pagerank)
    store = _get_store()
    store.ensure_schema()
    stats = store.replace_repo(idx)
    repograph_registry.register(idx.repo_key, path)

    return IndexResponse(
        repo_key=idx.repo_key,
        workspace_path=str(path),
        stats=stats,
    )


@router.get(
    "/search",
    response_model=list[SymbolOut],
    summary="Search symbols by name (case-insensitive substring)",
)
def repograph_search(
    repo_key: str = Query(..., min_length=1),
    q: str = Query(..., min_length=1, description="Substring to match."),
    limit: int = Query(50, ge=1, le=500),
) -> list[SymbolOut]:
    _reject_if_disabled()
    rows = _get_store().search_by_name(repo_key, q, limit=limit)
    return [SymbolOut(**_row_to_symbol(r)) for r in rows]


@router.get(
    "/callers",
    response_model=list[CallerOut],
    summary="Files that call a given symbol",
)
def repograph_callers(
    repo_key: str = Query(..., min_length=1),
    name: str = Query(..., min_length=1),
    rel_path: str | None = Query(
        None,
        description="Optional: restrict to a symbol defined in this specific file.",
    ),
    limit: int = Query(50, ge=1, le=500),
) -> list[CallerOut]:
    _reject_if_disabled()
    rows = _get_store().callers_of(repo_key, name, rel_path=rel_path, limit=limit)
    return [CallerOut(**r) for r in rows]


@router.get(
    "/callees",
    response_model=list[CalleeOut],
    summary="All symbols called from a given file",
)
def repograph_callees(
    repo_key: str = Query(..., min_length=1),
    rel_path: str = Query(..., min_length=1),
    limit: int = Query(100, ge=1, le=500),
) -> list[CalleeOut]:
    _reject_if_disabled()
    rows = _get_store().callees_of(repo_key, rel_path, limit=limit)
    return [CalleeOut(**r) for r in rows]


@router.get(
    "/co_changed",
    response_model=CoChangedResponse,
    summary="Files that changed in the same commits as a target (git log)",
)
def repograph_co_changed(
    repo_key: str = Query(..., min_length=1),
    rel_path: str = Query(..., min_length=1),
    window: int = Query(
        50,
        ge=1,
        le=1000,
        description="How many recent commits touching the target file to consider.",
    ),
    limit: int = Query(20, ge=1, le=200),
) -> CoChangedResponse:
    """Return files that historically change together with ``rel_path``.

    Uses ``git log`` over the workspace registered for ``repo_key`` \u2014
    Neo4j is not involved. This is a pragmatic signal for the ranker in
    D.5 (files that co-change are usually semantically related).
    """
    _reject_if_disabled()

    entry = repograph_registry.lookup(repo_key)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No workspace registered for repo_key={repo_key}. "
                "Call POST /api/repograph/index first."
            ),
        )

    try:
        files, error = _git_co_changed(
            Path(entry.absolute_path),
            rel_path,
            window=window,
            limit=limit,
        )
    except FileNotFoundError:
        return CoChangedResponse(
            target=rel_path,
            window=window,
            files=[],
            available=False,
            error="git not found in this environment",
        )

    return CoChangedResponse(
        target=rel_path,
        window=window,
        files=[CoChangedOut(rel_path=f, commits=c) for f, c in files],
        available=error is None,
        error=error,
    )


@router.get(
    "/graph",
    response_model=FullGraphResponse,
    summary="Top-N PageRank symbols with their files and CONTAINS/CALLS edges",
)
def repograph_graph(
    repo_key: str = Query(..., min_length=1),
    limit: int = Query(500, ge=1, le=2000),
) -> FullGraphResponse:
    """Return a graph-shaped view suitable for a force-directed layout.

    Selection is top-``limit`` symbols by PageRank plus every file that
    contains any of them; edges are CONTAINS (File→Symbol) and CALLS
    (File→Symbol) restricted to that set. METHOD_OF and UNRESOLVED_CALL
    are excluded from v1 to keep the graph shape uniformly bipartite.
    """
    _reject_if_disabled()
    data = _get_store().full_graph(repo_key, limit=limit)
    return FullGraphResponse(
        repo_key=repo_key,
        nodes=[GraphNodeOut(**n) for n in data["nodes"]],
        links=[GraphEdgeOut(**e) for e in data["links"]],
        stats=GraphStatsOut(**data["stats"]),
    )


@router.post(
    "/context_bundle",
    response_model=list[SymbolOut],
    summary="PageRank-ranked context symbols for a set of seed files",
)
def repograph_context_bundle(req: ContextBundleRequest) -> list[SymbolOut]:
    """Return the top symbols connected to a seed-file set, ranked by PageRank.

    Downstream callers (D.5's frontend Trace panel and the OpenHands tool
    that will land in D.5) treat this as the agent's read-list: "given
    these files matter, here are the other symbols most likely to matter."
    """
    _reject_if_disabled()
    rows = _get_store().context_bundle(req.repo_key, req.seeds, limit=req.limit)
    return [SymbolOut(**_row_to_symbol(r)) for r in rows]


# --- Internals ------------------------------------------------------------


def _row_to_symbol(row: dict[str, Any]) -> dict[str, Any]:
    """Neo4j returns None for missing string fields; coerce to defaults."""
    return {
        "rel_path": row["rel_path"],
        "name": row["name"],
        "category": row["category"],
        "start_line": row["start_line"],
        "end_line": row["end_line"],
        "parent": row.get("parent"),
        "info": row.get("info") or "",
        "pagerank": row.get("pagerank") or 0.0,
    }


def _git_co_changed(
    workspace: Path,
    rel_path: str,
    *,
    window: int,
    limit: int,
) -> tuple[list[tuple[str, int]], str | None]:
    """Return list of (rel_path, commit_count) sorted by count, plus optional error.

    Implementation:
      1. `git log -n <window> --pretty=format:%H -- <rel_path>` -> commit shas
      2. For each sha: `git show --name-only --pretty=format: <sha>` -> files
      3. Count files (excluding the target) across all commits.
    """
    try:
        log = subprocess.run(
            ["git", "log", "-n", str(window), "--pretty=format:%H", "--", rel_path],
            check=False,
            capture_output=True,
            text=True,
            cwd=workspace,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return [], "git log timed out"

    if log.returncode != 0:
        return [], f"git log failed: {log.stderr.strip() or log.returncode}"

    shas = [line.strip() for line in log.stdout.splitlines() if line.strip()]
    if not shas:
        return [], None

    counts: Counter[str] = Counter()
    for sha in shas:
        try:
            show = subprocess.run(
                ["git", "show", "--name-only", "--pretty=format:", sha],
                check=False,
                capture_output=True,
                text=True,
                cwd=workspace,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            continue
        if show.returncode != 0:
            continue
        for line in show.stdout.splitlines():
            f = line.strip()
            if not f or f == rel_path:
                continue
            counts[f] += 1

    top = counts.most_common(limit)
    return [(f, c) for f, c in top], None
