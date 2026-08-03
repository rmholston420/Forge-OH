"""
Repository indexer — walks a repo, extracts tags, and builds an in-memory
graph of files + symbols + edges ready to persist to Neo4j (see store.py).

This module is pure Python; it does not talk to Neo4j directly. The Neo4j
store consumes a ``RepoIndex`` produced here.

Pipeline:

  repo_root
      -> iter_source_files (respects .gitignore via `git ls-files`)
      -> extract_tags per file
      -> resolve_references (match REF names to DEF nodes)
      -> networkx DiGraph -> PageRank scores
      -> RepoIndex(files, symbols, calls, unresolved_calls, ranks, repo_key)
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from openhands_tools_ext.repograph.parser import (
    SUPPORTED_LANGUAGES,
    Tag,
    TagCategory,
    TagKind,
    extract_tags,
    language_for_path,
)

logger = logging.getLogger(__name__)


# Composite key that uniquely identifies a symbol within a repo.
SymbolKey = tuple[str, str, int]  # (rel_path, name, start_line)


@dataclass(frozen=True)
class FileNode:
    rel_path: str
    language: str


@dataclass(frozen=True)
class SymbolNode:
    rel_path: str
    name: str
    category: str  # TagCategory.value
    start_line: int
    end_line: int
    parent: str | None
    info: str
    pagerank: float = 0.0

    @property
    def key(self) -> SymbolKey:
        return (self.rel_path, self.name, self.start_line)


@dataclass(frozen=True)
class CallEdge:
    """A resolved call: file X calls symbol Y."""

    src_rel_path: str
    dst_symbol_key: SymbolKey
    callee_name: str
    line: int


@dataclass(frozen=True)
class UnresolvedCall:
    """A call whose callee name did not match any known definition."""

    src_rel_path: str
    callee_name: str
    line: int


@dataclass(frozen=True)
class MethodOfEdge:
    method_key: SymbolKey
    class_key: SymbolKey


@dataclass
class RepoIndex:
    """Everything needed to persist a repo's structural graph to Neo4j."""

    repo_root: str
    repo_key: str  # sha1(repo_root) truncated to 12 chars \u2014 stable per absolute path
    files: list[FileNode] = field(default_factory=list)
    symbols: dict[SymbolKey, SymbolNode] = field(default_factory=dict)
    calls: list[CallEdge] = field(default_factory=list)
    unresolved_calls: list[UnresolvedCall] = field(default_factory=list)
    method_edges: list[MethodOfEdge] = field(default_factory=list)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "files": len(self.files),
            "symbols": len(self.symbols),
            "calls": len(self.calls),
            "unresolved_calls": len(self.unresolved_calls),
            "method_edges": len(self.method_edges),
        }


# --- File discovery --------------------------------------------------------


def iter_source_files(
    repo_root: str | Path,
    *,
    fallback_to_walk: bool = True,
) -> list[Path]:
    """List source files under ``repo_root`` that our extractor supports.

    Uses ``git ls-files`` when the repo is a git checkout (respects
    .gitignore automatically). Falls back to a plain os.walk with a small
    hard-coded blocklist otherwise \u2014 useful for tests that use fresh
    tmp dirs.
    """
    root = Path(repo_root).resolve()
    if (root / ".git").exists():
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            paths = [root / line.strip() for line in proc.stdout.splitlines() if line.strip()]
            return [p for p in paths if p.is_file() and language_for_path(p) is not None]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            if not fallback_to_walk:
                raise

    return _fallback_walk(root)


