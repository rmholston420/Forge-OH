"""Unit tests for openhands_tools_ext.repograph.store.

These tests use a mock neo4j.Driver so they can run in CI without a live
Neo4j / DozerDB instance. A separate integration test that hits real
DozerDB will run on Colossus only, gated by the NEO4J_PASSWORD env var
(added in D.4 or D.5 when the endpoints are wired).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openhands_tools_ext.repograph.index import build_index
from openhands_tools_ext.repograph.store import CONSTRAINT_STATEMENTS, Neo4jStore


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mock_driver():
    """A fake neo4j.Driver whose session() yields a MagicMock session."""
    driver = MagicMock()
    session = MagicMock()
    tx = MagicMock()

    # Session context manager
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = False

    # Transaction context manager
    session.begin_transaction.return_value.__enter__.return_value = tx
    session.begin_transaction.return_value.__exit__.return_value = False

    return driver, session, tx


class TestEnsureSchema:
    def test_runs_every_constraint_statement(self, mock_driver):
        driver, session, _tx = mock_driver
        store = Neo4jStore(driver=driver, database="forgeoh")
        store.ensure_schema()
        assert session.run.call_count == len(CONSTRAINT_STATEMENTS)
        for call, expected in zip(session.run.call_args_list, CONSTRAINT_STATEMENTS):
            assert call.args[0] == expected

    def test_uses_configured_database(self, mock_driver):
        driver, _session, _tx = mock_driver
        Neo4jStore(driver=driver, database="forgeoh").ensure_schema()
        driver.session.assert_called_with(database="forgeoh")


class TestReplaceRepo:
    def test_delete_then_write_all_categories(self, mock_driver, tmp_path):
        driver, _session, tx = mock_driver
        _write(tmp_path, "lib.py", "def hello(): return 1\n")
        _write(
            tmp_path,
            "app.py",
            "from lib import hello\n\nclass App:\n    def run(self):\n        return hello()\n",
        )
        idx = build_index(tmp_path, compute_pagerank=False)

        store = Neo4jStore(driver=driver, database="forgeoh")
        stats = store.replace_repo(idx)

        # First run should be the DETACH DELETE
        first_stmt = tx.run.call_args_list[0].args[0]
        assert "DETACH DELETE" in first_stmt

        # There should be a File insert, a Symbol insert, a CONTAINS edge,
        # a METHOD_OF edge (App.run), and a CALLS edge (hello).
        stmts = [c.args[0] for c in tx.run.call_args_list]
        assert any("MERGE (f:File" in s for s in stmts)
        assert any("MERGE (s:Symbol" in s for s in stmts)
        assert any("MERGE (f)-[:CONTAINS]->(s)" in s for s in stmts)
        assert any("MERGE (m)-[:METHOD_OF]->(c)" in s for s in stmts)
        assert any("MERGE (f)-[c:CALLS" in s for s in stmts)

        # Stats returned match index stats
        assert stats == idx.stats
        # Transaction committed exactly once
        tx.commit.assert_called_once()

    def test_empty_index_only_runs_delete(self, mock_driver, tmp_path):
        driver, _session, tx = mock_driver
        idx = build_index(tmp_path, compute_pagerank=False)  # empty repo
        Neo4jStore(driver=driver, database="forgeoh").replace_repo(idx)
        stmts = [c.args[0] for c in tx.run.call_args_list]
        # Only the DETACH DELETE runs when there's nothing to insert.
        assert len(stmts) == 1
        assert "DETACH DELETE" in stmts[0]

    def test_unresolved_calls_produce_self_loop_edge(self, mock_driver, tmp_path):
        driver, _session, tx = mock_driver
        _write(tmp_path, "m.py", "def user():\n    return external_thing()\n")
        idx = build_index(tmp_path, compute_pagerank=False)
        assert idx.unresolved_calls
        Neo4jStore(driver=driver, database="forgeoh").replace_repo(idx)
        stmts = [c.args[0] for c in tx.run.call_args_list]
        assert any(
            "MERGE (f)-[:UNRESOLVED_CALL" in s for s in stmts
        )


class TestReads:
    def test_search_by_name_shape(self, mock_driver):
        driver, session, _tx = mock_driver
        session.run.return_value.data.return_value = [
            {"rel_path": "m.py", "name": "hello", "category": "function",
             "start_line": 1, "end_line": 2, "parent": None,
             "info": "def hello", "pagerank": 0.5}
        ]
        store = Neo4jStore(driver=driver, database="forgeoh")
        result = store.search_by_name("repo1", "hell")
        assert result[0]["name"] == "hello"
        called = session.run.call_args
        assert "toLower(s.name) CONTAINS toLower($q)" in called.args[0]
        assert called.kwargs["q"] == "hell"
        assert called.kwargs["repo"] == "repo1"

    def test_callers_of_optional_rel_path(self, mock_driver):
        driver, session, _tx = mock_driver
        session.run.return_value.data.return_value = []
        store = Neo4jStore(driver=driver, database="forgeoh")

        # Without rel_path
        store.callers_of("repo1", "hello")
        cypher_1 = session.run.call_args.args[0]
        assert "s.rel_path = $rel_path" not in cypher_1

        # With rel_path
        store.callers_of("repo1", "hello", rel_path="lib.py")
        cypher_2 = session.run.call_args.args[0]
        assert "s.rel_path = $rel_path" in cypher_2

    def test_callees_of_shape(self, mock_driver):
        driver, session, _tx = mock_driver
        session.run.return_value.data.return_value = []
        Neo4jStore(driver=driver, database="forgeoh").callees_of("repo1", "app.py")
        cypher = session.run.call_args.args[0]
        assert "MATCH (f:File {repo: $repo, rel_path: $rel_path})" in cypher
        assert "[c:CALLS]->(s:Symbol)" in cypher

    def test_context_bundle_uses_seeds(self, mock_driver):
        driver, session, _tx = mock_driver
        session.run.return_value.data.return_value = []
        Neo4jStore(driver=driver, database="forgeoh").context_bundle(
            "repo1", ["app.py", "lib.py"], limit=25
        )
        cypher = session.run.call_args.args[0]
        assert "f.rel_path IN $seeds" in cypher
        assert session.run.call_args.kwargs["seeds"] == ["app.py", "lib.py"]
        assert session.run.call_args.kwargs["limit"] == 25


class TestDeleteRepo:
    def test_returns_deleted_count(self, mock_driver):
        driver, session, _tx = mock_driver
        session.run.return_value.single.return_value = {"deleted": 7}
        store = Neo4jStore(driver=driver, database="forgeoh")
        assert store.delete_repo("repo1") == 7

    def test_zero_when_missing(self, mock_driver):
        driver, session, _tx = mock_driver
        session.run.return_value.single.return_value = None
        assert Neo4jStore(driver=driver, database="forgeoh").delete_repo("nope") == 0
