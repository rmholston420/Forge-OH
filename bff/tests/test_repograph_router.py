"""Tests for the RepoGraph router (Slice D.1 \u2014 health endpoint only).

D.4 endpoints (index/search/callers/callees/co_changed/context_bundle) get
their own tests when that slice lands.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from bff.deps import neo4j_driver
from bff.main import app
from bff.settings import Settings, get_settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_driver_singleton() -> None:
    """Ensure each test starts with a clean Neo4j driver singleton."""
    neo4j_driver.reset_neo4j_driver()
    yield
    neo4j_driver.reset_neo4j_driver()


def _override_settings(**overrides) -> None:
    """Replace the cached Settings with a test instance."""
    get_settings.cache_clear()

    def _factory() -> Settings:
        base_kwargs = {
            "neo4j_bolt_uri": "bolt://localhost:7687",
            "neo4j_user": "neo4j",
            "neo4j_password": "",
            "neo4j_database": "forgeoh",
            "repograph_enabled": False,
        }
        base_kwargs.update(overrides)
        return Settings(**base_kwargs)

    app.dependency_overrides[get_settings] = _factory


def _restore_settings() -> None:
    app.dependency_overrides.pop(get_settings, None)
    get_settings.cache_clear()


class TestHealthDisabled:
    def test_returns_disabled_when_flag_off(self, client: TestClient) -> None:
        with patch("bff.routers.repograph.get_settings") as gs:
            gs.return_value = Settings(
                repograph_enabled=False,
                neo4j_password="anything",
            )
            response = client.get("/api/repograph/health")

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is False
        assert body["reachable"] is False
        assert "repograph_enabled=False" in body["error"]


class TestHealthNoPassword:
    def test_returns_error_when_password_missing(self, client: TestClient) -> None:
        # Patch BOTH the router-level get_settings (for the enabled check)
        # AND the deps.neo4j_driver.get_settings (which is what
        # get_neo4j_driver() itself calls to read the password).  Without
        # the second patch, get_neo4j_driver() reads the real env and, on
        # a workstation with a live DozerDB, returns a live driver — which
        # makes reachable:true and this assertion fail.  See DEBUG_LOG
        # 2026-08-06 01:23 EDT.
        empty_settings = Settings(repograph_enabled=True, neo4j_password="")
        with (
            patch("bff.routers.repograph.get_settings", return_value=empty_settings),
            patch("bff.deps.neo4j_driver.get_settings", return_value=empty_settings),
        ):
            response = client.get("/api/repograph/health")

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["reachable"] is False
        # `get_neo4j_driver()` returns None when password is empty, so the
        # error is the driver-init message, not the CALL-dbms.components one.
        assert "driver init failed" in body["error"]


class TestHealthReachable:
    def test_returns_version_and_edition_when_neo4j_up(self, client: TestClient) -> None:
        # Build a fake driver whose .session().__enter__() returns a session
        # whose .run(...).single() yields the expected columns.
        fake_record = {"version": "5.26.27", "edition": "community"}
        fake_result = MagicMock()
        fake_result.single.return_value = fake_record

        fake_session = MagicMock()
        fake_session.__enter__.return_value = fake_session
        fake_session.__exit__.return_value = False
        fake_session.run.return_value = fake_result

        fake_driver = MagicMock()
        fake_driver.session.return_value = fake_session

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph.get_neo4j_driver", return_value=fake_driver),
        ):
            gs.return_value = Settings(
                repograph_enabled=True,
                neo4j_password="secret",
                neo4j_database="forgeoh",
            )
            response = client.get("/api/repograph/health")

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["reachable"] is True
        assert body["neo4j_version"] == "5.26.27"
        assert body["neo4j_edition"] == "community"
        assert body["database"] == "forgeoh"
        assert body["error"] is None
        # Confirm the router called .session(database=<configured>)
        fake_driver.session.assert_called_once_with(database="forgeoh")


class TestHealthUnreachable:
    def test_returns_error_when_query_raises(self, client: TestClient) -> None:
        fake_session = MagicMock()
        fake_session.__enter__.return_value = fake_session
        fake_session.__exit__.return_value = False
        fake_session.run.side_effect = RuntimeError("Bolt closed")

        fake_driver = MagicMock()
        fake_driver.session.return_value = fake_session

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph.get_neo4j_driver", return_value=fake_driver),
        ):
            gs.return_value = Settings(
                repograph_enabled=True,
                neo4j_password="secret",
                neo4j_database="forgeoh",
            )
            response = client.get("/api/repograph/health")

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["reachable"] is False
        assert "RuntimeError" in body["error"]
        assert "Bolt closed" in body["error"]


class TestDriverSingleton:
    def test_returns_none_when_disabled(self) -> None:
        with patch("bff.deps.neo4j_driver.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=False)
            assert neo4j_driver.get_neo4j_driver() is None

    def test_returns_none_when_password_empty(self) -> None:
        with patch("bff.deps.neo4j_driver.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="")
            assert neo4j_driver.get_neo4j_driver() is None

    def test_reset_clears_singleton(self) -> None:
        # Just prove the reset helper does what it says.
        neo4j_driver._driver = MagicMock()
        neo4j_driver.reset_neo4j_driver()
        assert neo4j_driver._driver is None

    def test_close_driver_is_idempotent(self) -> None:
        fake = MagicMock()
        neo4j_driver._driver = fake
        neo4j_driver.close_neo4j_driver()
        fake.close.assert_called_once()
        assert neo4j_driver._driver is None
        # Second call should not raise.
        neo4j_driver.close_neo4j_driver()


# --- D.4 tests -------------------------------------------------------------


class TestRejectsWhenDisabled:
    """All D.4 endpoints must 503 when repograph_enabled is False."""

    @pytest.mark.parametrize(
        "method,path,payload",
        [
            ("post", "/api/repograph/index", {"workspace_path": "/tmp"}),
            ("get", "/api/repograph/search?repo_key=r&q=a", None),
            ("get", "/api/repograph/callers?repo_key=r&name=a", None),
            ("get", "/api/repograph/callees?repo_key=r&rel_path=a.py", None),
            ("get", "/api/repograph/co_changed?repo_key=r&rel_path=a.py", None),
            (
                "post",
                "/api/repograph/context_bundle",
                {"repo_key": "r", "seeds": ["a.py"]},
            ),
            ("get", "/api/repograph/graph?repo_key=r", None),
        ],
    )
    def test_503_when_disabled(self, client: TestClient, method: str, path: str, payload) -> None:
        with patch("bff.routers.repograph.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=False, neo4j_password="anything")
            if method == "get":
                r = client.get(path)
            else:
                r = client.post(path, json=payload)
        assert r.status_code == 503
        assert "disabled" in r.json()["detail"].lower()


class TestIndexEndpoint:
    def test_index_writes_and_registers_workspace(self, client: TestClient, tmp_path) -> None:
        # Real repo on disk so build_index can extract tags for real.
        (tmp_path / "m.py").write_text("def a():\n    return 1\n", encoding="utf-8")

        fake_store = MagicMock()
        fake_store.replace_repo.return_value = {"files": 1, "symbols": 1}
        fake_store.ensure_schema.return_value = None

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph._get_store", return_value=fake_store),
        ):
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.post(
                "/api/repograph/index",
                json={"workspace_path": str(tmp_path)},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["stats"] == {"files": 1, "symbols": 1}
        assert body["workspace_path"] == str(tmp_path.resolve())
        assert len(body["repo_key"]) == 12
        fake_store.ensure_schema.assert_called_once()
        fake_store.replace_repo.assert_called_once()

        # Registry populated so co_changed can find it later.
        from bff.services import repograph_registry

        entry = repograph_registry.lookup(body["repo_key"])
        assert entry is not None
        assert entry.absolute_path == str(tmp_path.resolve())
        repograph_registry.clear()

    def test_index_rejects_nonexistent_path(self, client: TestClient) -> None:
        with patch("bff.routers.repograph.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.post(
                "/api/repograph/index",
                json={"workspace_path": "/definitely/not/a/real/path"},
            )
        assert r.status_code == 400
        assert "not a directory" in r.json()["detail"]


class TestSearchEndpoint:
    def test_search_returns_symbol_list(self, client: TestClient) -> None:
        rows = [
            {
                "rel_path": "m.py",
                "name": "hello",
                "category": "function",
                "start_line": 1,
                "end_line": 2,
                "parent": None,
                "info": "def hello():",
                "pagerank": 0.42,
            }
        ]
        fake_store = MagicMock()
        fake_store.search_by_name.return_value = rows

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph._get_store", return_value=fake_store),
        ):
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/search?repo_key=r1&q=hell&limit=10")

        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["name"] == "hello"
        assert body[0]["pagerank"] == 0.42
        fake_store.search_by_name.assert_called_once_with("r1", "hell", limit=10)

    def test_search_rejects_missing_q(self, client: TestClient) -> None:
        with patch("bff.routers.repograph.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/search?repo_key=r1")
        assert r.status_code == 422  # FastAPI validation


class TestCallersCalleesEndpoints:
    def test_callers_passes_rel_path_when_supplied(self, client: TestClient) -> None:
        fake_store = MagicMock()
        fake_store.callers_of.return_value = [
            {
                "caller_file": "app.py",
                "callee_file": "lib.py",
                "callee": "hello",
                "callee_line": 1,
                "call_line": 5,
            }
        ]

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph._get_store", return_value=fake_store),
        ):
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/callers?repo_key=r1&name=hello&rel_path=lib.py&limit=25")

        assert r.status_code == 200
        assert r.json()[0]["caller_file"] == "app.py"
        fake_store.callers_of.assert_called_once_with("r1", "hello", rel_path="lib.py", limit=25)

    def test_callees_shape(self, client: TestClient) -> None:
        fake_store = MagicMock()
        fake_store.callees_of.return_value = [
            {
                "callee_file": "lib.py",
                "callee": "hello",
                "category": "function",
                "callee_line": 1,
                "call_line": 5,
                "pagerank": 0.1,
            }
        ]

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph._get_store", return_value=fake_store),
        ):
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/callees?repo_key=r1&rel_path=app.py")

        assert r.status_code == 200
        assert r.json()[0]["category"] == "function"


class TestCoChangedEndpoint:
    def test_404_when_workspace_not_registered(self, client: TestClient) -> None:
        from bff.services import repograph_registry as reg

        reg.clear()
        with patch("bff.routers.repograph.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/co_changed?repo_key=missing&rel_path=x.py")
        assert r.status_code == 404
        assert "No workspace registered" in r.json()["detail"]

    def test_returns_ranked_files(self, client: TestClient, tmp_path) -> None:
        from bff.services import repograph_registry as reg

        reg.clear()
        reg.register("r1", tmp_path)

        # Fake `git log`: one call for the initial log, then one per sha.
        # We stub subprocess.run at the module level so both calls funnel
        # through us.
        log_stdout = "abc111\ndef222\nghi333\n"
        show_outputs = {
            "abc111": "\napp.py\nlib.py\n",
            "def222": "\napp.py\nutils.py\n",
            "ghi333": "\napp.py\nlib.py\n",
        }

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            if cmd[:3] == ["git", "log", "-n"]:
                result.returncode = 0
                result.stdout = log_stdout
                return result
            if cmd[:2] == ["git", "show"]:
                sha = cmd[-1]
                result.returncode = 0
                result.stdout = show_outputs.get(sha, "")
                return result
            result.returncode = 1
            result.stdout = ""
            return result

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph.subprocess.run", side_effect=fake_run),
        ):
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/co_changed?repo_key=r1&rel_path=app.py")

        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert body["target"] == "app.py"
        # lib.py touched in 2 of 3 commits, utils.py in 1
        by_name = {f["rel_path"]: f["commits"] for f in body["files"]}
        assert by_name == {"lib.py": 2, "utils.py": 1}
        # app.py itself is excluded
        assert "app.py" not in by_name

        reg.clear()

    def test_git_missing_returns_unavailable(self, client: TestClient, tmp_path) -> None:
        from bff.services import repograph_registry as reg

        reg.clear()
        reg.register("r1", tmp_path)

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch(
                "bff.routers.repograph.subprocess.run",
                side_effect=FileNotFoundError(),
            ),
        ):
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/co_changed?repo_key=r1&rel_path=app.py")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is False
        assert "git not found" in body["error"]

        reg.clear()


class TestContextBundleEndpoint:
    def test_context_bundle_returns_symbols(self, client: TestClient) -> None:
        rows = [
            {
                "rel_path": "lib.py",
                "name": "hello",
                "category": "function",
                "start_line": 1,
                "end_line": 2,
                "parent": None,
                "info": "def hello():",
                "pagerank": 0.9,
            }
        ]
        fake_store = MagicMock()
        fake_store.context_bundle.return_value = rows

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph._get_store", return_value=fake_store),
        ):
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.post(
                "/api/repograph/context_bundle",
                json={"repo_key": "r1", "seeds": ["app.py"], "limit": 10},
            )

        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["name"] == "hello"
        fake_store.context_bundle.assert_called_once_with("r1", ["app.py"], limit=10)

    def test_context_bundle_rejects_empty_seeds(self, client: TestClient) -> None:
        with patch("bff.routers.repograph.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.post(
                "/api/repograph/context_bundle",
                json={"repo_key": "r1", "seeds": [], "limit": 10},
            )
        assert r.status_code == 422  # min_length=1 on the list


class TestGraphEndpoint:
    def test_graph_returns_nodes_links_stats(self, client: TestClient) -> None:
        fake_store = MagicMock()
        fake_store.full_graph.return_value = {
            "nodes": [
                {
                    "id": "file::m.py",
                    "kind": "file",
                    "label": "m.py",
                    "rel_path": "m.py",
                    "language": "python",
                },
                {
                    "id": "sym::m.py::hello::1",
                    "kind": "symbol",
                    "label": "hello",
                    "rel_path": "m.py",
                    "category": "function",
                    "start_line": 1,
                    "end_line": 2,
                    "parent": None,
                    "pagerank": 0.42,
                },
            ],
            "links": [
                {
                    "source": "file::m.py",
                    "target": "sym::m.py::hello::1",
                    "type": "CONTAINS",
                },
                {
                    "source": "file::m.py",
                    "target": "sym::m.py::hello::1",
                    "type": "CALLS",
                    "line": 42,
                },
            ],
            "stats": {"nodes": 2, "symbols": 1, "files": 1, "edges": 2},
        }

        with (
            patch("bff.routers.repograph.get_settings") as gs,
            patch("bff.routers.repograph._get_store", return_value=fake_store),
        ):
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/graph?repo_key=abc&limit=100")

        assert r.status_code == 200
        body = r.json()
        assert body["repo_key"] == "abc"
        assert body["stats"] == {"nodes": 2, "symbols": 1, "files": 1, "edges": 2}
        assert len(body["nodes"]) == 2
        assert body["links"][1]["type"] == "CALLS"
        fake_store.full_graph.assert_called_once_with("abc", limit=100)

    def test_graph_rejects_limit_out_of_range(self, client: TestClient) -> None:
        with patch("bff.routers.repograph.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="secret")
            r = client.get("/api/repograph/graph?repo_key=abc&limit=99999")
        assert r.status_code == 422


class TestRegistry:
    def test_register_and_lookup_roundtrip(self) -> None:
        from bff.services import repograph_registry as reg

        reg.clear()
        entry = reg.register("k1", "/tmp")
        assert entry.repo_key == "k1"
        assert reg.lookup("k1").absolute_path.endswith("tmp")
        assert reg.lookup("missing") is None
        reg.clear()
