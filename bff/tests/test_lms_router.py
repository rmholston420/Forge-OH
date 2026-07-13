"""Unit tests for bff/routers/lms.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import time

from bff.routers import lms
from bff.auth_state import _TOKENS

app = FastAPI()
app.include_router(lms.router, prefix="/api")
client = TestClient(app)

VALID_TOKEN = next(iter(_TOKENS))
AUTH = {"Authorization": f"Bearer {VALID_TOKEN}"}

CONTEXT_PAYLOAD = {
    "courseId": "course-101",
    "moduleId": "mod-01",
    "learnerProfile": {"level": "beginner"},
}


class TestCreateContext:
    def test_authed_returns_200(self):
        r = client.post("/api/lms/context", headers=AUTH, json=CONTEXT_PAYLOAD)
        assert r.status_code == 200

    def test_unauthed_returns_401(self):
        r = client.post("/api/lms/context", json=CONTEXT_PAYLOAD)
        assert r.status_code == 401

    def test_session_id_in_response(self):
        body = client.post("/api/lms/context", headers=AUTH, json=CONTEXT_PAYLOAD).json()
        assert "sessionId" in body["data"]

    def test_session_id_is_string(self):
        body = client.post("/api/lms/context", headers=AUTH, json=CONTEXT_PAYLOAD).json()
        assert isinstance(body["data"]["sessionId"], str)


class TestGetContext:
    def _create_session(self) -> str:
        body = client.post("/api/lms/context", headers=AUTH, json=CONTEXT_PAYLOAD).json()
        return body["data"]["sessionId"]

    def test_get_known_session_returns_200(self):
        sid = self._create_session()
        r = client.get(f"/api/lms/context/{sid}", headers=AUTH)
        assert r.status_code == 200

    def test_get_unknown_session_returns_404(self):
        r = client.get("/api/lms/context/does-not-exist", headers=AUTH)
        assert r.status_code == 404

    def test_unauthed_returns_401(self):
        sid = self._create_session()
        r = client.get(f"/api/lms/context/{sid}")
        assert r.status_code == 401

    def test_context_data_echoed(self):
        sid = self._create_session()
        body = client.get(f"/api/lms/context/{sid}", headers=AUTH).json()
        assert body["data"]["courseId"] == "course-101"


class TestSessionEviction:
    """TTL eviction: sessions older than 3600 s must not be retrievable."""

    def test_expired_session_returns_404(self, monkeypatch):
        sid = client.post("/api/lms/context", headers=AUTH, json=CONTEXT_PAYLOAD).json()["data"]["sessionId"]
        # Back-date the creation timestamp by 3601 seconds
        ctx, _ts = lms._sessions[sid]
        lms._sessions[sid] = (ctx, time.time() - 3601)
        r = client.get(f"/api/lms/context/{sid}", headers=AUTH)
        assert r.status_code == 404
