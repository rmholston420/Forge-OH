"""
Neo4j persistence for the RepoGraph structural index.

Schema (all nodes carry a ``repo`` property so a single DozerDB database
can host multiple indexed repos side by side):

  (:File   {repo, rel_path, language})
  (:Symbol {repo, rel_path, name, category, start_line, end_line, parent,
            info, pagerank})

Edges:
  (:File)-[:CONTAINS]->(:Symbol)
  (:Symbol)-[:METHOD_OF]->(:Symbol)
  (:File)-[:CALLS {name, line}]->(:Symbol)
  (:File)-[:UNRESOLVED_CALL {name, line}]->(:File)  (self-loop on same file)

Constraints (created lazily via ensure_schema):
  * (File.repo, File.rel_path) unique
  * (Symbol.repo, Symbol.rel_path, Symbol.name, Symbol.start_line) unique

Every write goes through ``replace_repo`` which is idempotent: it deletes
all nodes carrying the target ``repo`` key inside one transaction, then
recreates them from the ``RepoIndex``. This is simpler and safer than
diffing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from neo4j import Driver

from openhands_tools_ext.repograph.index import RepoIndex

logger = logging.getLogger(__name__)


CONSTRAINT_STATEMENTS: tuple[str, ...] = (
    # File uniqueness per repo + rel_path
    (
        "CREATE CONSTRAINT forgeoh_file_unique IF NOT EXISTS "
        "FOR (f:File) REQUIRE (f.repo, f.rel_path) IS UNIQUE"
    ),
    # Symbol uniqueness per repo + rel_path + name + start_line
    (
        "CREATE CONSTRAINT forgeoh_symbol_unique IF NOT EXISTS "
        "FOR (s:Symbol) REQUIRE (s.repo, s.rel_path, s.name, s.start_line) IS UNIQUE"
    ),
    # Speed up name-based search
    ("CREATE INDEX forgeoh_symbol_name IF NOT EXISTS FOR (s:Symbol) ON (s.repo, s.name)"),
)


@dataclass
class Neo4jStore:
    """Thin wrapper around a neo4j.Driver bound to a specific database."""

    driver: Driver
    database: str

    # --- schema ------------------------------------------------------------

    def ensure_schema(self) -> None:
        """Create constraints + indexes if missing. Idempotent."""
        with self.driver.session(database=self.database) as session:
            for stmt in CONSTRAINT_STATEMENTS:
                session.run(stmt).consume()

    # --- writes ------------------------------------------------------------

    def replace_repo(self, index: RepoIndex) -> dict[str, int]:
        """Delete any existing nodes for this repo, then re-insert from index.

        Returns a summary of counts written (for logging + tests).
        """
        with (
            self.driver.session(database=self.database) as session,
            session.begin_transaction() as tx,
        ):
            tx.run(
                "MATCH (n {repo: $repo}) DETACH DELETE n",
                repo=index.repo_key,
            ).consume()

            # Files
            if index.files:
                tx.run(
                    "UNWIND $rows AS row "
                    "MERGE (f:File {repo: $repo, rel_path: row.rel_path}) "
                    "SET f.language = row.language",
                    repo=index.repo_key,
                    rows=[{"rel_path": f.rel_path, "language": f.language} for f in index.files],
                ).consume()

            # Symbols
            if index.symbols:
                tx.run(
                    "UNWIND $rows AS row "
                    "MERGE (s:Symbol {"
                    "  repo: $repo, "
                    "  rel_path: row.rel_path, "
                    "  name: row.name, "
                    "  start_line: row.start_line"
                    "}) "
                    "SET s.category = row.category, "
                    "    s.end_line = row.end_line, "
                    "    s.parent = row.parent, "
                    "    s.info = row.info, "
                    "    s.pagerank = row.pagerank",
                    repo=index.repo_key,
                    rows=[
                        {
                            "rel_path": s.rel_path,
                            "name": s.name,
                            "category": s.category,
                            "start_line": s.start_line,
                            "end_line": s.end_line,
                            "parent": s.parent,
                            "info": s.info,
                            "pagerank": s.pagerank,
                        }
                        for s in index.symbols.values()
                    ],
                ).consume()

            # (:File)-[:CONTAINS]->(:Symbol)
            if index.symbols:
                tx.run(
                    "UNWIND $rows AS row "
                    "MATCH (f:File {repo: $repo, rel_path: row.rel_path}) "
                    "MATCH (s:Symbol {repo: $repo, rel_path: row.rel_path, "
                    "                  name: row.name, start_line: row.start_line}) "
                    "MERGE (f)-[:CONTAINS]->(s)",
                    repo=index.repo_key,
                    rows=[
                        {
                            "rel_path": s.rel_path,
                            "name": s.name,
                            "start_line": s.start_line,
                        }
                        for s in index.symbols.values()
                    ],
                ).consume()

            # METHOD_OF
            if index.method_edges:
                tx.run(
                    "UNWIND $rows AS row "
                    "MATCH (m:Symbol {repo: $repo, rel_path: row.m_rel, "
                    "                  name: row.m_name, start_line: row.m_line}) "
                    "MATCH (c:Symbol {repo: $repo, rel_path: row.c_rel, "
                    "                  name: row.c_name, start_line: row.c_line}) "
                    "MERGE (m)-[:METHOD_OF]->(c)",
                    repo=index.repo_key,
                    rows=[
                        {
                            "m_rel": e.method_key[0],
                            "m_name": e.method_key[1],
                            "m_line": e.method_key[2],
                            "c_rel": e.class_key[0],
                            "c_name": e.class_key[1],
                            "c_line": e.class_key[2],
                        }
                        for e in index.method_edges
                    ],
                ).consume()

            # CALLS
            if index.calls:
                tx.run(
                    "UNWIND $rows AS row "
                    "MATCH (f:File {repo: $repo, rel_path: row.src_rel}) "
                    "MATCH (s:Symbol {repo: $repo, rel_path: row.dst_rel, "
                    "                  name: row.dst_name, start_line: row.dst_line}) "
                    "MERGE (f)-[c:CALLS {name: row.callee, line: row.line}]->(s)",
                    repo=index.repo_key,
                    rows=[
                        {
                            "src_rel": c.src_rel_path,
                            "dst_rel": c.dst_symbol_key[0],
                            "dst_name": c.dst_symbol_key[1],
                            "dst_line": c.dst_symbol_key[2],
                            "callee": c.callee_name,
                            "line": c.line,
                        }
                        for c in index.calls
                    ],
                ).consume()

            # UNRESOLVED_CALL as a self-loop on the source file
            if index.unresolved_calls:
                tx.run(
                    "UNWIND $rows AS row "
                    "MATCH (f:File {repo: $repo, rel_path: row.src_rel}) "
                    "MERGE (f)-[:UNRESOLVED_CALL {name: row.callee, line: row.line}]->(f)",
                    repo=index.repo_key,
                    rows=[
                        {
                            "src_rel": u.src_rel_path,
                            "callee": u.callee_name,
                            "line": u.line,
                        }
                        for u in index.unresolved_calls
                    ],
                ).consume()

            tx.commit()

        return index.stats

    def delete_repo(self, repo_key: str) -> int:
        """Remove all nodes/edges for a repo. Returns node-delete count."""
        with self.driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (n {repo: $repo}) DETACH DELETE n RETURN count(n) AS deleted",
                repo=repo_key,
            ).single()
            return int(result["deleted"]) if result else 0

    # --- reads (used by D.4 routers) --------------------------------------

    def search_by_name(
        self,
        repo_key: str,
        query: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Case-insensitive substring match on Symbol.name OR Symbol.rel_path.

        Users search by symbol name AND by filename interchangeably ("where
        is the run_metadata thing?"), so this matches either. When only the
        path matches, we still return the symbol row; the caller can group
        client-side by rel_path if they want a file-grouped UI.
        """
        with self.driver.session(database=self.database) as session:
            rows = session.run(
                "MATCH (s:Symbol {repo: $repo}) "
                "WHERE toLower(s.name) CONTAINS toLower($q) "
                "   OR toLower(s.rel_path) CONTAINS toLower($q) "
                "RETURN s.rel_path AS rel_path, s.name AS name, "
                "       s.category AS category, s.start_line AS start_line, "
                "       s.end_line AS end_line, s.parent AS parent, "
                "       s.info AS info, s.pagerank AS pagerank "
                "ORDER BY s.pagerank DESC, s.name ASC "
                "LIMIT $limit",
                repo=repo_key,
                q=query,
                limit=limit,
            ).data()
        return rows

    def callers_of(
        self,
        repo_key: str,
        symbol_name: str,
        *,
        rel_path: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Files that call a symbol identified by name (optionally by file)."""
        cypher = (
            "MATCH (f:File)-[c:CALLS {name: $name}]->(s:Symbol) "
            "WHERE s.repo = $repo AND s.name = $name "
        )
        params: dict[str, Any] = {"repo": repo_key, "name": symbol_name, "limit": limit}
        if rel_path is not None:
            cypher += "AND s.rel_path = $rel_path "
            params["rel_path"] = rel_path
        cypher += (
            "RETURN f.rel_path AS caller_file, "
            "       s.rel_path AS callee_file, s.name AS callee, "
            "       s.start_line AS callee_line, c.line AS call_line "
            "ORDER BY caller_file, call_line "
            "LIMIT $limit"
        )
        with self.driver.session(database=self.database) as session:
            return session.run(cypher, **params).data()

    def callees_of(
        self,
        repo_key: str,
        rel_path: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """All symbols called from a given file."""
        with self.driver.session(database=self.database) as session:
            return session.run(
                "MATCH (f:File {repo: $repo, rel_path: $rel_path})"
                "-[c:CALLS]->(s:Symbol) "
                "RETURN s.rel_path AS callee_file, s.name AS callee, "
                "       s.category AS category, s.start_line AS callee_line, "
                "       c.line AS call_line, s.pagerank AS pagerank "
                "ORDER BY s.pagerank DESC, callee_file, call_line "
                "LIMIT $limit",
                repo=repo_key,
                rel_path=rel_path,
                limit=limit,
            ).data()

    def context_bundle(
        self,
        repo_key: str,
        rel_paths: list[str],
        *,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        """PageRank-ranked context for a set of seed files.

        Returns the top-``limit`` symbols reachable from the seed files
        (either defined in them or called by them), ordered by PageRank.
        This is the input to D.4's context_bundle endpoint, which downstream
        callers use as the coding-agent's read-list.
        """
        with self.driver.session(database=self.database) as session:
            return session.run(
                "MATCH (f:File) "
                "WHERE f.repo = $repo AND f.rel_path IN $seeds "
                "OPTIONAL MATCH (f)-[:CONTAINS]->(local:Symbol) "
                "OPTIONAL MATCH (f)-[:CALLS]->(dep:Symbol) "
                "WITH collect(DISTINCT local) + collect(DISTINCT dep) AS syms "
                "UNWIND syms AS s "
                "WITH DISTINCT s WHERE s IS NOT NULL "
                "RETURN s.rel_path AS rel_path, s.name AS name, "
                "       s.category AS category, s.start_line AS start_line, "
                "       s.end_line AS end_line, s.info AS info, "
                "       s.pagerank AS pagerank "
                "ORDER BY s.pagerank DESC "
                "LIMIT $limit",
                repo=repo_key,
                seeds=rel_paths,
                limit=limit,
            ).data()


__all__ = ["CONSTRAINT_STATEMENTS", "Neo4jStore"]
