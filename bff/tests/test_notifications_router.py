"""Tests for bff/routers/notifications.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers import notifications

app = FastAPI()
app.include_router(notifications.router, prefix="/api")
client = TestClient(app)


class TestListNotifications:
    def test_returns_200(self):
        assert client.get("/api/notifications").status_code == 200

    def test_data_is_list(self):
        body = client.get("/api/notifications").json()
        payload = body.get("data", body) if isinstance(body, dict) else body
        assert isinstance(payload, list)


class TestMarkRead:
    def test_mark_single_read(self):
        r = client.post("/api/notifications/notif-001/read")
        assert r.status_code in (200, 404)

    def test_mark_all_read(self):
        r = client.post("/api/notifications/read-all")
        assert r.status_code == 200

    def test_mark_all_returns_ok(self):
        body = client.post("/api/notifications/read-all").json()
        assert body.get("ok") is True or "count" in body


class TestDeleteNotification:
    def test_delete_returns_200_or_404(self):
        r = client.delete("/api/notifications/notif-001")
        assert r.status_code in (200, 404)
