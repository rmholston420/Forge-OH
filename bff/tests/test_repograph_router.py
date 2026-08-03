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
        with patch("bff.routers.repograph.get_settings") as gs:
            gs.return_value = Settings(repograph_enabled=True, neo4j_password="")
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
