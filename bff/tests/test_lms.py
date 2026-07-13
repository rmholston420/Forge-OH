"""
Tests for bff/routers/lms.py

Covers: feature flag gate, auth guard on all 3 endpoints, TTL eviction,
inject/get/package happy paths.
"""
import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import patch
import bff.routers.lms as lms_module
from bff.main import app
from bff.auth_state import _TOKENS

client = TestClient(app)

VALID_CTX = {
    "userId": "usr_001",
    "courseId": "course-abc",
    "taskType": "exercise-gen",
    "permissions": {"canWriteRepo": True, "canRunShell": True, "canOpenPR": False},
    "pedagogicalContext": {"audience": "beginner", "learningGoals": ["closures"]},
}


@pytest.fixture(autouse=True)
def setup():
    _TOKENS.clear()
    _TOKENS["valid-token"] = "1"
    lms_module._sessions.clear()
    original_flag = lms_module.FEATURE_ENABLED
    lms_module.FEATURE_ENABLED = True
    yield
    lms_module.FEATURE_ENABLED = original_flag
    lms_module._sessions.clear()
    _TOKENS.clear()


AUTH = {"Authorization": "Bearer valid-token"}


class TestFeatureFlag:
    def test_inject_blocked_when_feature_disabled(self):
        lms_module.FEATURE_ENABLED = False
        r = client.post("/api/lms/context", json=VALID_CTX, headers=AUTH)
        assert r.status_code == 503

    def test_get_blocked_when_feature_disabled(self):
        lms_module.FEATURE_ENABLED = False
        r = client.get("/api/lms/context/sess_rigpa_abc123", headers=AUTH)
        assert r.status_code == 503

    def test_package_blocked_when_feature_disabled(self):
        lms_module.FEATURE_ENABLED = False
        r = client.post("/api/lms/package", json={
            "runId": "run-1", "artifactIds": ["art-1"],
            "targetType": "exercise", "courseId": "c-1"
        }, headers=AUTH)
        assert r.status_code == 503


class TestAuthGuard:
    def test_inject_without_token_returns_401(self):
        r = client.post("/api/lms/context", json=VALID_CTX)
        assert r.status_code == 401

    def test_inject_with_invalid_token_returns_401(self):
        r = client.post("/api/lms/context", json=VALID_CTX,
                        headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401

    def test_get_without_token_returns_401(self):
        r = client.get("/api/lms/context/any-session")
        assert r.status_code == 401

    def test_package_without_token_returns_401(self):
        r = client.post("/api/lms/package", json={
            "runId": "r", "artifactIds": ["a"], "targetType": "exercise", "courseId": "c"
        })
        assert r.status_code == 401


class TestInjectAndGet:
    def test_inject_returns_session_id_and_injected_true(self):
        r = client.post("/api/lms/context", json=VALID_CTX, headers=AUTH)
        assert r.status_code == 201
        body = r.json()
        assert body["injected"] is True
        assert body["sessionId"].startswith("sess_rigpa_")

    def test_get_returns_same_context(self):
        sess = client.post("/api/lms/context", json=VALID_CTX, headers=AUTH).json()["sessionId"]
        r = client.get(f"/api/lms/context/{sess}", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["courseId"] == "course-abc"
        assert r.json()["userId"] == "usr_001"

    def test_get_unknown_session_returns_404(self):
        r = client.get("/api/lms/context/sess_rigpa_doesnotexist", headers=AUTH)
        assert r.status_code == 404

    def test_each_inject_creates_unique_session_id(self):
        s1 = client.post("/api/lms/context", json=VALID_CTX, headers=AUTH).json()["sessionId"]
        s2 = client.post("/api/lms/context", json=VALID_CTX, headers=AUTH).json()["sessionId"]
        assert s1 != s2


class TestTTLEviction:
    def test_expired_session_returns_404(self):
        sess = client.post("/api/lms/context", json=VALID_CTX, headers=AUTH).json()["sessionId"]
        ctx, _ = lms_module._sessions[sess]
        lms_module._sessions[sess] = (ctx, time.monotonic() - lms_module._SESSION_TTL_SECONDS - 1)
        r = client.get(f"/api/lms/context/{sess}", headers=AUTH)
        assert r.status_code == 404

    def test_expired_session_is_evicted_from_store(self):
        sess = client.post("/api/lms/context", json=VALID_CTX, headers=AUTH).json()["sessionId"]
        ctx, _ = lms_module._sessions[sess]
        lms_module._sessions[sess] = (ctx, time.monotonic() - lms_module._SESSION_TTL_SECONDS - 1)
        client.get(f"/api/lms/context/{sess}", headers=AUTH)
        assert sess not in lms_module._sessions

    def test_fresh_session_not_evicted(self):
        sess = client.post("/api/lms/context", json=VALID_CTX, headers=AUTH).json()["sessionId"]
        lms_module._evict_expired()
        assert sess in lms_module._sessions


class TestPackage:
    def test_package_returns_one_item_per_artifact(self):
        r = client.post("/api/lms/package", json={
            "runId": "run-1",
            "artifactIds": ["art-aaa", "art-bbb"],
            "targetType": "exercise",
            "courseId": "course-abc",
        }, headers=AUTH)
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 2
        assert all(i["status"] == "packaged" for i in items)

    def test_package_lms_object_id_format(self):
        r = client.post("/api/lms/package", json={
            "runId": "run-1",
            "artifactIds": ["artifact-id-12345678"],
            "targetType": "feedback-record",
            "courseId": "c1",
        }, headers=AUTH)
        item = r.json()[0]
        assert item["lmsObjectId"].startswith("lms_feedback-record_")
        assert item["targetType"] == "feedback-record"