_FALLBACK_BLOCKLIST = {
    ".git",
    "node_modules",
    ".venv",
    ".oh-venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def _fallback_walk(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _FALLBACK_BLOCKLIST for part in p.relative_to(root).parts):
            continue
        if language_for_path(p) is not None:
            out.append(p)
    return out


# --- Index construction ----------------------------------------------------


def build_index(
    repo_root: str | Path,
    *,
    files: Iterable[Path] | None = None,
    compute_pagerank: bool = True,
) -> RepoIndex:
    """Build a full ``RepoIndex`` for a repo.

    Args:
        repo_root: Absolute path to the repo root.
        files: Optional pre-filtered iterable of files to index. Used by
            tests to control the file set. Defaults to iter_source_files.
        compute_pagerank: If True, compute PageRank on the def/ref graph
            and store the score on each SymbolNode. Cheap enough for small
            repos and useful for D.4's context_bundle ranking. Set False
            in tests where determinism matters more than ranking.
    """
    root = Path(repo_root).resolve()
    repo_key = _repo_key(root)
    src_files = list(files) if files is not None else iter_source_files(root)

    index = RepoIndex(repo_root=str(root), repo_key=repo_key)

    # Step 1: extract tags per file. Keep them by rel_path so we can build
    # File nodes and later resolve references.
    tags_by_file: dict[str, list[Tag]] = {}
    for path in src_files:
        rel = _rel_posix(path, root)
        lang = language_for_path(path)
        if lang is None:  # defensive; iter_source_files already filters
            continue
        index.files.append(FileNode(rel_path=rel, language=lang))
        tags_by_file[rel] = extract_tags(path, rel_fname=rel)

    # Step 2: gather DEFs into a symbol table keyed by
    # (rel_path, name, start_line). Also build a global name -> [SymbolKey]
    # index for cross-file reference resolution.
    name_to_keys: dict[str, list[SymbolKey]] = {}
    for rel, tags in tags_by_file.items():
        for t in tags:
            if t.kind != TagKind.DEF:
                continue
            sym = SymbolNode(
                rel_path=t.rel_fname,
                name=t.name,
                category=t.category.value,
                start_line=t.start_line,
                end_line=t.end_line,
                parent=t.parent,
                info=t.info,
            )
            key = sym.key
            index.symbols[key] = sym
            name_to_keys.setdefault(t.name, []).append(key)

    # Step 3: resolve REF tags to symbols. Preference order:
    #   1) A symbol defined in the same file (most likely intra-module call).
    #   2) A single global match anywhere in the repo.
    #   3) All global matches (ambiguous \u2014 keep them all; downstream can
    #      still surface useful "candidate callee" edges).
    #   4) None \u2014 emit UnresolvedCall.
    for rel, tags in tags_by_file.items():
        for t in tags:
            if t.kind != TagKind.REF:
                continue
            # IMPORT refs are informational only; they don't produce CALLS
            # edges but a future slice may use them for cross-file link
            # candidates.
            if t.category == TagCategory.IMPORT:
                continue

            candidates = name_to_keys.get(t.name, [])
            same_file = [k for k in candidates if k[0] == rel]
            resolved: list[SymbolKey]
            if same_file:
                resolved = same_file
            elif candidates:
                resolved = candidates
            else:
                index.unresolved_calls.append(
                    UnresolvedCall(
                        src_rel_path=rel,
                        callee_name=t.name,
                        line=t.start_line,
                    )
                )
                continue

            for k in resolved:
                index.calls.append(
                    CallEdge(
                        src_rel_path=rel,
                        dst_symbol_key=k,
                        callee_name=t.name,
                        line=t.start_line,
                    )
                )

    # Step 4: derive METHOD_OF edges from Symbol.parent -> class symbol in
    # the same file. We rely on the parser producing method tags with
    # `parent=<class name>`.
    for sym in list(index.symbols.values()):
        if sym.category != TagCategory.METHOD.value or sym.parent is None:
            continue
        class_candidates = [
            k
            for k in index.symbols
            if k[0] == sym.rel_path
            and k[1] == sym.parent
            and index.symbols[k].category == TagCategory.CLASS.value
        ]
        if class_candidates:
            index.method_edges.append(
                MethodOfEdge(method_key=sym.key, class_key=class_candidates[0])
            )

    # Step 5: PageRank on the (File+Symbol) directed graph. Nodes are the
    # symbol keys; edges are (calling file's implicit node) -> (dst symbol).
    # RepoGraph's ranking works over this shape to surface "hub" symbols.
    if compute_pagerank and index.symbols:
        ranks = _compute_pagerank(index)
        # Replace SymbolNodes with copies carrying the score.
        for key, score in ranks.items():
            old = index.symbols[key]
            index.symbols[key] = SymbolNode(
                rel_path=old.rel_path,
                name=old.name,
                category=old.category,
                start_line=old.start_line,
                end_line=old.end_line,
                parent=old.parent,
                info=old.info,
                pagerank=score,
            )

    return index


def _compute_pagerank(index: RepoIndex) -> dict[SymbolKey, float]:
    """Run PageRank on a directed graph of calls into symbols.

    Nodes:  every SymbolKey.
    Edges:  for each CallEdge, add an edge from every symbol defined in the
            caller file to the callee symbol. This matches RepoGraph's
            heuristic of treating "file X calls Y" as "every def in X
            endorses Y".

    Uses a pure-Python power iteration so we don't need numpy/scipy just
    for this one computation. Small repos converge in <50 iterations; big
    ones cap at max_iter regardless.
    """
    nodes: list[SymbolKey] = list(index.symbols.keys())
    if not nodes:
        return {}

    # Adjacency: out_edges[u] -> list of v
    out_edges: dict[SymbolKey, list[SymbolKey]] = {n: [] for n in nodes}

    # Precompute defs per file so we don't re-scan for each edge.
    defs_by_file: dict[str, list[SymbolKey]] = {}
    for key in nodes:
        defs_by_file.setdefault(key[0], []).append(key)

    for c in index.calls:
        src_defs = defs_by_file.get(c.src_rel_path, [])
        for s in src_defs:
            if s != c.dst_symbol_key:
                out_edges[s].append(c.dst_symbol_key)

    return _power_iteration_pagerank(nodes, out_edges)


def _power_iteration_pagerank(
    nodes: list[SymbolKey],
    out_edges: dict[SymbolKey, list[SymbolKey]],
    *,
    alpha: float = 0.85,
    tol: float = 1.0e-6,
    max_iter: int = 100,
) -> dict[SymbolKey, float]:
    """Numpy-free PageRank via power iteration.

    Standard formulation: r_{t+1} = (1-alpha)/N + alpha * (M @ r_t), where
    the mass at each dangling node (no outbound edges) is redistributed
    uniformly across all nodes.
    """
    n = len(nodes)
    if n == 0:
        return {}
    total_edges = sum(len(v) for v in out_edges.values())
    if total_edges == 0:
        return {node: 0.0 for node in nodes}

    initial = 1.0 / n
    rank: dict[SymbolKey, float] = {node: initial for node in nodes}
    teleport = (1.0 - alpha) / n

    for _ in range(max_iter):
        new_rank: dict[SymbolKey, float] = {node: teleport for node in nodes}

        # Dangling mass — mass held by nodes with no out-edges gets
        # redistributed uniformly across all nodes.
        dangling_mass = 0.0
        for node, out in out_edges.items():
            if not out:
                dangling_mass += rank[node]

        if dangling_mass:
            share = alpha * dangling_mass / n
            for node in nodes:
                new_rank[node] += share

        # Push contribution from each non-dangling node to its successors.
        for node, out in out_edges.items():
            if not out:
                continue
            contribution = alpha * rank[node] / len(out)
            for dst in out:
                new_rank[dst] += contribution

        # Convergence check (L1 diff).
        diff = 0.0
        for node in nodes:
            diff += abs(new_rank[node] - rank[node])
        rank = new_rank
        if diff < tol:
            break

    return rank


# --- Utilities -------------------------------------------------------------


def _rel_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _repo_key(root: Path) -> str:
    """Stable 12-char key for a repo, derived from its absolute path.

    Not cryptographic \u2014 just needs to be collision-free across the small
    number of repos a single Colossus install indexes.
    """
    return hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]


# Re-export SUPPORTED_LANGUAGES for callers that want to gate on it before
# invoking build_index.
__all__ = [
    "SUPPORTED_LANGUAGES",
    "CallEdge",
    "FileNode",
    "MethodOfEdge",
    "RepoIndex",
    "SymbolKey",
    "SymbolNode",
    "UnresolvedCall",
    "build_index",
    "iter_source_files",
]
