"""Stage 3.4 \u2014 contract test for the compare_runs FastAPI query keys.

Guards against future drift: the BFF must accept `?base=&fork=` and reject
`?left=&right=` with 422. Complements the service-level tests in
`test_run_compare.py` which cover the diff computation itself.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import runs

app = FastAPI()
app.include_router(runs.router, prefix="/api")
client = TestClient(app)


class TestCompareRunsQueryContract:
    def test_missing_base_returns_422(self) -> None:
        resp = client.get("/api/runs/compare", params={"fork": "run-b"})
        assert resp.status_code == 422
        body = resp.json()
        # FastAPI-style validation error: at least one entry mentions `base`.
        assert any("base" in str(err.get("loc", ())) for err in body["detail"])

    def test_missing_fork_returns_422(self) -> None:
        resp = client.get("/api/runs/compare", params={"base": "run-a"})
        assert resp.status_code == 422
        body = resp.json()
        assert any("fork" in str(err.get("loc", ())) for err in body["detail"])

    def test_left_right_alone_is_422(self) -> None:
        # Stage 3.4 explicit anti-drift guard: the stale `left`/`right`
        # spelling must not accidentally be accepted.
        resp = client.get(
            "/api/runs/compare",
            params={"left": "run-a", "right": "run-b"},
        )
        assert resp.status_code == 422

    def test_base_and_fork_are_accepted(self) -> None:
        # With both query keys present, the endpoint should proceed past
        # validation. Mock the downstream event fetch + conversation fetch
        # so the test runs offline (no agent-server on :8090 required).
        with (
            patch(
                "bff.routers.runs._fetch_all_events",
                new=AsyncMock(return_value=[]),
            ),
            patch("bff.routers.runs.get_client") as get_client_mock,
        ):
            mock_client = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.json = lambda: {}
            mock_client.get = AsyncMock(return_value=mock_resp)
            get_client_mock.return_value = mock_client

            resp = client.get(
                "/api/runs/compare",
                params={"base": "run-a", "fork": "run-b"},
            )

        assert resp.status_code == 200
        body = resp.json()
        # compare_runs wraps its result in {"data": {...}}.
        assert "data" in body
        assert body["data"]["baseRunId"] == "run-a"
        assert body["data"]["forkRunId"] == "run-b"
